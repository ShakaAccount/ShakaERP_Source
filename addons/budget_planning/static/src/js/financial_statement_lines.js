/** @odoo-module **/

import {Component} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {X2ManyField, x2ManyField} from "@web/views/fields/x2many/x2many_field";

class EntryModeDialog extends Component {
    static template = "budget_planning.EntryModeDialog";
    static components = {Dialog};
    static props = {close: Function, onSelect: Function};

    async select(mode) {
        this.props.close();
        await this.props.onSelect(mode);
    }
}

class FinancialStatementLines extends X2ManyField {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    async onAdd(params = {}) {
        if (this.props.record.data.entry_mode) {
            return super.onAdd(params);
        }
        this.dialog.add(EntryModeDialog, {
            onSelect: async (mode) => {
                await this.props.record.update({entry_mode: mode});
                await X2ManyField.prototype.onAdd.call(this, params);
            },
        });
    }
}

registry.category("fields").add("financial_statement_lines", {
    ...x2ManyField,
    component: FinancialStatementLines,
});
