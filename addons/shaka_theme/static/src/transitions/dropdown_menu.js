/** @odoo-module **/
import { onWillUnmount } from "@odoo/owl";
import { Popover } from "@web/core/popover/popover";
import { patch } from "@web/core/utils/patch";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Scale from the corner/edge the menu hangs off. Uses real geometry, so it is
// correct for RTL, flipped (opens upward) and nested submenus alike.
function originFor(menu, target) {
    const m = menu.getBoundingClientRect();
    const t = target.getBoundingClientRect();
    const y = m.top >= t.top ? "top" : "bottom";
    let x = "center";
    if (m.left >= t.right - 1 || Math.abs(m.left - t.left) < 2) {
        x = "left";
    } else if (m.right <= t.left + 1 || Math.abs(m.right - t.right) < 2) {
        x = "right";
    }
    return `${y}-${x}`;
}

// Menu dropdown (transitions.dev) on every Odoo dropdown menu.
patch(Popover.prototype, {
    setup() {
        super.setup();
        onWillUnmount(() => {
            // Odoo drops the menu from the DOM on close; fade out an inert clone.
            const menu = this.popoverRef.el;
            if (!menu?.classList.contains("is-open") || reducedMotion.matches) {
                return;
            }
            const ghost = menu.cloneNode(true);
            ghost.inert = true;
            ghost.removeAttribute("id");
            (menu.closest(".o-overlay-container") || document.body).append(ghost);
            void ghost.offsetWidth; // start from the open state
            ghost.classList.replace("is-open", "is-closing");
            const dur = parseFloat(getComputedStyle(ghost).getPropertyValue("--dropdown-close-dur"));
            setTimeout(() => ghost.remove(), dur || 150);
        });
    },

    onPositioned(solution) {
        super.onPositioned(solution);
        const menu = this.popoverRef.el;
        if (!menu?.classList.contains("o-dropdown--menu") || menu.classList.contains("t-dropdown")) {
            return; // not a dropdown, or already opened (repositioning)
        }
        menu.dataset.origin = originFor(menu, this.props.target);
        menu.classList.add("t-dropdown");
        void menu.offsetWidth; // commit the pre-open state before tweening
        menu.classList.add("is-open");
    },
});
