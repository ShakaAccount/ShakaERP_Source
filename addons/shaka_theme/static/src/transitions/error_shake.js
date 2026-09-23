/** @odoo-module **/
import { Record } from "@web/model/relational_model/record";
import { patch } from "@web/core/utils/patch";

// Error state shake: a field still invalid from the last attempt keeps its
// class, so its CSS shake wouldn't play again. Replay it on every failed save.
patch(Record.prototype, {
    _displayInvalidFieldNotification() {
        for (const el of document.querySelectorAll(".o_field_widget.o_field_invalid")) {
            el.style.animation = "none";
            void el.offsetWidth; // restart from a clean baseline
            el.style.animation = "";
        }
        return super._displayInvalidFieldNotification(...arguments);
    },
});
