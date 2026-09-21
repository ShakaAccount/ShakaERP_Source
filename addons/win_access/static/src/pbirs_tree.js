import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Many2many of win.access.option (kind=pbirs) shown as a collapsible folder tree with checkboxes. */
export class PbirsTreeField extends Component {
    static template = "win_access.PbirsTree";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ open: {} });
        onWillStart(async () => {
            const recs = await this.orm.searchRead(
                "win.access.option", [["kind", "=", "pbirs"]], ["path", "item_type"], { order: "path" });
            const paths = new Set(recs.map((r) => r.path));
            this.children = { root: [] };
            this.parentOf = {};
            for (const r of recs) {
                const parent = r.path.slice(0, r.path.lastIndexOf("/"));
                const key = parent && paths.has(parent) ? parent : "root";
                (this.children[key] ||= []).push(r);
                this.parentOf[r.path] = key;
            }
            this.byPath = Object.fromEntries(recs.map((r) => [r.path, r]));
            // open the ancestors of what is already selected
            for (const id of this.selected) {
                let p = recs.find((r) => r.id === id)?.path;
                while (p && (p = this.parentOf[p]) && p !== "root") {
                    this.state.open[p] = true;
                }
            }
        });
    }

    get selected() {
        return this.props.record.data[this.props.name].currentIds;
    }

    get rows() {
        const rows = [];
        const walk = (key, depth) => {
            for (const r of this.children[key] || []) {
                const hasChildren = !!this.children[r.path];
                rows.push({
                    id: r.id, path: r.path, depth, hasChildren,
                    label: r.path.slice(r.path.lastIndexOf("/") + 1) || r.path,
                    type: r.item_type,
                    icon: hasChildren || r.item_type === "Folder" ? "fa-folder-o" : "fa-bar-chart",
                });
                if (hasChildren && this.state.open[r.path]) {
                    walk(r.path, depth + 1);
                }
            }
        };
        walk("root", 0);
        return rows;
    }

    isOpen(row) {
        return !!this.state.open[row.path];
    }

    toggle(row) {
        this.state.open[row.path] = !this.state.open[row.path];
    }

    onCheck(row, checked) {
        this.props.record.data[this.props.name].addAndRemove(
            checked ? { add: [row.id] } : { remove: [row.id] });
    }
}

registry.category("fields").add("win_access_tree", {
    component: PbirsTreeField,
    supportedTypes: ["many2many"],
});
