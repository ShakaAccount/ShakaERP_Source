/** @odoo-module **/
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Component, useState, onWillStart, useRef, useExternalListener} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";

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
    closingIds: Object,
    onSelect: Function,
    onToggle: Function,
    onAddChild: Function,
    onDelete: Function,
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
        this.bus = useService("bus_service");
        this.bus.subscribe("COMPANY_CHANGED", () => this.onCompanyChanged());

        this.labelPickerRef = useRef("labelPicker");

        useExternalListener(document, "click", (ev) => {
            if (!this.state.showLabelPicker) return;
            const el = this.labelPickerRef.el;
            if (el && !el.contains(ev.target)) {
                this.state.showLabelPicker = false;
            }
        });

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
            labelColumns: [],
            showLabelPicker: false,
            pageSize: 20,
        });

        try {
            const saved = parseInt(
                localStorage.getItem(this._pageSizeStorageKey()), 10);
            if (saved > 0) {
                this.state.pageSize = saved;
            }
        } catch (e) { /* ignore */
        }

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
            selectedIds: {},
            anchorIndex: null,
        };
    }

    async onCompanyChanged() {
        await this.reloadTree();
        this.state.selectedCategory = null;
        this.state.left = this._blankSide();
        this.state.right = this._blankSide();
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
            this.state.expandedIds[id] = true;
            if (this.state.closingIds[id]) {
                delete this.state.closingIds[id];
            }
        } else if (!isClosing) {
            this.state.closingIds[id] = true;
            setTimeout(() => {
                delete this.state.expandedIds[id];
                delete this.state.closingIds[id];
            }, 220);
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
        this.state.showLabelPicker = false;
        this.state.labelColumns = [];
        if (cat && cat.entity_id) {
            this.state.labelColumns = this._loadLabelColumns(cat.entity_id[0]);
        }
        await this.reloadPanes();
    }

    async reloadPanes() {
        await Promise.all([this.loadLeft(), this.loadRight()]);
    }

    // ---------- Label column picker (multi-select) ----------
    _labelStorageKey(entityId) {
        return `category_manager.label.${entityId}`;
    }

    _loadLabelColumns(entityId) {
        let raw = null;
        try {
            raw = localStorage.getItem(this._labelStorageKey(entityId));
        } catch (e) {
            return [];
        }
        if (!raw) return [];
        if (raw.startsWith("[")) {
            try {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    return parsed.filter(s => typeof s === "string" && s);
                }
            } catch (e) { /* fall through */
            }
            return [];
        }
        return [raw];
    }

    _persistLabelColumns() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) return;
        const entityId = cat.entity_id[0];
        try {
            const cols = this.state.labelColumns;
            if (cols.length) {
                localStorage.setItem(
                    this._labelStorageKey(entityId), JSON.stringify(cols));
            } else {
                localStorage.removeItem(this._labelStorageKey(entityId));
            }
        } catch (e) { /* ignore */
        }
    }

    toggleLabelPicker(ev) {
        if (ev) ev.stopPropagation();
        if (!this.state.selectedCategory || !this.state.entityColumns.length) {
            return;
        }
        this.state.showLabelPicker = !this.state.showLabelPicker;
    }

    isLabelColSelected(name) {
        return this.state.labelColumns.includes(name);
    }

    toggleLabelCol(name, ev) {
        if (ev) ev.stopPropagation();
        const next = new Set(this.state.labelColumns);
        if (next.has(name)) {
            next.delete(name);
        } else {
            next.add(name);
        }
        const order = new Map(
            this.state.entityColumns.map((c, i) => [c.name, i]));
        this.state.labelColumns = Array.from(next)
            .sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
        this._persistLabelColumns();
        this._reapplyLabels();
    }

    clearLabelColumns(ev) {
        if (ev) ev.stopPropagation();
        this.state.labelColumns = [];
        this._persistLabelColumns();
        this._reapplyLabels();
    }

    _reapplyLabels() {
        this.state.left.records =
            this.state.left.records.map(r => this.applyLabel(r));
        this.state.right.records =
            this.state.right.records.map(r => this.applyLabel(r));
    }

    get labelPickerSummary() {
        const n = this.state.labelColumns.length;
        if (n === 0) return "Auto";
        if (n === 1) return this.state.labelColumns[0];
        if (n <= 3) return this.state.labelColumns.join(" · ");
        return `${n} columns`;
    }

    /** Columns to render in the item tables. */
    get tableColumns() {
        const avail = new Set(this.state.entityColumns.map(c => c.name));
        const chosen = this.state.labelColumns.filter(n => avail.has(n));
        if (chosen.length) {
            return this.state.entityColumns.filter(c => chosen.includes(c.name));
        }
        // Auto mode: a single column carrying the server's auto-label.
        return [{name: null, title: "Display name"}];
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

    applyLabel(record) {
        const cols = this.state.labelColumns;
        if (!cols.length) {
            return {...record, label: record._auto_label ?? record.label};
        }
        const parts = [];
        for (const c of cols) {
            const val = record[c];
            if (val !== undefined && val !== null && val !== "") {
                parts.push(String(val));
            }
        }
        if (!parts.length) {
            return {...record, label: record._auto_label ?? record.label};
        }
        return {...record, label: parts.join(" · ")};
    }

    /** Value to render in a table cell for `colName` (null = auto column). */
    cellValue(rec, colName) {
        if (colName === null || colName === undefined) {
            return this.recordLabel(rec);
        }
        const v = rec[colName];
        if (v === null || v === undefined || v === false) {
            return "";
        }
        return String(v);
    }

    _pageSizeStorageKey() {
        return "category_manager.page_size";
    }

    onPageSizeChange(ev) {
        const size = parseInt(ev.target.value, 10) || 20;
        this.state.pageSize = size;
        try {
            localStorage.setItem(this._pageSizeStorageKey(), String(size));
        } catch (e) { /* ignore */
        }
        for (const side of ["left", "right"]) {
            this.state[side].page = 1;
            this.state[side].selectedIds = {};
            this.state[side].anchorIndex = null;
        }
        this.reloadPanes();
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
                (side.page - 1) * this.state.pageSize,
                this.state.pageSize,
                side.search || "",
            ]);
            side.records = (res.records || []).map(r => {
                r._auto_label = r.label;
                return this.applyLabel(r);
            });
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

    // ---------- Selection helpers ----------
    isRowSelected(sideName, rec) {
        return !!this.state[sideName].selectedIds[rec.id];
    }

    selectedCount(sideName) {
        return Object.keys(this.state[sideName].selectedIds).length;
    }

    selectedRecords(sideName) {
        return Object.values(this.state[sideName].selectedIds);
    }

    clearSelection(sideName) {
        const side = this.state[sideName];
        side.selectedIds = {};
        side.anchorIndex = null;
    }

    allOnPageSelected(sideName) {
        const side = this.state[sideName];
        if (!side.records.length) return false;
        return side.records.every(r => !!side.selectedIds[r.id]);
    }

    toggleAllOnPage(sideName, ev) {
        if (ev) ev.stopPropagation();
        if (this.allOnPageSelected(sideName)) {
            this.clearSelection(sideName);
        } else {
            this.selectAllOnPage(sideName);
        }
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
                    next[r.id] = r;
                }
            }
            side.selectedIds = next;
        } else if (multi) {
            const next = {...side.selectedIds};
            if (next[rec.id]) {
                delete next[rec.id];
            } else {
                next[rec.id] = rec;
            }
            side.selectedIds = next;
            side.anchorIndex = idx;
        } else {
            if (side.selectedIds[rec.id] && this.selectedCount(sideName) === 1) {
                side.selectedIds = {};
            } else {
                side.selectedIds = {[rec.id]: rec};
            }
            side.anchorIndex = idx;
        }
    }

    selectAllOnPage(sideName) {
        const side = this.state[sideName];
        const next = {...side.selectedIds};
        for (const r of side.records) {
            next[r.id] = r;
        }
        side.selectedIds = next;
    }

    invertSelection(sideName) {
        const side = this.state[sideName];
        const next = {...side.selectedIds};
        for (const r of side.records) {
            if (next[r.id]) {
                delete next[r.id];
            } else {
                next[r.id] = r;
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
        const movedIds = new Set(recs.map(r => r.id));
        const vals = recs.map(r => ({
            category_id: cat.id,
            member_id: r.id,
            entity_id: cat.entity_id[0],
        }));
        try {
            await this.orm.create("raes.md.category.member", vals);
            const next = {};
            for (const [id, rec] of Object.entries(this.state.left.selectedIds)) {
                if (!movedIds.has(id)) {
                    next[id] = rec;
                }
            }
            this.state.left.selectedIds = next;
            this.state.left.anchorIndex = null;
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
        const movedIds = new Set(recs.map(r => r.id));
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
            const next = {};
            for (const [id, rec] of Object.entries(this.state.right.selectedIds)) {
                if (!movedIds.has(id)) {
                    next[id] = rec;
                }
            }
            this.state.right.selectedIds = next;
            this.state.right.anchorIndex = null;
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
        if (record.id === undefined || record.id === null || record.id === "") {
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
        this.state.left.selectedIds = {};
        this.state.left.anchorIndex = null;
        this.loadLeft();
    }

    onSearchRight(ev) {
        this.state.right.search = ev.target.value;
        this.state.right.page = 1;
        this.state.right.selectedIds = {};
        this.state.right.anchorIndex = null;
        this.loadRight();
    }

    get leftPages() {
        return Math.max(1, Math.ceil(this.state.left.total / this.state.pageSize));
    }

    get rightPages() {
        return Math.max(1, Math.ceil(this.state.right.total / this.state.pageSize));
    }

    async nextLeft() {
        if (this.state.left.page < this.leftPages) {
            this.state.left.page++;
            this.state.left.anchorIndex = null;
            await this.loadLeft();
        }
    }

    async prevLeft() {
        if (this.state.left.page > 1) {
            this.state.left.page--;
            this.state.left.anchorIndex = null;
            await this.loadLeft();
        }
    }

    async nextRight() {
        if (this.state.right.page < this.rightPages) {
            this.state.right.page++;
            this.state.right.anchorIndex = null;
            await this.loadRight();
        }
    }

    async prevRight() {
        if (this.state.right.page > 1) {
            this.state.right.page--;
            this.state.right.anchorIndex = null;
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
        const candidate =
            record.label || record.title || record.name ||
            record.englishtitle || record.english_title || "";
        const trimmed = String(candidate).trim();
        if (trimmed && trimmed !== "#0") {
            return trimmed;
        }
        return `#${record.id}`;
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
            case "company-mismatch":
                return `This category belongs to a company you are not a member of.`;
            default:
                return "";
        }
    }
}

CategoryManager.template = "category.CategoryManager";
CategoryManager.components = {CategoryNode};

registry.category("actions").add(
    "category.category_manager", CategoryManager);