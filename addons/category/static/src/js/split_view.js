/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class MySplitView extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        // Get category_id from context (passed when opening the action)
        const context = this.props.action.context || {};
        const categoryId = context.active_id || context.default_category_id;

        this.state = useState({
            categoryId: categoryId,
            category: null,
            entityId: null,
            records: [],
            selectedRecord: null,
            page: 1,
            limit: 10,
            total: 0,
            searchTerm: "",
        });

        onWillStart(async () => {
            if (this.state.categoryId) {
                await this.loadCategory();
                await this.loadRecords();
            }
        });
    }

    async loadCategory() {
        const categories = await this.orm.read("raes.md.category", [this.state.categoryId], ["title", "entity_id"]);
        if (categories.length > 0) {
            this.state.category = categories[0];
            this.state.entityId = this.state.category.entity_id ? this.state.category.entity_id[0] : null;
        }
    }

    async loadRecords() {
        if (!this.state.entityId) return;

        const result = await this.orm.call(
            "raes.md.entity",
            "get_dw_records",
            [
                this.state.entityId,
                (this.state.page - 1) * this.state.limit,
                this.state.limit,
                this.state.searchTerm
            ]
        );
        this.state.records = result.records;
        this.state.total = result.total;
    }

    async selectRecord(record) {
        this.state.selectedRecord = record;
    }

    async addSelectedToCategory() {
        if (!this.state.selectedRecord || !this.state.categoryId) return;

        try {
            await this.orm.create("raes.md.category.member", [{
                category_id: this.state.categoryId,
                member_id: this.state.selectedRecord.id, // The PK from the DW table
                entity_id: this.state.entityId,
            }]);
            this.notification.add("Record added to category successfully!", { type: "success" });
            this.state.selectedRecord = null;
        } catch (error) {
            this.notification.add("Error adding record. It might already exist.", { type: "danger" });
        }
    }

    async nextPage() {
        if (this.state.page * this.state.limit < this.state.total) {
            this.state.page++;
            await this.loadRecords();
        }
    }

    async prevPage() {
        if (this.state.page > 1) {
            this.state.page--;
            await this.loadRecords();
        }
    }

    async firstPage() {
        this.state.page = 1;
        await this.loadRecords();
    }

    async lastPage() {
        this.state.page = Math.ceil(this.state.total / this.state.limit) || 1;
        await this.loadRecords();
    }

    onSearch(ev) {
        this.state.searchTerm = ev.target.value;
        this.state.page = 1;
        this.loadRecords();
    }
}

MySplitView.template = "my_module.MySplitView";
registry.category("actions").add("my_directory_split_view", MySplitView);