/** @odoo-module **/
import { onWillUnmount } from "@odoo/owl";
import { Popover } from "@web/core/popover/popover";
import { Tooltip } from "@web/core/tooltip/tooltip";
import { clamp } from "@web/core/utils/numbers";
import { patch } from "@web/core/utils/patch";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Dropdown menu morph: clip the menu to a toggler-sized box on the edge nearest
// the toggler. Real geometry, so RTL, upward-flipped and nested menus all work.
function morphFrom(menu, target) {
    const m = menu.getBoundingClientRect();
    const t = target.getBoundingClientRect();
    const w = Math.min(t.width, m.width);
    const h = Math.min(t.height, m.height);
    const x = clamp(t.left - m.left, 0, m.width - w);
    const y = clamp(t.top - m.top, 0, m.height - h);
    const inset = `${y}px ${m.width - x - w}px ${m.height - y - h}px ${x}px`;
    menu.style.setProperty("--morph-from", `inset(${inset} round var(--morph-r-closed))`);
    menu.style.setProperty("--morph-dir", y > 0 ? 1 : -1); // content slides from the toggler side
}

// Dropdown menu morph on every Odoo dropdown menu, Tooltip open/close on every
// tooltip (transitions.dev). Both CSS files treat `.is-open` as shown.
patch(Popover.prototype, {
    setup() {
        super.setup();
        onWillUnmount(() => {
            // Odoo drops the popover from the DOM on close; play the exit on an inert clone.
            const el = this.popoverRef.el;
            if (!el?.classList.contains("is-open") || reducedMotion.matches) {
                return;
            }
            const ghost = el.cloneNode(true);
            ghost.inert = true;
            ghost.removeAttribute("id");
            // Not in .o-overlay-container: Owl empties it wholesale when its last overlay closes.
            document.body.append(ghost);
            ghost.classList.remove("is-settled");
            void ghost.offsetWidth; // start from the open state
            ghost.classList.remove("is-open");
            const exits = ghost.getAnimations({ subtree: true }).map((a) => a.finished);
            Promise.allSettled(exits).then(() => ghost.remove());
        });
    },

    onPositioned(solution) {
        const el = this.popoverRef.el;
        const isTooltip = this.props.component === Tooltip;
        if (isTooltip) {
            this.animationDone = true; // tooltip.css replaces Odoo's own fade/slide
        }
        super.onPositioned(solution);
        const kind = el?.classList.contains("o-dropdown--menu") ? "t-morph" : isTooltip && "t-tt";
        if (!kind || el.classList.contains(kind)) {
            return; // other popover, or already opened (repositioning)
        }
        if (kind === "t-morph") {
            morphFrom(el, this.props.target);
            el.addEventListener("transitionend", (ev) => {
                if (ev.target === el && ev.propertyName === "clip-path" && el.classList.contains("is-open")) {
                    el.classList.add("is-settled");
                }
            });
        }
        el.classList.add(kind);
        void el.offsetWidth; // commit the closed state before tweening
        el.classList.add("is-open");
    },
});
