/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

export class PrStageRadio extends Component {
    static template = "payment_request.PrStageRadio";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ busy: false });
    }

    get allowReject() {
        return !!this.props.record.data.allow_reject;
    }

    get value() {
        return this.props.record.data.decision;
    }

    async onChange(value) {
        if (!value || this.state.busy) return;
        this.state.busy = true;
        try {
            // server write() applies the waterfall + chatter notifications
            await this.orm.write(
                this.props.record.resModel,
                [this.props.record.resId],
                { decision: value },
            );
            // reload the whole form: stage states + request state changed
            await this.action.doAction(
                { type: "ir.actions.client", tag: "reload_context" },
                { clearCache: true },
            );
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("fields").add("radio_pr_stage", {
    component: PrStageRadio,
    supportedTypes: ["selection"],
    fieldIsEditable: true,
});
