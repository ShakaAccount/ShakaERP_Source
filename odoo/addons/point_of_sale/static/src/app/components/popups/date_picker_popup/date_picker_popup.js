import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DatePickerPopup extends Component {
    static template = "point_of_sale.DatePickerPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        confirmLabel: _t("Confirm"),
        title: _t("DatePicker"),
    };

    setup() {
        super.setup();
        this.datetimePicker = useService("datetime_picker");
        this.popupService = useService("popover");
        this.state = useState({ shippingDate: this._today() });
        this.inputRef = useRef("input");
        onMounted(() => this.inputRef.el.focus());
    }

    async confirm() {
        const date = this.state.shippingDate < this._today() ? this._today() : this.state.shippingDate;
        this.props.getPayload(date);
        this.props.close();
    }

    _today() {
        return new Date().toISOString().split("T")[0];
    }

    async openDatePicker() {
        const picker = this.datetimePicker.create({
            target: this.inputRef.el,
            pickerProps: {
                type: "date",
                value: this.state.shippingDate ? luxon.DateTime.fromISO(this.state.shippingDate) : null,
                minDate: luxon.DateTime.local().startOf("day"),
            },
            onApply: (value) => {
                if (value) {
                    this.state.shippingDate = value.toISODate();
                }
            },
        });
        picker.enable();
        picker.open(0);
    }
}
