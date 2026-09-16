/** @odoo-module **/
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Component, useState, onWillStart, useRef, useExternalListener} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";

const TREE_WIDTH_KEY = "category_manager.tree_width";
const TREE_MIN = 180;
const TREE_MAX = 700;
const COL_MIN = 60;

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
        this.entityPickerRef = useRef("entityPicker");
        this._drag = null;
        this._entitiesLoaded = false;
        this._filterCacheKey = null;
        this._filterCacheValue = null;

        useExternalListener(document, "click", (ev) => {
            if (this.state.showLabelPicker) {
                const el = this.labelPickerRef.el;
                if (el && !el.contains(ev.target)) {
                    this.state.showLabelPicker = false;
                }
            }
            if (this.state.entityPickerOpen) {
                const el = this.entityPickerRef.el;
                if (el && !el.contains(ev.target)) {
                    this.closeEntityPicker();
                }
            }
        });
        useExternalListener(window, "mousemove", (ev) => this._handleMouseMove(ev));
        useExternalListener(window, "mouseup", () => this._handleMouseUp());

        this.state = useState({
            tree: [],
            treeByParent: {},
            loading: true,
            selectedCategory: null,
            expandedIds: {},
            closingIds: {},
            treeSearch: "",
            entities: [],
            entityPickerOpen: false,
            entitySearch: "",
            entityHighlightIdx: 0,
            left: this._blankSide(),
            right: this._blankSide(),
            showNewCategory: false,
            newCategory: {title: "", code: "", entity_id: null},
            saving: false,
            entityColumns: [],
            labelColumns: [],
            colWidths: {},
            showLabelPicker: false,
            treeWidth: 280,
            pageSize: 20,
            dragCol: null,
            dragOverCol: null,
            resizingCol: null,
            resizingTree: false,
        });

        try {
            const saved = parseInt(localStorage.getItem(TREE_WIDTH_KEY), 10);
            if (saved >= TREE_MIN && saved <= TREE_MAX) {
                this.state.treeWidth = saved;
            }
        } catch (e) { /* ignore */
        }

        try {
            const saved = parseInt(
                localStorage.getItem(this._pageSizeStorageKey()), 10);
            if (saved > 0) {
                this.state.pageSize = saved;
            }
        } catch (e) { /* ignore */
        }

        this.getChildren = (cat) => {
            const all = this.state.treeByParent[cat.id] || [];
            const res = this._filterResult;
            if (!res) return all;
            return all.filter(c => res.visible.has(c.id));
        };
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
            searchColumn: "",
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
            this._filterCacheKey = null;
        } catch (e) {
            console.error("get_category_tree failed", e);
            this.notification.add(
                "Could not load the category tree.", {type: "danger"});
        } finally {
            this.state.loading = false;
        }
    }

    // ---------- Tree search ----------
    onTreeSearch(ev) {
        this.state.treeSearch = ev.target.value;
        this._filterCacheKey = null;
    }

    clearTreeSearch(ev) {
        if (ev) ev.stopPropagation();
        this.state.treeSearch = "";
        this._filterCacheKey = null;
    }

    get _filterResult() {
        const term = (this.state.treeSearch || "").trim().toLowerCase();
        if (!term) return null;
        const cacheKey = term + "|" + this.state.tree.length;
        if (this._filterCacheKey === cacheKey) {
            return this._filterCacheValue;
        }
        const visible = new Set();
        const autoExpand = new Set();
        const byId = new Map(this.state.tree.map(c => [c.id, c]));
        const hasChildren = (id) =>
            (this.state.treeByParent[id] || []).length > 0;

        for (const cat of this.state.tree) {
            const t = (cat.title || "").toLowerCase();
            if (!t.includes(term)) continue;
            let node = cat;
            while (node && !visible.has(node.id)) {
                visible.add(node.id);
                if (node.parent_id) {
                    autoExpand.add(node.parent_id[0]);
                }
                node = node.parent_id
                    ? byId.get(node.parent_id[0])
                    : null;
            }
            if (hasChildren(cat.id)) {
                autoExpand.add(cat.id);
            }
        }
        const value = {visible, autoExpand};
        this._filterCacheKey = cacheKey;
        this._filterCacheValue = value;
        return value;
    }

    get filteredRootNodes() {
        const roots = this.state.treeByParent[0] || [];
        const res = this._filterResult;
        if (!res) return roots;
        return roots.filter(c => res.visible.has(c.id));
    }

    get effectiveExpandedIds() {
        const res = this._filterResult;
        if (!res || res.autoExpand.size === 0) return this.state.expandedIds;
        const merged = {};
        for (const k of Object.keys(this.state.expandedIds)) {
            merged[k] = this.state.expandedIds[k];
        }
        for (const id of res.autoExpand) {
            merged[id] = true;
        }
        return merged;
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
            this.state[side].searchColumn = "";
            this.state[side].selectedIds = {};
            this.state[side].anchorIndex = null;
        }
        this.state.showLabelPicker = false;
        this.state.labelColumns = [];
        this.state.colWidths = {};
        if (cat && cat.entity_id) {
            const eid = cat.entity_id[0];
            this.state.labelColumns = this._loadLabelColumns(eid);
            this.state.colWidths = this._loadColWidths(eid);
        }
        await this.reloadPanes();
    }

    async reloadPanes() {
        await Promise.all([this.loadLeft(), this.loadRight()]);
    }

    // ---------- Persistence keys ----------
    _labelStorageKey(entityId) {
        return `category_manager.label.${entityId}`;
    }

    _colWidthsStorageKey(entityId) {
        return `category_manager.colwidths.${entityId}`;
    }

    _pageSizeStorageKey() {
        return "category_manager.page_size";
    }

    // ---------- Label column picker ----------
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

    _loadColWidths(entityId) {
        try {
            const raw = localStorage.getItem(this._colWidthsStorageKey(entityId));
            if (!raw) return {};
            const parsed = JSON.parse(raw);
            return parsed && typeof parsed === "object" ? parsed : {};
        } catch (e) {
            return {};
        }
    }

    _persistColWidths() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) return;
        try {
            localStorage.setItem(
                this._colWidthsStorageKey(cat.entity_id[0]),
                JSON.stringify(this.state.colWidths));
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
        const list = [...this.state.labelColumns];
        const idx = list.indexOf(name);
        if (idx !== -1) {
            list.splice(idx, 1);
        } else {
            list.push(name);
        }
        this.state.labelColumns = list;
        this._persistLabelColumns();
    }

    clearLabelColumns(ev) {
        if (ev) ev.stopPropagation();
        this.state.labelColumns = [];
        this._persistLabelColumns();
    }

    get labelPickerSummary() {
        const n = this.state.labelColumns.length;
        if (n === 0) return "Auto";
        if (n === 1) return this.state.labelColumns[0];
        if (n <= 3) return this.state.labelColumns.join(" · ");
        return `${n} columns`;
    }

    get tableColumns() {
        const avail = new Map(this.state.entityColumns.map(c => [c.name, c]));
        const chosen = this.state.labelColumns.filter(n => avail.has(n));
        if (chosen.length) {
            return chosen.map(n => avail.get(n));
        }
        return [{name: null, title: "Display name"}];
    }

    refreshLabelOptions() {
        const rec = this.state.right.records[0] || this.state.left.records[0];
        if (!rec) {
            return;
        }
        const skip = new Set(["id", "_pk", "label", "_auto_label"]);
        this.state.entityColumns = Object.keys(rec)
            .filter(k => !skip.has(k))
            .map(k => ({name: k, title: k}));
    }

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

    // ---------- Column reorder ----------
    onColReorderStart(colName, ev) {
        if (!colName || this.state.labelColumns.length < 2) return;
        if (ev.button !== 0) return;
        ev.preventDefault();
        this._drag = {
            type: "reorder",
            colName,
            startX: ev.clientX,
            startY: ev.clientY,
            moved: false,
        };
    }

    // ---------- Column resize ----------
    onColResizeStart(colName, ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const th = ev.target.closest("th");
        const startWidth = th
            ? Math.round(th.getBoundingClientRect().width)
            : 120;
        this._drag = {
            type: "col",
            colName,
            startX: ev.clientX,
            startWidth,
            rtlSign: this._rtlSign(th),
        };
        this.state.resizingCol = colName;
    }

    // ---------- Tree pane resize ----------
    onTreeResizeStart(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const container = ev.currentTarget.parentElement;
        const treePane = container
            ? container.querySelector(".o_cat_pane_tree")
            : null;
        this._drag = {
            type: "tree",
            startX: ev.clientX,
            startWidth: this.state.treeWidth,
            rtlSign: this._rtlSign(treePane || ev.currentTarget),
        };
        this.state.resizingTree = true;
    }

    // ---------- RTL detection ----------
    _rtlSign(el) {
        const target = el || document.body;
        try {
            return getComputedStyle(target).direction === "rtl" ? -1 : 1;
        } catch (e) {
            return 1;
        }
    }

    // ---------- Global pointer handlers ----------
    _handleMouseMove(ev) {
        const d = this._drag;
        if (!d) return;
        const sign = d.rtlSign || 1;

        if (d.type === "col") {
            const delta = (ev.clientX - d.startX) * sign;
            const w = Math.max(COL_MIN, d.startWidth + delta);
            this.state.colWidths = {...this.state.colWidths, [d.colName]: w};
        } else if (d.type === "tree") {
            const delta = (ev.clientX - d.startX) * sign;
            const w = Math.max(TREE_MIN, Math.min(TREE_MAX, d.startWidth + delta));
            this.state.treeWidth = w;
        } else if (d.type === "reorder") {
            if (!d.moved) {
                const dx = Math.abs(ev.clientX - d.startX);
                const dy = Math.abs(ev.clientY - d.startY);
                if (dx > 5 || dy > 5) {
                    d.moved = true;
                    this.state.dragCol = d.colName;
                }
            }
            if (d.moved) {
                const el = document.elementFromPoint(ev.clientX, ev.clientY);
                const th = el && el.closest
                    ? el.closest("th[data-col-name]")
                    : null;
                const over = th ? th.getAttribute("data-col-name") : null;
                this.state.dragOverCol =
                    (over && over !== d.colName) ? over : null;
            }
        }
    }

    _handleMouseUp() {
        const d = this._drag;
        if (!d) return;

        if (d.type === "col") {
            this.state.resizingCol = null;
            this._persistColWidths();
        } else if (d.type === "tree") {
            this.state.resizingTree = false;
            try {
                localStorage.setItem(
                    TREE_WIDTH_KEY, String(this.state.treeWidth));
            } catch (e) { /* ignore */
            }
        } else if (d.type === "reorder") {
            const target = this.state.dragOverCol;
            if (d.moved && target && target !== d.colName) {
                const list = [...this.state.labelColumns];
                const from = list.indexOf(d.colName);
                const to = list.indexOf(target);
                if (from !== -1 && to !== -1) {
                    list.splice(from, 1);
                    list.splice(to, 0, d.colName);
                    this.state.labelColumns = list;
                    this._persistLabelColumns();
                }
            }
            this.state.dragCol = null;
            this.state.dragOverCol = null;
        }

        this._drag = null;
    }

    // ---------- Page size ----------
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
                side.searchColumn || false,
            ]);
            side.records = res.records || [];
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

    // ---------- Selection ----------
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
                if (r) next[r.id] = r;
            }
            side.selectedIds = next;
        } else if (multi) {
            const next = {...side.selectedIds};
            if (next[rec.id]) delete next[rec.id];
            else next[rec.id] = rec;
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
        for (const r of side.records) next[r.id] = r;
        side.selectedIds = next;
    }

    invertSelection(sideName) {
        const side = this.state[sideName];
        const next = {...side.selectedIds};
        for (const r of side.records) {
            if (next[r.id]) delete next[r.id];
            else next[r.id] = r;
        }
        side.selectedIds = next;
    }

    // ---------- Bulk move ----------
    async bulkAddSelected() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) return;
        const recs = this.selectedRecords("left");
        if (!recs.length) return;
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
                if (!movedIds.has(id)) next[id] = rec;
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
        if (!cat || !cat.entity_id) return;
        const recs = this.selectedRecords("right");
        if (!recs.length) return;
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
                if (!movedIds.has(id)) next[id] = rec;
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
        if (!cat || !cat.entity_id) return;
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
        if (!cat || !cat.entity_id) return;
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

    onSearchColumnChange(sideName, ev) {
        const col = ev.target.value || "";
        this.state[sideName].searchColumn = col;
        this.state[sideName].page = 1;
        if (this.state[sideName].search) {
            if (sideName === "left") {
                this.loadLeft();
            } else {
                this.loadRight();
            }
        }
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
    async loadEntities() {
        if (this._entitiesLoaded) return;
        try {
            const rows = await this.orm.searchRead(
                "raes.md.entity",
                [["entity_type_lu", "=", "1"]],
                ["id", "name", "title"],
                {limit: 500, order: "name"});
            this.state.entities = rows.map(e => ({
                id: e.id,
                name: e.name,
                title: e.title || e.name,
            }));
            this._entitiesLoaded = true;
        } catch (e) {
            console.error("loadEntities failed", e);
            this.notification.add(
                "Could not load the entity list.", {type: "danger"});
        }
    }

    // ---------- Entity picker (combobox) ----------
    get selectedEntity() {
        const id = this.state.newCategory.entity_id;
        if (!id) return null;
        const n = Number(id);
        return this.state.entities.find(e => e.id === n) || null;
    }

    get filteredEntities() {
        const term = (this.state.entitySearch || "").trim().toLowerCase();
        const list = this.state.entities;
        if (!term) return list;
        return list.filter(e => {
            const t = (e.title || "").toLowerCase();
            const n = (e.name || "").toLowerCase();
            return t.includes(term) || n.includes(term);
        });
    }

    async toggleEntityPicker(ev) {
        if (ev) ev.stopPropagation();
        if (this.state.newCategory.parent_id) return;
        if (this.state.entityPickerOpen) {
            this.closeEntityPicker();
        } else {
            await this.openEntityPicker();
        }
    }

    async openEntityPicker() {
        if (this.state.newCategory.parent_id) return;
        if (this.state.entityPickerOpen) return;
        this.state.entityPickerOpen = true;
        this.state.entitySearch = "";
        this.state.entityHighlightIdx = 0;
        await new Promise((resolve) => setTimeout(resolve, 0));
        const el = this.entityPickerRef.el;
        const input = el && el.querySelector(".o_cat_entity_search");
        if (input) input.focus();
    }

    closeEntityPicker() {
        this.state.entityPickerOpen = false;
        this.state.entitySearch = "";
        this.state.entityHighlightIdx = 0;
    }

    onEntitySearchInput(ev) {
        this.state.entitySearch = ev.target.value;
        this.state.entityHighlightIdx = 0;
    }

    onEntityKeydown(ev) {
        const list = this.filteredEntities;
        if (ev.key === "Escape") {
            this.closeEntityPicker();
            ev.preventDefault();
            ev.stopPropagation();
        } else if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.state.entityHighlightIdx =
                Math.min(this.state.entityHighlightIdx + 1, list.length - 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.state.entityHighlightIdx =
                Math.max(this.state.entityHighlightIdx - 1, 0);
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const sel = list[this.state.entityHighlightIdx];
            if (sel) this.selectEntity(sel);
        }
    }

    selectEntity(ent) {
        this.state.newCategory.entity_id = ent.id;
        this.closeEntityPicker();
    }

    clearEntity(ev) {
        if (ev) ev.stopPropagation();
        this.state.newCategory.entity_id = null;
        this.state.entitySearch = "";
    }

    async openNewCategory(parentCat) {
        await this.loadEntities();
        const parent = parentCat || this.state.selectedCategory;
        const nested = !!parentCat;
        this.state.newCategory = {
            title: "",
            code: "",
            parent_id: nested ? parent.id : null,
            parent_title: nested ? parent.title : null,
            entity_id: parent && parent.entity_id ? parent.entity_id[0] : null,
        };
        this.closeEntityPicker();
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
            if (this.state.selectedCategory &&
                !remaining.has(this.state.selectedCategory.id)) {
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
        this.closeEntityPicker();
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
                entity_id: nc.entity_id ? parseInt(nc.entity_id, 10) : false,
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
CategoryManager.props = {
    action: {type: Object, optional: true},
    actionId: {type: [Number, String], optional: true},
    updateActionState: {type: Function, optional: true},
    className: {type: String, optional: true},
};
registry.category("actions").add(
    "category.category_manager", CategoryManager);