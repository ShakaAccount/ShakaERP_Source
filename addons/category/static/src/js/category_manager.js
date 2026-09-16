/** @odoo-module **/
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Component, useState, onWillStart} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";

const PAGE_SIZE = 20;

// ---------- Recursive tree node ----------
export class CategoryNode extends Component {
    get hasChildren() {
        return !!(this.props.children && this.props.children.length);
    }

    get isSelected() {
        return this.props.selectedId === this.props.category.id;
    }

    get isOpen() {
        return !!this.props.expandedIds[this.props.category.id];
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

    onAddChild(ev) {
        ev.stopPropagation();
        this.props.onAddChild(this.props.category);
    }

    onRemove(ev) {
        ev.stopPropagation();
        this.props.onDelete(this.props.category);
    }
}

CategoryNode.template = "category.CategoryNode";
CategoryNode.props = {
    category: Object,
    children: {type: Array, optional: true},
    selectedId: {type: Number, optional: true},
    expandedIds: Object,
    closingIds: Object,          // <-- new
    onSelect: Function,
    onToggle: Function,
    onAddChild: Function,
    onDelete: Function,          // <-- new
    getChildren: Function,
    level: Number,
};
CategoryNode.components = {CategoryNode};

// ---------- Main component ----------
export class CategoryManager extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.pageSize = PAGE_SIZE;

        this.state = useState({
            tree: [],
            treeByParent: {},
            loading: true,
            selectedCategory: null,
            expandedIds: {},
            closingIds: {},
            left: this._blankSide(),
            right: this._blankSide(),
            showNewCategory: false,
            newCategory: {title: "", code: "", entity_id: null},
            saving: false,
            entityColumns: [],
            labelColumn: "",
        });

        // Bound once so they are stable references across re-renders.
        this.getChildren = (cat) => this.state.treeByParent[cat.id] || [];
        this.onSelect = (cat) => this.selectCategory(cat);
        this.onToggle = (id) => this.toggleExpand(id);
        this.onAddChild = (cat) => this.openNewCategory(cat);
        this.onDelete = (cat) => this.confirmDeleteCategory(cat);

        onWillStart(async () => {
            await this.reloadTree();
        });
    }

    _blankSide() {
        return {
            records: [],
            total: 0,
            page: 1,
            search: "",
            reason: null,
            selectedIds: {},   // {id: true}
            anchorIndex: null, // for shift-click range
        };
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

    get rootNodes() {
        return this.state.treeByParent[0] || [];
    }

    toggleExpand(id) {
        const isOpen = !!this.state.expandedIds[id];
        const isClosing = !!this.state.closingIds[id];
        if (!isOpen) {
            // Opening: show immediately, clear any stale closing flag.
            this.state.expandedIds[id] = true;
            if (this.state.closingIds[id]) {
                delete this.state.closingIds[id];
            }
        } else if (!isClosing) {
            // Closing: mark, wait for the animation, then unmount.
            this.state.closingIds[id] = true;
            setTimeout(() => {
                delete this.state.expandedIds[id];
                delete this.state.closingIds[id];
            }, 200);
        }
    }

    async selectCategory(cat) {
        this.state.selectedCategory = cat;
        for (const side of ["left", "right"]) {
            this.state[side].page = 1;
            this.state[side].search = "";
            this.state[side].selectedIds = {};
            this.state[side].anchorIndex = null;
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

    // ---------- Label column picker ----------
    _labelStorageKey(entityId) {
        return `category_manager.label.${entityId}`;
    }

    refreshLabelOptions() {
        const rec = this.state.right.records[0] || this.state.left.records[0];
        if (!rec) {
            this.state.entityColumns = [];
            return;
        }
        const skip = new Set(["id", "_pk", "label", "_auto_label"]);
        this.state.entityColumns = Object.keys(rec)
            .filter(k => !skip.has(k))
            .map(k => ({name: k, title: k}));
    }

    onLabelColumnChange(ev) {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            return;
        }
        const entityId = cat.entity_id[0];
        const column = ev.target.value || "";
        this.state.labelColumn = column;
        try {
            if (column) {
                localStorage.setItem(this._labelStorageKey(entityId), column);
            } else {
                localStorage.removeItem(this._labelStorageKey(entityId));
            }
        } catch (e) { /* ignore */
        }

        this.state.left.records =
            this.state.left.records.map(r => this.applyLabel(r));
        this.state.right.records =
            this.state.right.records.map(r => this.applyLabel(r));
    }

    applyLabel(record) {
        const col = this.state.labelColumn;
        if (!col) {
            return {...record, label: record._auto_label ?? record.label};
        }
        const val = record[col];
        if (val === undefined || val === null || val === "") {
            return record;
        }
        return {...record, label: String(val)};
    }

    // ---------- Fetch ----------
    async fetchPane(sideName, method) {
        const side = this.state[sideName];
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            side.records = [];
            side.total = 0;
            side.selectedIds = {};
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
            side.records = (res.records || []).map(r => {
                r._auto_label = r.label;
                return this.applyLabel(r);
            });
            side.total = res.total || 0;
            side.reason = res.reason || null;
            // Clear selections on reload to avoid stale ids.
            side.selectedIds = {};
            side.anchorIndex = null;
            this.refreshLabelOptions();
        } catch (e) {
            console.error(`${method} failed`, e);
            side.records = [];
            side.total = 0;
            side.selectedIds = {};
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

    // ---------- Selection helpers ----------
    isRowSelected(sideName, rec) {
        return !!this.state[sideName].selectedIds[rec.id];
    }

    selectedCount(sideName) {
        return Object.keys(this.state[sideName].selectedIds).length;
    }

    selectedRecords(sideName) {
        const side = this.state[sideName];
        return side.records.filter(r => side.selectedIds[r.id]);
    }

    clearSelection(sideName) {
        const side = this.state[sideName];
        side.selectedIds = {};
        side.anchorIndex = null;
    }

    toggleRow(sideName, rec, ev) {
        const side = this.state[sideName];
        const idx = side.records.findIndex(r => r.id === rec.id);
        const shift = ev && ev.shiftKey;
        const multi = ev && (ev.ctrlKey || ev.metaKey);

        if (shift && side.anchorIndex !== null) {
            const [a, b] = [side.anchorIndex, idx].sort((x, y) => x - y);
            const next = {...side.selectedIds};
            for (let i = a; i <= b; i++) {
                const r = side.records[i];
                if (r) {
                    next[r.id] = true;
                }
            }
            side.selectedIds = next;
        } else if (multi) {
            const next = {...side.selectedIds};
            if (next[rec.id]) {
                delete next[rec.id];
            } else {
                next[rec.id] = true;
            }
            side.selectedIds = next;
            side.anchorIndex = idx;
        } else {
            // plain click: toggle this one only
            if (side.selectedIds[rec.id] && this.selectedCount(sideName) === 1) {
                side.selectedIds = {};
            } else {
                side.selectedIds = {[rec.id]: true};
            }
            side.anchorIndex = idx;
        }
    }

    selectAllOnPage(sideName) {
        const side = this.state[sideName];
        const next = {};
        for (const r of side.records) {
            next[r.id] = true;
        }
        side.selectedIds = next;
    }

    invertSelection(sideName) {
        const side = this.state[sideName];
        const next = {};
        for (const r of side.records) {
            if (!side.selectedIds[r.id]) {
                next[r.id] = true;
            }
        }
        side.selectedIds = next;
    }

    // ---------- Bulk move ----------
    async bulkAddSelected() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            return;
        }
        const recs = this.selectedRecords("left");
        if (!recs.length) {
            return;
        }
        const vals = recs.map(r => ({
            category_id: cat.id,
            member_id: r.id,
            entity_id: cat.entity_id[0],
        }));
        try {
            await this.orm.create("raes.md.category.member", vals);
            await this.reloadPanes();
            this.notification.add(
                `Added ${vals.length} item(s) to the category.`,
                {type: "success"});
        } catch (e) {
            console.error("bulk add failed", e);
            this.notification.add(
                "Could not add all selected records. Some may already be in the category.",
                {type: "danger"});
        }
    }

    async bulkRemoveSelected() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            return;
        }
        const recs = this.selectedRecords("right");
        if (!recs.length) {
            return;
        }
        const memberIds = recs.map(r => r.id);
        try {
            const members = await this.orm.searchRead(
                "raes.md.category.member",
                [["category_id", "=", cat.id],
                    ["member_id", "in", memberIds],
                    ["entity_id", "=", cat.entity_id[0]]],
                ["id"]);
            if (members.length) {
                await this.orm.unlink(
                    "raes.md.category.member", members.map(m => m.id));
            }
            await this.reloadPanes();
            this.notification.add(
                `Removed ${members.length} item(s) from the category.`,
                {type: "success"});
        } catch (e) {
            console.error("bulk remove failed", e);
            this.notification.add(
                "Could not remove all selected records.", {type: "danger"});
        }
    }

    // ---------- Single actions ----------
    async addToCategory(record) {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            return;
        }
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
            console.error("create member failed", e);
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
                ["id"]);
            if (!members.length) {
                this.notification.add(
                    "This record is no longer in the category.",
                    {type: "warning"});
                await this.reloadPanes();
                return;
            }
            await this.orm.unlink(
                "raes.md.category.member", members.map(m => m.id));
            await this.reloadPanes();
        } catch (e) {
            console.error("unlink member failed", e);
            this.notification.add(
                "Could not remove the record.", {type: "danger"});
        }
    }

    // ---------- Search + pagination ----------
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
    openNewCategory(parentCat) {
        const parent = parentCat || this.state.selectedCategory;
        const nested = !!parentCat;
        this.state.newCategory = {
            title: "",
            code: "",
            parent_id: nested ? parent.id : null,
            parent_title: nested ? parent.title : null,
            entity_id: parent && parent.entity_id ? parent.entity_id[0] : null,
        };
        if (nested) {
            this.state.expandedIds[parentCat.id] = true;
        }
        this.state.showNewCategory = true;
    }

    confirmDeleteCategory(cat) {
        this.dialog.add(ConfirmationDialog, {
            title: "Delete category",
            body:
                `Delete "${cat.title}" and every sub-category under it?\n\n` +
                `This also removes all item assignments to those categories. ` +
                `This action cannot be undone.`,
            confirmLabel: "Delete",
            confirm: () => this._deleteCategory(cat),
            cancel: () => {
            },
        });
    }

    async _deleteCategory(cat) {
        try {
            await this.orm.unlink("raes.md.category", [cat.id]);

            // If the selected category was part of the removed subtree,
            // clear the panes.
            const stillThere = new Set(this.state.tree.map(c => c.id));
            await this.reloadTree();
            const remaining = new Set(this.state.tree.map(c => c.id));
            if (
                this.state.selectedCategory &&
                !remaining.has(this.state.selectedCategory.id)
            ) {
                this.state.selectedCategory = null;
                this.state.left = this._blankSide();
                this.state.right = this._blankSide();
            }
            // Clean up expansion state for removed nodes.
            for (const id of Object.keys(this.state.expandedIds)) {
                if (!remaining.has(Number(id))) {
                    delete this.state.expandedIds[id];
                }
            }

            this.notification.add(
                `Category "${cat.title}" and its sub-categories were deleted.`,
                {type: "success"});
        } catch (e) {
            console.error("delete category failed", e);
            this.notification.add(
                "Could not delete the category. See the browser console for details.",
                {type: "danger"});
        }
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
                "An entity is required — select a category first.",
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
            console.error("create category failed", e);
            this.notification.add(
                "Could not create the category. A sub-category must belong " +
                "to the same entity as its tree root.",
                {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    // ---------- Misc ----------
    recordLabel(record) {
        return record.label || record.title || record.name ||
            record.englishtitle || record.english_title || `#${record.id}`;
    }

    reasonMessage(reason) {
        const sel = this.state.selectedCategory;
        const table = sel && sel.entity_id ? sel.entity_id[1] : "this entity";
        switch (reason) {
            case "no-connection":
                return `No SQL Server connection is configured for "${table}".`;
            case "no-table":
                return `Entity "${table}" has no schema/table set.`;
            case "no-pk":
                return `No primary key column could be resolved for "${table}".`;
            case "no-entity":
                return `This category has no entity assigned.`;
            case "no-entity-record":
                return `The entity assigned to this category no longer exists.`;
            case "connection-error":
                return `Could not reach the SQL Server for "${table}".`;
            case "rpc-error":
                return `The data-warehouse query failed — see the browser console.`;
            default:
                return "";
        }
    }
}

CategoryManager.template = "category.CategoryManager";
CategoryManager.components = {CategoryNode};

registry.category("actions").add(
    "category.category_manager", CategoryManager);