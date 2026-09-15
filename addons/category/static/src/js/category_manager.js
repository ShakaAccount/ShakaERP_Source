/** @odoo-module **/
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Component, useState, onWillStart} from "@odoo/owl";

const PAGE_SIZE = 20;

// ---------- Recursive Tree Node ----------
export class CategoryNode extends Component {
    get hasChildren() {
        return !!(this.props.children && this.props.children.length);
    }

    get isSelected() {
        return this.props.selectedId === this.props.category.id;
    }

    onClick(ev) {
        ev.stopPropagation();
        this.props.onSelect(this.props.category);
    }

    onToggle(ev) {
        ev.stopPropagation();
        if (this.hasChildren) {
            this.props.onToggle(this.props.category.id);
        }
    }

    /** Create a sub-category nested under this node. */
    onAddChild(ev) {
        ev.stopPropagation();
        this.props.onAddChild(this.props.category);
    }
}

CategoryNode.template = "category.CategoryNode";
CategoryNode.props = {
    category: Object,
    children: {type: Array, optional: true},
    selectedId: {type: Number, optional: true},
    expandedIds: Object,
    onSelect: Function,
    onToggle: Function,
    onAddChild: Function,
    getChildren: Function,
    level: Number,
};
// Recursive components must be registered on themselves so the template
// can reference <CategoryNode> while rendering a CategoryNode.
CategoryNode.components = {CategoryNode};


// ---------- Main Component ----------
export class CategoryManager extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.pageSize = PAGE_SIZE;

        this.state = useState({
            tree: [],
            treeByParent: {},
            loading: true,
            selectedCategory: null,
            expandedIds: {},
            left: {records: [], total: 0, page: 1, search: "", reason: null},
            right: {records: [], total: 0, page: 1, search: "", reason: null},
            showNewCategory: false,
            newCategory: {title: "", code: "", entity_id: null},
            saving: false,
            entityColumns: [],       // <-- ADD THIS BACK
            labelColumn: "",         // currently-selected label column
        });

        // Bound once so they are stable references across re-renders; the
        // templates hand them down to every recursive node.
        this.getChildren = (cat) => this.state.treeByParent[cat.id] || [];
        this.onSelect = (cat) => this.selectCategory(cat);
        this.onToggle = (id) => this.toggleExpand(id);
        this.onAddChild = (cat) => this.openNewCategory(cat);

        onWillStart(async () => {
            await this.reloadTree();
        });
    }

    _labelStorageKey(entityId) {
        return `category_manager.label.${entityId}`;
    }

    /** Rebuild the column list from the currently-loaded records. */
    refreshLabelOptions() {
        const rec = (this.state.right.records[0] || this.state.left.records[0]);
        if (!rec) return;
        // Keys the DW record carries, minus our own metadata fields.
        this.state.entityColumns = Object.keys(rec)
            .filter(k => !["id", "_pk", "label"].includes(k))
            .map(k => ({name: k, title: k}));
    }


    // ---------- Tree ----------
    async reloadTree() {
        try {
            const flat = await this.orm.call(
                "raes.md.entity", "get_category_tree", []);
            const byParent = {};
            for (const c of flat) {
                const key = c.parent_id ? c.parent_id[0] : 0;
                (byParent[key] = byParent[key] || []).push(c);
            }
            for (const k of Object.keys(byParent)) {
                byParent[k].sort((a, b) =>
                    (a.title || "").localeCompare(b.title || ""));
            }
            this.state.tree = flat;
            this.state.treeByParent = byParent;
        } catch (e) {
            console.error("get_category_tree failed", e);
            this.notification.add(
                "Could not load the category tree.", {type: "danger"});
        } finally {
            this.state.loading = false;
        }
    }


    async onLabelColumnChange(ev) {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) return;
        const entityId = cat.entity_id[0];
        const column = ev.target.value || false;
        this.state.labelColumn = column;
        try {
            await this.orm.call(
                "raes.md.entity", "set_entity_label_column",
                [entityId, column]);
            await this.reloadPanes();
        } catch (e) {
            console.error("set_entity_label_column failed", e);
            this.notification.add(
                "Could not save the label column.", {type: "danger"});
        }
    }

    get rootNodes() {
        return this.state.treeByParent[0] || [];
    }

    toggleExpand(id) {
        this.state.expandedIds[id] = !this.state.expandedIds[id];
    }

    async selectCategory(cat) {
        this.state.selectedCategory = cat;
        for (const side of ["left", "right"]) {
            this.state[side].page = 1;
            this.state[side].search = "";
        }
        this.state.labelColumn = "";
        if (cat && cat.entity_id) {
            try {
                this.state.labelColumn =
                    localStorage.getItem(this._labelStorageKey(cat.entity_id[0])) || "";
            } catch (e) { /* ignore */
            }
        }
        await this.reloadPanes();
    }

    async reloadPanes() {
        await Promise.all([this.loadLeft(), this.loadRight()]);
    }

    /** Override record.label with the user's chosen column, if set. */
    applyLabel(record) {
        const col = this.state.labelColumn;
        if (!col) return record;
        const val = record[col];
        if (val === undefined || val === null || val === "") return record;
        return {...record, label: String(val)};
    }

    // ---------- DW item lists ----------
    /**
     * Fetch one pane. `entity_id` is mandatory: without it there is no DW
     * table to read from, so bail out early rather than issue an RPC that
     * can only fail.
     */
    async fetchPane(sideName, method) {
        const side = this.state[sideName];
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            side.records = [];
            side.total = 0;
            side.reason = cat ? "no-entity" : null;
            return;
        }
        const entityId = cat.entity_id[0];
        try {
            const res = await this.orm.call("raes.md.entity", method, [
                entityId,
                cat.id,
                (side.page - 1) * this.pageSize,
                this.pageSize,
                side.search || "",
            ]);
            side.records = (res.records || []).map(r => this.applyLabel(r));
            side.total = res.total || 0;
            side.reason = res.reason || null;
            this.refreshLabelOptions();
        } catch (e) {
            console.error(`${method} failed`, e);
            side.records = [];
            side.total = 0;
            side.reason = "rpc-error";
            this.notification.add("Could not load DW items.", {type: "danger"});
        }
    }

    loadLeft() {
        return this.fetchPane("left", "get_items_not_in_category");
    }

    loadRight() {
        return this.fetchPane("right", "get_items_in_category");
    }

    /** Explain an empty pane caused by an unresolved DW relation. */
    reasonMessage(reason) {
        const sel = this.state.selectedCategory;
        const table = sel && sel.entity_id ? sel.entity_id[1] : "this entity";
        switch (reason) {
            case "no-connection":
                return `No SQL Server connection is configured for "${table}". ` +
                    `Set one on the entity's configuration to link items.`;
            case "no-table":
                return `Entity "${table}" has no schema/table set.`;
            case "no-pk":
                return `No primary key column could be resolved for "${table}".`;
            case "no-entity":
                return `This category has no entity assigned.`;
            case "no-entity-record":
                return `The entity assigned to this category no longer exists.`;
            case "connection-error":
                return `Could not reach the SQL Server for "${table}" — check ` +
                    `the connection settings and the browser console.`;
            case "rpc-error":
                return `The data-warehouse query failed — see the browser console.`;
            default:
                return "";
        }
    }

    // ---------- Add / remove ----------
    async addToCategory(record) {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            return;
        }
        // `record.id` is the DW primary key, normalised server-side by
        // _dw_normalize_record (the raw DW column is e.g. `partyid`).
        // Posting an undefined id would violate the NOT NULL on
        // md.category_member.member_id.
        if (record.id === undefined || record.id === null) {
            this.notification.add(
                "This DW row has no primary key; cannot add it.",
                {type: "warning"});
            return;
        }
        try {
            await this.orm.create("raes.md.category.member", [{
                category_id: cat.id,
                member_id: record.id,
                entity_id: cat.entity_id[0],
            }]);
            await this.reloadPanes();
        } catch (e) {
            console.error("create raes.md.category.member failed", e);
            this.notification.add(
                "Could not add the record. It may already be in this category.",
                {type: "danger"});
        }
    }

    async removeFromCategory(record) {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            return;
        }
        try {
            const members = await this.orm.searchRead(
                "raes.md.category.member",
                [["category_id", "=", cat.id],
                    ["member_id", "=", record.id],
                    ["entity_id", "=", cat.entity_id[0]]],
                ["id"],
            );
            if (!members.length) {
                this.notification.add(
                    "This record is no longer in the category.",
                    {type: "warning"});
                await this.reloadPanes();
                return;
            }
            await this.orm.unlink(
                "raes.md.category.member", members.map((m) => m.id));
            await this.reloadPanes();
        } catch (e) {
            console.error("unlink raes.md.category.member failed", e);
            this.notification.add(
                "Could not remove the record.", {type: "danger"});
        }
    }

    onSearchLeft(ev) {
        this.state.left.search = ev.target.value;
        this.state.left.page = 1;
        this.loadLeft();
    }

    onSearchRight(ev) {
        this.state.right.search = ev.target.value;
        this.state.right.page = 1;
        this.loadRight();
    }

    get leftPages() {
        return Math.max(1, Math.ceil(this.state.left.total / this.pageSize));
    }

    get rightPages() {
        return Math.max(1, Math.ceil(this.state.right.total / this.pageSize));
    }

    async nextLeft() {
        if (this.state.left.page < this.leftPages) {
            this.state.left.page++;
            await this.loadLeft();
        }
    }

    async prevLeft() {
        if (this.state.left.page > 1) {
            this.state.left.page--;
            await this.loadLeft();
        }
    }

    async nextRight() {
        if (this.state.right.page < this.rightPages) {
            this.state.right.page++;
            await this.loadRight();
        }
    }

    async prevRight() {
        if (this.state.right.page > 1) {
            this.state.right.page--;
            await this.loadRight();
        }
    }

    // ---------- New category ----------
    /**
     * Open the create modal.
     *
     * `parentCat` is set when the user clicks the `+` on a tree node, in
     * which case the new category is nested under it and inherits its
     * entity (md.category_same_entity() requires a child to share its
     * tree root's entity_id, so this must not be freely editable).
     */
    openNewCategory(parentCat) {
        const parent = parentCat || this.state.selectedCategory;
        const nested = !!parentCat;
        this.state.newCategory = {
            title: "",
            code: "",
            parent_id: nested ? parent.id : null,
            parent_title: nested ? parent.title : null,
            // The entity is fixed to the tree root's entity when nested:
            // the legacy trigger rejects a mismatching child.
            entity_id: parent && parent.entity_id ? parent.entity_id[0] : null,
        };
        // Auto-expand the parent so the new child is immediately visible.
        if (nested) {
            this.state.expandedIds[parentCat.id] = true;
        }
        this.state.showNewCategory = true;
    }

    cancelNewCategory() {
        this.state.showNewCategory = false;
    }

    async saveNewCategory() {
        const nc = this.state.newCategory;
        if (!nc.title) {
            this.notification.add("Title is required.", {type: "warning"});
            return;
        }
        if (!nc.entity_id) {
            this.notification.add(
                "An entity is required — select a category first, or type an entity id.",
                {type: "warning"});
            return;
        }
        this.state.saving = true;
        try {
            const vals = {
                title: nc.title,
                code: nc.code || false,
                entity_id: nc.entity_id,
            };
            if (nc.parent_id) {
                vals.parent_id = nc.parent_id;
            }
            await this.orm.create("raes.md.category", [vals]);
            this.state.showNewCategory = false;
            await this.reloadTree();
            if (nc.parent_id) {
                this.state.expandedIds[nc.parent_id] = true;
            }
            this.notification.add(
                nc.parent_id
                    ? `Sub-category created under "${nc.parent_title}".`
                    : "Root category created.",
                {type: "success"});
        } catch (e) {
            console.error("create raes.md.category failed", e);
            this.notification.add(
                "Could not create the category. A sub-category must belong " +
                "to the same entity as its tree root.",
                {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    // ---------- View helpers ----------
    /** Server computes `label`; keep a fallback for safety. */
    recordLabel(record) {
        return record.label || record.title || record.name ||
            record.englishtitle || record.english_title || `#${record.id}`;
    }
}

CategoryManager.template = "category.CategoryManager";
CategoryManager.components = {CategoryNode};

registry.category("actions").add(
    "category.category_manager", CategoryManager);