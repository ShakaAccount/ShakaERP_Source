/** @odoo-module **/
import { clamp } from "@web/core/utils/numbers";

// Shared open/close for floating menus: the Dropdown menu morph (t-morph) and
// Tooltip open/close (t-tt). Both CSS files treat `.is-open` as shown. Used by
// popover.js (Odoo dropdowns, tooltips) and autocomplete.js (many2one menus).
//
// Odoo removes these elements from the DOM on close, so the exit plays on an
// inert clone ("ghost"). Interruptible: a close mid-open, or a reopen while the
// ghost still plays, starts from the other element's *current* values instead
// of the end state of its class.

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
// What dropdown_menu_morph.css / tooltip.css tween, on the menu and its children.
const TWEENED = ["clip-path", "opacity", "scale", "translate", "filter"];
const ghosts = new Map(); // key (the menu's target) -> exit ghost still playing

// Morph: clip the menu to a target-sized box on the edge nearest the target.
// Real geometry, so RTL, upward-flipped and nested menus all work.
function morphFrom(menu, target) {
    const m = menu.getBoundingClientRect();
    const t = target.getBoundingClientRect();
    const w = Math.min(t.width, m.width);
    const h = Math.min(t.height, m.height);
    const x = clamp(t.left - m.left, 0, m.width - w);
    const y = clamp(t.top - m.top, 0, m.height - h);
    const inset = `${y}px ${m.width - x - w}px ${m.height - y - h}px ${x}px`;
    menu.style.setProperty("--morph-from", `inset(${inset} round var(--morph-r-closed))`);
    menu.style.setProperty("--morph-dir", y > 0 ? 1 : -1); // content slides from the target side
}

function snapshot(el) {
    return [el, ...el.children].map((node) => {
        const style = getComputedStyle(node);
        return TWEENED.map((prop) => style.getPropertyValue(prop));
    });
}

// Pin `snap` inline, commit it as the starting style, then release it: the
// caller's next class change transitions from there.
function startFrom(el, snap) {
    const nodes = [el, ...el.children];
    nodes.forEach((node, i) => {
        node.style.transition = "none";
        TWEENED.forEach((prop, j) => {
            const value = snap[i]?.[j];
            // clip-path `none` (a settled menu) can't interpolate; the class value stands in.
            if (value && !(prop === "clip-path" && value === "none")) {
                node.style.setProperty(prop, value);
            }
        });
    });
    void el.offsetWidth;
    nodes.forEach((node) => {
        node.style.transition = "";
        TWEENED.forEach((prop) => node.style.removeProperty(prop));
    });
}

/** Play the open of `el` (kind "t-morph" or "t-tt") growing out of `target`. */
export function openMenu(el, target, kind) {
    if (el.classList.contains(kind)) {
        return; // already open (repositioning)
    }
    if (kind === "t-morph") {
        morphFrom(el, target);
        el.addEventListener("transitionend", (ev) => {
            if (ev.target === el && ev.propertyName === "clip-path" && el.classList.contains("is-open")) {
                el.classList.add("is-settled"); // drop the clip so nothing overflowing is cut
            }
        });
    }
    el.classList.add(kind);
    const ghost = ghosts.get(target);
    if (ghost && !reducedMotion.matches) {
        // Reopened while its exit is still playing: continue from the ghost.
        const snap = snapshot(ghost);
        ghost.remove();
        ghosts.delete(target);
        startFrom(el, snap);
    } else {
        void el.offsetWidth; // commit the closed state before tweening
    }
    el.classList.add("is-open");
}

/** Play the close of `el`, which the caller is about to remove from the DOM. */
export function closeMenu(el, target) {
    if (!el?.classList.contains("is-open") || reducedMotion.matches) {
        return;
    }
    const snap = snapshot(el); // mid-open if closed while still opening
    const rect = el.getBoundingClientRect();
    const ghost = el.cloneNode(true);
    ghost.inert = true;
    ghost.removeAttribute("id");
    // Keep what came from its ancestors (e.g. `.o-autocomplete .o-autocomplete--dropdown-menu`
    // sets the z-index that lifts it above dialogs): the ghost lives on body.
    Object.assign(ghost.style, {
        zIndex: getComputedStyle(el).zIndex,
        boxSizing: "border-box",
        width: `${rect.width}px`,
        height: `${rect.height}px`,
    });
    // On body: Owl empties .o-overlay-container wholesale when its last overlay closes.
    document.body.append(ghost);
    ghost.classList.remove("is-settled");
    if (ghost.classList.contains("t-morph") && target?.isConnected) {
        morphFrom(ghost, target); // the menu may have grown since it opened
    }
    startFrom(ghost, snap);
    ghost.classList.remove("is-open");
    ghosts.get(target)?.remove();
    ghosts.set(target, ghost);
    // Only our transitions: an infinite spinner inside (autocomplete "loading")
    // would never settle and the ghost would stay forever.
    const exits = ghost
        .getAnimations({ subtree: true })
        .filter((a) => a instanceof CSSTransition)
        .map((a) => a.finished);
    Promise.allSettled(exits).then(() => {
        ghost.remove();
        if (ghosts.get(target) === ghost) {
            ghosts.delete(target);
        }
    });
}
