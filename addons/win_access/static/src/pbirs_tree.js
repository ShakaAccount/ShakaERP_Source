import { Component, onWillStart, onWillUnmount, onWillUpdateProps, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Many2many of win.access.option (kind=pbirs) as a folder tree.
 * Ticking a folder ticks everything under it (each item is stored, so each gets its own policy call).
 * Descendants come from an exact parent -> children map, never from a path prefix: "/A B" is a
 * sibling of "/A", not a child.
 */
export class PbirsTreeField extends Component {
    static template = "win_access.PbirsTree";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.root = useRef("root");
        this.state = useState({ open: {}, query: "", selected: {} });
        // Batch changes like core's many2many_checkboxes so a click right before Save is not lost.
        this.idsToAdd = new Set();
        this.idsToRemove = new Set();
        this.debouncedCommit = debounce(this.commitChanges.bind(this), 500);
        useBus(this.props.record.model.bus, "NEED_LOCAL_CHANGES", this.commitChanges.bind(this));
        onWillUnmount(this.commitChanges.bind(this));
        onWillUpdateProps((next) => {
            if (!this.idsToAdd.size && !this.idsToRemove.size) {
                this.seed(next.record.data[next.name].currentIds);
            }
        });
        onWillStart(async () => {
            const recs = await this.orm.searchRead(
                "win.access.option", [["kind", "=", "pbirs"]], ["path", "item_type"], { order: "path" });
            const paths = new Set(recs.map((r) => r.path));
            this.children = {};
            this.parentOf = {};
            for (const r of recs) {
                const parent = r.path.slice(0, r.path.lastIndexOf("/"));
                const key = parent && paths.has(parent) ? parent : "root";
                (this.children[key] ||= []).push(r);
                this.parentOf[r.path] = key;
            }
            this.recs = recs;
            this.desc = {};
            const walk = (r) => {
                const out = [];
                for (const c of this.children[r.path] || []) {
                    out.push(c.id, ...walk(c));
                }
                return (this.desc[r.id] = out);
            };
            recs.forEach(walk);
            this.seed(this.props.record.data[this.props.name].currentIds);
            for (const r of recs) {
                if (this.state.selected[r.id]) {
                    let p = r.path;
                    while ((p = this.parentOf[p]) && p !== "root") {
                        this.state.open[p] = true;
                    }
                }
            }
        });
        // <input indeterminate> is a DOM property, not an attribute
        useEffect(() => {
            this.root.el?.querySelectorAll("input[data-tri]").forEach((el) => {
                el.indeterminate = el.dataset.tri === "1";
            });
        });
    }

    seed(ids) {
        this.state.selected = Object.fromEntries(ids.map((id) => [id, true]));
    }

    get total() {
        return this.recs.length;
    }

    get count() {
        return this.recs.filter((r) => this.state.selected[r.id]).length;
    }

    get rows() {
        const q = this.state.query.trim().toLowerCase();
        const match = q ? new Set(this.recs.filter((r) => r.path.toLowerCase().includes(q)).map((r) => r.id)) : null;
        const shown = (r) => !match || match.has(r.id) || this.desc[r.id].some((id) => match.has(id));
        const rows = [];
        const walk = (key, depth) => {
            for (const r of this.children[key] || []) {
                if (!shown(r)) {
                    continue;
                }
                const hasChildren = !!this.children[r.path];
                const ids = [r.id, ...this.desc[r.id]];
                const n = ids.filter((id) => this.state.selected[id]).length;
                rows.push({
                    id: r.id, path: r.path, depth, hasChildren,
                    label: r.path.slice(r.path.lastIndexOf("/") + 1) || r.path,
                    type: r.item_type,
                    icon: hasChildren || r.item_type === "Folder" ? "fa-folder-o" : "fa-bar-chart",
                    checked: n === ids.length,
                    partial: n > 0 && n < ids.length,
                    open: hasChildren && (!!match || !!this.state.open[r.path]),
                });
                if (hasChildren && (match || this.state.open[r.path])) {
                    walk(r.path, depth + 1);
                }
            }
        };
        walk("root", 0);
        return rows;
    }

    toggle(row) {
        this.state.open[row.path] = !this.state.open[row.path];
    }

    expandAll(open) {
        this.state.open = open
            ? Object.fromEntries(this.recs.filter((r) => this.children[r.path]).map((r) => [r.path, true]))
            : {};
    }

    onCheck(row, checked) {
        for (const id of [row.id, ...this.desc[row.id]]) {
            if (!!this.state.selected[id] === checked) {
                continue;
            }
            this.state.selected[id] = checked;
            const [cancel, queue] = checked ? [this.idsToRemove, this.idsToAdd] : [this.idsToAdd, this.idsToRemove];
            if (!cancel.delete(id)) {
                queue.add(id);
            }
        }
        this.debouncedCommit();
    }

    commitChanges() {
        if (!this.idsToAdd.size && !this.idsToRemove.size) {
            return;
        }
        const res = this.props.record.data[this.props.name].addAndRemove({
            add: [...this.idsToAdd],
            remove: [...this.idsToRemove],
        });
        this.idsToAdd.clear();
        this.idsToRemove.clear();
        return res;
    }
}

registry.category("fields").add("win_access_tree", {
    component: PbirsTreeField,
    supportedTypes: ["many2many"],
});
