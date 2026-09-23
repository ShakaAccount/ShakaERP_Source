/** @odoo-module **/
import { onMounted, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
// What modal.css tweens, per element of a dialog (.o_dialog root).
const PARTS = [
    [":scope > .modal", ["background-color"]],
    [":scope > .modal > .modal-dialog", ["transform", "opacity"]],
];

const parts = (root) => PARTS.map(([selector, props]) => [root.querySelector(selector), props]);

function setState(root, state) {
    for (const [el] of parts(root)) {
        el.classList.remove("is-open", "is-closing");
        if (state) {
            el.classList.add(state);
        }
    }
}

// Modal open/close (transitions.dev) on every Odoo dialog. Interruptible: a
// dialog closed while still opening closes from the scale/opacity on screen.
patch(Dialog.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            const modal = this.modalRef.el;
            if (!modal) {
                return;
            }
            modal.classList.add("t-modal-backdrop");
            modal.querySelector(":scope > .modal-dialog")?.classList.add("t-modal");
            void modal.offsetWidth; // commit the closed state before tweening
            setState(modal.parentElement, "is-open");
        });
        onWillUnmount(() => {
            const root = this.modalRef.el?.parentElement;
            if (!root?.querySelector(":scope > .modal.is-open") || reducedMotion.matches) {
                return;
            }
            // Odoo removes the dialog now; play the close on an inert clone.
            const live = parts(root);
            const snap = live.map(([el, props]) => {
                const style = getComputedStyle(el);
                return props.map((prop) => style.getPropertyValue(prop));
            });
            const ghost = root.cloneNode(true);
            ghost.inert = true;
            ghost.removeAttribute("id");
            document.body.append(ghost);
            // A clone has neither live input values nor scroll positions.
            const fields = "input, textarea, select";
            const liveFields = root.querySelectorAll(fields);
            ghost.querySelectorAll(fields).forEach((el, i) => {
                if (el.type !== "file") {
                    el.value = liveFields[i].value; // a file input's value can't be set
                }
                el.checked = liveFields[i].checked;
            });
            const scrollers = ":scope > .modal, .modal-body";
            const liveScrollers = root.querySelectorAll(scrollers);
            ghost.querySelectorAll(scrollers).forEach((el, i) => (el.scrollTop = liveScrollers[i].scrollTop));
            // Start from the values on screen (mid-open if closed while opening).
            const ghostParts = parts(ghost);
            ghostParts.forEach(([el, props], i) => {
                el.style.transition = "none";
                props.forEach((prop, j) => el.style.setProperty(prop, snap[i][j]));
            });
            void ghost.offsetWidth;
            ghostParts.forEach(([el, props]) => {
                el.style.transition = "";
                props.forEach((prop) => el.style.removeProperty(prop));
            });
            setState(ghost, "is-closing");
            // Only our transitions: an infinite spinner inside would never settle.
            const exits = ghost
                .getAnimations({ subtree: true })
                .filter((a) => a instanceof CSSTransition)
                .map((a) => a.finished);
            Promise.allSettled(exits).then(() => ghost.remove());
        });
    },
});
