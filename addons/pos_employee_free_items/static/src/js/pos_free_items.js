/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

class FreeItemList extends Component {
    static template = "pos_employee_free_items.FreeItemList";
    static props = {};

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({ catalog: [], loading: true });

        onWillStart(async () => {
            try {
                this.state.catalog = await this.orm.searchRead(
                    "pos.free.item.catalog",
                    [["active", "=", true], ["company_id", "=", this.pos.company.id]],
                    ["id", "product_id"]
                );
            } catch {
                this.showError(_t("Free items unavailable"), _t("The free-item catalogue could not be loaded."));
            } finally {
                this.state.loading = false;
            }
        });
    }

    showError(title, body) {
        this.dialog.add(AlertDialog, { title, body });
    }

    getEmployeeId() {
        const employee = this.pos.getCashier()?.employee_id;
        if (Array.isArray(employee)) {
            return employee[0];
        }
        return employee?.id || employee || false;
    }

    getProduct(catalogItem) {
        const productId = Array.isArray(catalogItem.product_id)
            ? catalogItem.product_id[0]
            : catalogItem.product_id?.id || catalogItem.product_id;
        return this.pos.models["product.product"].get(productId);
    }

    async onSelectFreeItem(catalogItem) {
        const product = this.getProduct(catalogItem);
        if (!product) {
            this.showError(_t("Product unavailable"), _t("This free item is not available in this POS."));
            return;
        }

        const employeeId = this.getEmployeeId();
        if (!employeeId) {
            this.showError(_t("No employee linked"), _t("The current cashier has no employee record."));
            return;
        }

        const code = await makeAwaitable(this.dialog, NumberPopup, {
            title: _t("Enter 2FA code from your authenticator app"),
            startingValue: "",
            isValid: (value) => /^\d{6}$/.test(value),
        });
        if (code === undefined) {
            return;
        }

        try {
            await rpc("/pos_free_item/totp/verify", { code });
        } catch {
            this.showError(_t("Invalid code"), _t("The code is not correct. Try again."));
            return;
        }

        let result;
        try {
            result = await rpc("/pos_free_item/claim", { employee_id: employeeId });
        } catch {
            this.showError(_t("Free item unavailable"), _t("The allowance could not be claimed."));
            return;
        }
        if (!result.allowed) {
            this.showError(_t("Limit reached"), result.error || _t("You have already claimed your free items for today."));
            return;
        }

        const line = await this.pos.addLineToCurrentOrder(
            {
                product_id: product,
                product_tmpl_id: product.product_tmpl_id,
                price_unit: 0,
                is_free_item: true,
            },
            { force: true }
        );
        if (line) {
            line.is_free_item = true;
        }
    }
}

// Components referenced by a ProductScreen template extension must be registered
// on ProductScreen itself; the legacy Registries API no longer exists in Odoo 19.
ProductScreen.components = { ...ProductScreen.components, FreeItemList };
