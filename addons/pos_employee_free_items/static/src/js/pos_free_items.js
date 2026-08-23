/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

/**
 * Odoo 19 POS extension for choosing an approved employee free item.
 * The catalogue is loaded with normal POS data, so opening the screen never
 * depends on an extra ORM call or on back-office access rights.
 */
class FreeItemList extends Component {
    static template = "pos_employee_free_items.FreeItemList";
    static props = {};

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.state = useState({ isClaiming: false });
    }

    get catalogItems() {
        return this.pos.models["pos.free.item.catalog"]?.getAll() || [];
    }

    get hasEmployeeMode() {
        return Boolean(this.pos.config.module_pos_hr);
    }

    get cashier() {
        return this.hasEmployeeMode ? this.pos.getCashier() : false;
    }

    showError(title, body) {
        this.dialog.add(AlertDialog, { title, body });
    }

    getProduct(catalogItem) {
        return this.pos.models["product.product"].get(catalogItem.product_id?.id || catalogItem.product_id);
    }

    getProductTemplate(product) {
        const templateId = product.product_tmpl_id?.id || product.product_tmpl_id;
        return this.pos.models["product.template"].get(templateId);
    }

    async requestCode() {
        return makeAwaitable(this.dialog, NumberPopup, {
            title: _t("Confirm free item"),
            subtitle: _t("Enter the 6-digit authenticator code."),
            placeholder: "000000",
            startingValue: "",
            isValid: (value) => /^\d{6}$/.test(value),
        });
    }

    async onSelectFreeItem(catalogItem) {
        if (this.state.isClaiming) {
            return;
        }
        if (!this.hasEmployeeMode) {
            this.showError(
                _t("Employee mode is required"),
                _t("Enable Employees in this POS configuration before using employee free items.")
            );
            return;
        }
        if (!this.cashier?.id) {
            this.showError(_t("Select a cashier"), _t("Select an employee cashier before claiming a free item."));
            return;
        }

        const product = this.getProduct(catalogItem);
        const productTemplate = product && this.getProductTemplate(product);
        if (!product || !productTemplate) {
            this.showError(
                _t("Product unavailable"),
                _t("This catalogue product is not loaded in the current POS. Check that it is available in POS.")
            );
            return;
        }

        const code = await this.requestCode();
        if (code === undefined) {
            return;
        }

        this.state.isClaiming = true;
        try {
            const claim = await rpc("/pos_free_item/claim", {
                employee_id: this.cashier.id,
                product_id: product.id,
                pos_config_id: this.pos.config.id,
                code,
            });

            // Use the native POS API with the actual product.template record.
            // This keeps Odoo's tax engine and order-line bookkeeping intact.
            const line = await this.pos.addLineToCurrentOrder({
                product_id: product,
                product_tmpl_id: productTemplate,
                price_unit: 0,
                is_free_item: true,
            });
            if (!line) {
                this.showError(
                    _t("Free item was not added"),
                    _t("The allowance was approved, but Odoo could not add the item to this order.")
                );
            }
        } catch (error) {
            this.showError(_t("Free item could not be claimed"), this.getErrorMessage(error));
        } finally {
            this.state.isClaiming = false;
        }
    }

    getErrorMessage(error) {
        return (
            error?.data?.message ||
            error?.message ||
            _t("Please check the cashier, product catalogue, and authenticator code, then try again.")
        );
    }
}

// The template extends ProductScreen, therefore Owl resolves FreeItemList from
// ProductScreen.components rather than from a global component registry.
ProductScreen.components = { ...ProductScreen.components, FreeItemList };
