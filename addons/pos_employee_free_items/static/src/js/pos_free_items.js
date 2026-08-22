/** POS widget that intercepts the "Free Item" button,
 *  asks the cashier for a TOTP code, validates it via the
 *  JSON endpoint, then adds the selected free product with
 *  price 0 and marks the line as a free-item.                                            */

odoo.define('pos_employee_free_items.PosFreeItems', function (require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');
    const { useListener } = require('@web/core/utils/hooks');
    const { _t } = require('web.core');
    const rpc = require('web.rpc');

    class FreeItemButton extends PosComponent {
        static template = 'FreeItemButton';
        static props = ['product'];

        setup() {
            super.setup();
            useListener('click', this.onClick);
        }

        async onClick() {
            const { confirmed, payload: code } = await this.showPopup('NumberPopup', {
                title: _t('Enter 2FA code from your authenticator app'),
                startingValue: '',
                cheap: true,
            });
            if (!confirmed) return;

            // 1️⃣ verify TOTP
            try {
                await rpc.query({
                    route: '/pos_free_item/totp/verify',
                    params: { code: parseInt(code, 10) },
                });
            } catch (e) {
                await this.showPopup('ErrorPopup', {
                    title: _t('Invalid code'),
                    body: _t('The code you entered is not correct. Try again.'),
                });
                return;
            }

            // 2️⃣ claim allowance (server side)
            const order = this.env.pos.get_order();
            const employee = this.env.pos.get_cashier()?.employee_id;
            if (!employee) {
                await this.showPopup('ErrorPopup', { title: _t('No employee linked'), body: _t('Cashier has no employee record.') });
                return;
            }

            const { allowed } = await rpc.query({
                route: '/pos_free_item/claim',
                params: { employee_id: employee[0] },
            });

            if (!allowed) {
                await this.showPopup('ErrorPopup', {
                    title: _t('Limit reached'),
                    body: _t('You have already claimed your 2 free items for today.'),
                });
                return;
            }

            // 3️⃣ add line with price 0 and flag
            const line = new (require('point_of_sale.models').Orderline)({}, {
                pos: this.env.pos,
                product: this.props.product,
                quantity: 1,
                price: 0,
                is_free_item: true,
            });
            order.add_orderline(line);
        }
    }

    FreeItemButton.template = 'FreeItemButton';

    // Register as a component that can be dropped into the POS product screen
    Registries.Component.add(FreeItemButton);

    // Component to display the list of free items
    const { useState } = require('@odoo/owl');

    class FreeItemList extends PosComponent {
        static template = 'FreeItemList';

        setup() {
            super.setup();
            this.state = useState({ catalog: [] });
            // fetch catalogue once
            this.env.services.rpc({
                route: '/web/dataset/call_kw',
                params: {
                    model: 'pos.free.item.catalog',
                    method: 'search_read',
                    args: [[['active','=',true],['company_id','=',this.env.pos.company.id]]],
                    kwargs: {fields: ['id','product_id']},
                },
            }).then(res => this.state.catalog = res);
        }
    }

    Registries.Component.add(FreeItemList);

    return { FreeItemButton, FreeItemList };
});