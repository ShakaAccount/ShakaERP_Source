/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

// ---------- Recursive Tree Node ----------
export class CategoryNode extends Component {
    get hasChildren() {
        return this.props.children && this.props.children.length > 0;
    }
    onClick(ev) {
        ev.stopPropagation();
        this.props.onSelect(this.props.category);
    }
    onToggle(ev) {
        ev.stopPropagation();
        this.props.onToggle(this.props.category.id);
    }
}
CategoryNode.template = "category.CategoryNode";
CategoryNode.props = {
    category: Object,
    children: { type: Array, optional: true },
    selectedId: { type: Number, optional: true },
    expandedIds: Object,
    onSelect: Function,
    onToggle: Function,
    getChildren: Function,
    level: Number,
};
// FIX: register the component in itself so it can recurse
CategoryNode.components = { CategoryNode };


// ---------- Main Component ----------
export class CategoryManager extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            tree: [],
            treeByParent: {},
            selectedCategory: null,
            expandedIds: {},
            left:  { records: [], total: 0, page: 1, search: '' },
            right: { records: [], total: 0, page: 1, search: '' },
            showNewCategory: false,
            newCategory: { title: '', code: '', parent_id: null, entity_id: null },
        });

        onWillStart(async () => {
            await this.reloadTree();
        });
    }

    // ---------- Tree ----------
    async reloadTree() {
        const flat = await this.orm.call("raes.md.entity", "get_category_tree", []);
        const byParent = {};
        for (const c of flat) {
            const key = c.parent_id ? c.parent_id[0] : 0;
            (byParent[key] = byParent[key] || []).push(c);
        }
        for (const k in byParent) {
            byParent[k].sort((a, b) => (a.title || '').localeCompare(b.title || ''));
        }
        this.state.tree = flat;
        this.state.treeByParent = byParent;
    }

    get rootNodes() {
        return this.state.treeByParent[0] || [];
    }

    // FIX: bind getChildren so it's a stable function on `this`
    getChildren = (cat) => {
        return this.state.treeByParent[cat.id] || [];
    };

    toggleExpand(id) {
        this.state.expandedIds[id] = !this.state.expandedIds[id];
    }

    async selectCategory(cat) {
        this.state.selectedCategory = cat;
        this.state.left.page = 1;
        this.state.right.page = 1;
        this.state.left.search = '';
        this.state.right.search = '';
        await Promise.all([this.loadLeft(), this.loadRight()]);
    }

    // ---------- DW item lists ----------
    async loadLeft() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            this.state.left.records = [];
            this.state.left.total = 0;
            return;
        }
        const entity_id = cat.entity_id[0];
        const res = await this.orm.call(
            "raes.md.entity",
            "get_items_not_in_category",
            [entity_id, cat.id,
             (this.state.left.page - 1) * 20, 20,
             this.state.left.search || ''],
        );
        this.state.left.records = res.records;
        this.state.left.total = res.total;
    }

    async loadRight() {
        const cat = this.state.selectedCategory;
        if (!cat || !cat.entity_id) {
            this.state.right.records = [];
            this.state.right.total = 0;
            return;
        }
        const entity_id = cat.entity_id[0];
        const res = await this.orm.call(
            "raes.md.entity",
            "get_items_in_category",
            [entity_id, cat.id,
             (this.state.right.page - 1) * 20, 20,
             this.state.right.search || ''],
        );
        this.state.right.records = res.records;
        this.state.right.total = res.total;
    }

    async addToCategory(record) {
        const cat = this.state.selectedCategory;
        if (!cat) return;
        try {
            await this.orm.create("raes.md.category.member", [{
                category_id: cat.id,
                member_id: record.id,
                entity_id: cat.entity_id[0],
            }]);
            await Promise.all([this.loadLeft(), this.loadRight()]);
        } catch (e) {
            this.notification.add("Could not add record.", { type: "danger" });
        }
    }

    async removeFromCategory(record) {
        const cat = this.state.selectedCategory;
        if (!cat) return;
        const members = await this.orm.searchRead(
            "raes.md.category.member",
            [["category_id", "=", cat.id],
             ["member_id", "=", record.id],
             ["entity_id", "=", cat.entity_id[0]]],
            ["id"],
        );
        if (members.length) {
            await this.orm.unlink("raes.md.category.member", [members[0].id]);
            await Promise.all([this.loadLeft(), this.loadRight()]);
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

    async nextLeft() {
        if (this.state.left.page * 20 < this.state.left.total) {
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
        if (this.state.right.page * 20 < this.state.right.total) {
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
    openNewCategory(parentCat = null) {
        this.state.newCategory = {
            title: '',
            code: '',
            parent_id: parentCat ? parentCat.id : null,
            entity_id: parentCat && parentCat.entity_id ? parentCat.entity_id[0] : null,
        };
        this.state.showNewCategory = true;
    }
    cancelNewCategory() {
        this.state.showNewCategory = false;
    }
    async saveNewCategory() {
        const nc = this.state.newCategory;
        if (!nc.title) {
            this.notification.add("Title is required.", { type: "warning" });
            return;
        }
        if (!nc.entity_id) {
            this.notification.add("Please set an entity.", { type: "warning" });
            return;
        }
        await this.orm.create("raes.md.category", [{
            title: nc.title,
            code: nc.code || false,
            parent_id: nc.parent_id || false,
            entity_id: nc.entity_id,
        }]);
        this.state.showNewCategory = false;
        await this.reloadTree();
    }

    recordLabel(record) {
        return record.title || record.name || record.english_title ||
               `#${record.id}`;
    }
}
CategoryManager.template = "category.CategoryManager";
CategoryManager.components = { CategoryNode };

registry.category("actions").add(
    "category.category_manager", CategoryManager);