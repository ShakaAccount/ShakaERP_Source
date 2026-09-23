/** @odoo-module **/
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { patch } from "@web/core/utils/patch";

patch(StatusBarField.prototype, {
    /** 1-based position of `item` among all stages, and whether it is already passed. */
    shakaStep(item) {
        const all = this.getAllItems();
        const index = all.findIndex((i) => i.value === item.value);
        const current = all.findIndex((i) => i.isSelected);
        return { number: index + 1, done: current !== -1 && index < current };
    },
});
