import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const TITLES = {
    local: "Local group", ssas: "SSAS role", pbirs: "PBIRS", members: "Members",
    user: "Windows account", dw: "Warehouse",
};
const ICON = { ok: "fa-check", fail: "fa-times", skip: "fa-minus" };

/** Renders the JSON steps of the last sync (of any model with action_sync), and can run a sync from the panel. */
export class SyncPanelField extends Component {
    static template = "win_access.SyncPanel";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ busy: false, open: {} });
    }

    get steps() {
        return this.props.record.data[this.props.name] || [];
    }

    get counts() {
        const c = { ok: 0, fail: 0, skip: 0 };
        this.steps.forEach((s) => c[s.status]++);
        return c;
    }

    get sections() {
        const keys = [...new Set(this.steps.map((s) => s.section))];
        return keys.map((key) => {
            const steps = this.steps.filter((s) => s.section === key);
            return { key, title: TITLES[key] || key, steps, failed: steps.some((s) => s.status === "fail") };
        });
    }

    icon(status) {
        return ICON[status];
    }

    // failures start expanded, successes collapsed; a click overrides
    isOpen(sec) {
        return this.state.open[sec.key] ?? sec.failed;
    }

    toggle(sec) {
        this.state.open[sec.key] = !this.isOpen(sec);
    }

    async copy(step) {
        const text = `${step.label}\n${step.message}\n${step.hint || ""}`.trim();
        try {
            await navigator.clipboard.writeText(text);
            this.notification.add("Copied.", { type: "success" });
        } catch {
            this.notification.add("Could not access the clipboard.", { type: "warning" });
        }
    }

    async runSync() {
        const rec = this.props.record;
        this.state.busy = true;
        try {
            if (!(await rec.save())) {
                return;
            }
            await this.orm.call(rec.resModel, "action_sync", [[rec.resId]]);
            await rec.load();
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("fields").add("win_access_sync", {
    component: SyncPanelField,
    supportedTypes: ["json"],
});
