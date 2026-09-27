/** @odoo-module **/

import {Component, useState, useRef, useExternalListener} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class FinancialAccountTree extends Component {
    static template = "budget_planning.FinancialAccountTree";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.state = useState({open: false, nodes: [], expanded: {}, members: {}, loading: false, style: "", search: ""});
        useExternalListener(document, "pointerdown", (ev) => {
            if (this.state.open && this.root.el && !this.root.el.contains(ev.target)) {
                this.state.open = false;
            }
        });
    }

    get companyId() {
        const value = this.props.record.data.company_id;
        return Array.isArray(value) ? value[0] : (value?.id || value || false);
    }

    get roots() {
        return this.state.nodes.filter((node) => !node.parent_id && this.nodeMatches(node));
    }

    children(id) {
        return this.state.nodes.filter((node) => node.parent_id === id && this.nodeMatches(node));
    }

    normalize(value) {
        return String(value || "").toLocaleLowerCase("fa").replace(/[يى]/g, "ی").replace(/[ك]/g, "ک");
    }

    nodeMatches(node) {
        const term = this.normalize(this.state.search).trim();
        if (!term) return true;
        return this.normalize(node.title).includes(term)
            || this.state.nodes.some((child) => child.parent_id === node.id && this.nodeMatches(child));
    }

    members(id) {
        const term = this.normalize(this.state.search).trim();
        return (this.state.members[id] || []).filter((member) => !term
            || this.normalize(member.title).includes(term)
            || this.normalize(member.code).includes(term));
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
        if (this.state.search) {
            for (const node of this.state.nodes) {
                if (this.nodeMatches(node)) this.state.expanded[node.id] = true;
            }
        }
    }

    async toggleDropdown(ev) {
        ev.stopPropagation();
        if (this.props.readonly) {
            const parent = this.props.record._parentRecord;
            const list = ["balance_line_ids", "income_line_ids"]
                .map((name) => parent?.data[name])
                .find((value) => value?.records?.some((record) => record.id === this.props.record.id));
            if (!list || this.props.record.data.row_type === "category") return;
            const record = list.records.find((item) => item.id === this.props.record.id);
            if (!(await list.enterEditMode(record))) return;
        }
        if (!this.root.el) return;
        this.state.open = !this.state.open;
        if (!this.state.open) return;
        const box = this.root.el.getBoundingClientRect();
        this.state.style = `position:fixed;top:${Math.min(box.bottom + 4, window.innerHeight - 340)}px;left:${Math.max(8, Math.min(box.left, window.innerWidth - 380))}px`;
        if (this.state.nodes.length) return;
        this.state.loading = true;
        try {
            this.state.nodes = await this.orm.call(
                "budget.financial.statement.line", "account_tree", [this.companyId, this.props.record.data.section]);
        } catch (error) {
            this.notification.add("بارگذاری گروه‌بندی حساب معین ممکن نشد.", {type: "danger"});
            this.state.open = false;
        } finally {
            this.state.loading = false;
        }
    }

    async toggleNode(node) {
        const id = node.id;
        this.state.expanded[id] = !this.state.expanded[id];
        if (!this.state.expanded[id] || this.state.members[id]) return;
        try {
            this.state.members[id] = await this.orm.call(
                "budget.financial.statement.line", "account_members", [id, node.company_id, this.props.record.data.section]);
        } catch (error) {
            this.notification.add("دریافت حساب‌های زیرگروه ممکن نشد.", {type: "danger"});
            this.state.expanded[id] = false;
        }
    }

    async selectMember(node, member) {
        await this.props.record.update({
            title: member.title,
            category_id: {id: node.id, display_name: node.title},
            member_id: member.id,
            row_type: "member",
        });
        this.state.open = false;
    }
}

registry.category("fields").add("financial_account_tree", {
    component: FinancialAccountTree,
    supportedTypes: ["char"],
});
