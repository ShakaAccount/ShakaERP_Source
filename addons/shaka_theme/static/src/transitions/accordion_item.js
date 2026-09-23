/** @odoo-module **/
import { AccordionItem } from "@web/core/dropdown/accordion_item";
import { patch } from "@web/core/utils/patch";

// Accordion: Odoo's t-if drops the panel at once; keep it mounted (`closing`)
// until the collapse in accordion.scss has played.
patch(AccordionItem.prototype, {
    toggle() {
        clearTimeout(this.collapseTimer);
        this.state.open = !this.state.open;
        this.state.closing = !this.state.open;
        if (this.state.closing) {
            const dur = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--acc-collapse"));
            this.collapseTimer = setTimeout(() => (this.state.closing = false), dur || 250);
        }
    },
});
