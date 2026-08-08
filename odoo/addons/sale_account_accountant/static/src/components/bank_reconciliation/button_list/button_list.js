import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(BankRecButtonList, {
    props: {
        ...BankRecButtonList.props,
        hasSaleOrders: { type: Boolean, optional: true },
        actionOpenSaleOrders: { type: Function, optional: true },
    },
    defaultProps: {
        ...BankRecButtonList.defaultProps,
    },
});

patch(BankRecButtonList.prototype, {
    async _setPartnerOnReconcileLine(partner_id) {
        super._setPartnerOnReconcileLine(partner_id);
        await this.bankReconciliation.checkPartnerSales(partner_id);
    },

    get isSalesButtonShown() {
        return this.props.hasSaleOrders;
    },

    get buttons() {
        const buttonsToDisplay = super.buttons;
        if (this.isSalesButtonShown) {
            buttonsToDisplay.sale = {
                label: _t("Sales"),
                action: () => this.props.actionOpenSaleOrders(),
                classes: "sales-btn",
            };
        }
        return buttonsToDisplay;
    },
});
