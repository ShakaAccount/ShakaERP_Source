/** Many2one field that shows a spinner while its own value-change onchange is in flight.
 * Used for fields whose picker triggers a live, slow SSAS/warehouse call server-side (e.g.
 * picking the SSAS column here re-fetches that column's dimension member rows) -- the
 * standard Many2one gives no feedback that anything is happening until the whole round
 * trip finishes, which is confusing against a backend known to be slow. */
import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

export class LoadingMany2OneField extends Many2OneField {
    static template = "win_access.LoadingMany2One";

    setup() {
        super.setup();
        this.loadingState = useState({ busy: false });
    }

    get m2oProps() {
        const props = super.m2oProps;
        return {
            ...props,
            update: async (...args) => {
                this.loadingState.busy = true;
                try {
                    return await props.update(...args);
                } finally {
                    this.loadingState.busy = false;
                }
            },
        };
    }
}

registry.category("fields").add("win_access_m2o_loading", {
    ...buildM2OFieldDescription(LoadingMany2OneField),
});
