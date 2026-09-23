import { Component, onWillStart, onWillUnmount, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { TreeNode } from "@shaka_ui_kit/js/tree_node";

/**
 * Many2many of win.access.option (kind=pbirs) as a folder tree.
 * Ticking a folder ticks everything under it (each item is stored, so each gets its own policy call).
 * Descendants come from an exact parent -> children map, never from a path prefix: "/A B" is a
 * sibling of "/A", not a child.
 */
export class PbirsTreeField extends Component {
    static template = "win_access.PbirsTree";
    static components = { TreeNode };
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.root = useRef("root");
        this.state = useState({ open: {}, closing: {}, query: "", selected: {} });
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
            this.idByPath = {};
            for (const r of recs) {
                const parent = r.path.slice(0, r.path.lastIndexOf("/"));
                const key = parent && paths.has(parent) ? parent : "root";
                (this.children[key] ||= []).push(r);
                this.parentOf[r.path] = key;
                this.idByPath[r.path] = r.id;
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
                        this.state.open[this.idByPath[p]] = true;
                    }
                }
            }
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

    get _query() {
        return this.state.query.trim().toLowerCase();
    }

    get _matchIds() {
        const q = this._query;
        if (!q) return null;
        return new Set(this.recs.filter((r) => r.path.toLowerCase().includes(q)).map((r) => r.id));
    }

    _shown(rec) {
        const match = this._matchIds;
        return !match || match.has(rec.id) || this.desc[rec.id].some((id) => match.has(id));
    }

    toNode(rec) {
        return {
            id: rec.id,
            path: rec.path,
            label: rec.path.slice(rec.path.lastIndexOf("/") + 1) || rec.path,
            item_type: rec.item_type,
            hasChildren: !!this.children[rec.path],
        };
    }

    // Bound arrow: passed as a bare prop reference to TreeNode, which calls
    // it detached from `this` (unlike a template expression like
    // `this.rootNodes`, which keeps its receiver).
    getChildren = (node) => {
        return (this.children[node.path] || []).filter((r) => this._shown(r)).map((r) => this.toNode(r));
    };

    get rootNodes() {
        return (this.children.root || []).filter((r) => this._shown(r)).map((r) => this.toNode(r));
    }

    // While searching, every folder auto-expands so matches surface regardless
    // of manual expand/collapse state; `getChildren`'s `_shown` filter still
    // hides branches with no match.
    get effectiveOpen() {
        if (!this._matchIds) return this.state.open;
        const merged = { ...this.state.open };
        for (const r of this.recs) {
            if (this.children[r.path]) merged[r.id] = true;
        }
        return merged;
    }

    toggleNode(id) {
        const isOpen = !!this.state.open[id];
        const isClosing = !!this.state.closing[id];
        if (!isOpen) {
            this.state.open[id] = true;
            if (this.state.closing[id]) {
                delete this.state.closing[id];
            }
        } else if (!isClosing) {
            this.state.closing[id] = true;
            setTimeout(() => {
                delete this.state.open[id];
                delete this.state.closing[id];
            }, 220);
        }
    }

    expandAll(open) {
        this.state.open = open
            ? Object.fromEntries(this.recs.filter((r) => this.children[r.path]).map((r) => [r.id, true]))
            : {};
        this.state.closing = {};
    }

    checkState = (node) => {
        const ids = [node.id, ...this.desc[node.id]];
        const n = ids.filter((id) => this.state.selected[id]).length;
        if (n === 0) return "unchecked";
        return n === ids.length ? "checked" : "partial";
    };

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
