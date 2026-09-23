/** @odoo-module **/
import { onWillUnmount } from "@odoo/owl";
import { Popover } from "@web/core/popover/popover";
import { Tooltip } from "@web/core/tooltip/tooltip";
import { patch } from "@web/core/utils/patch";
import { closeMenu, openMenu } from "./morph";

// Dropdown menu morph on every Odoo dropdown menu, Tooltip open/close on every
// tooltip (transitions.dev); the mechanics live in morph.js.
patch(Popover.prototype, {
    setup() {
        super.setup();
        onWillUnmount(() => closeMenu(this.popoverRef.el, this.props.target));
    },

    onPositioned(solution) {
        const el = this.popoverRef.el;
        const isTooltip = this.props.component === Tooltip;
        if (isTooltip) {
            this.animationDone = true; // tooltip.css replaces Odoo's own fade/slide
        }
        super.onPositioned(solution);
        const kind = el?.classList.contains("o-dropdown--menu") ? "t-morph" : isTooltip && "t-tt";
        if (kind) {
            openMenu(el, this.props.target, kind);
        }
    },
});
