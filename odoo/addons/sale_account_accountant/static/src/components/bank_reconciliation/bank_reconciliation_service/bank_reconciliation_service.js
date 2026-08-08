import { BankReconciliationService } from "@account_accountant/components/bank_reconciliation/bank_reconciliation_service";
import { reactive } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(BankReconciliationService.prototype, {
    setup(env, services) {
        super.setup(...arguments);
        this.partnersWithSales = reactive({});
    },
    async fetchPartnersWithSales(records) {
        const partner_ids = records
            .filter((record) => !!record.data.partner_id.id)
            .map((record) => record.data.partner_id.id);

        const result = await this.orm.webReadGroup(
            "sale.order",
            [["partner_id", "in", partner_ids]],
            ["partner_id"],
            []
        );
        this.partnersWithSales = {};
        result.groups.forEach((group) => {
            this.partnersWithSales[group.partner_id[0]] = true;
        });
    },
    async checkPartnerSales(partner_id) {
        if (partner_id in this.partnersWithSales) {
            return;
        }
        const result = await this.orm.search("sale.order", [["partner_id", "=", partner_id]], {
            limit: 1,
        });
        this.partnersWithSales[partner_id] = result.length > 0;
    },
});
