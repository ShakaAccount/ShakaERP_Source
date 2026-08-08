# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.addons.mrp_account.tests.common import TestBomPriceOperationCommon
from freezegun import freeze_time


class TestReportsCommon(TestBomPriceOperationCommon):

    @freeze_time('2022-05-28')
    def test_mrp_avg_cost_calculation(self):
        """
            Check that the average cost is calculated based on the quantity produced in each MO

            1:/ MO1:
                - qty to produce: 10 units
                - work_order duration: 300
                unit_component_cost = (12 * 200 + 60 * 10 + 12 * 100 + 57 * 25) + (50 * 3)) = 5625
                unit_duration = 300 / 10 = 30
                unit_operation_cost = 100 * 30'unit_duration' = 50
                unit_cost = 5623 + 50 = 5675

            2:/ MO2:
                - update plywood_sheet cost to: $300
                - qty to produce: 20 units
                - work order duration: 600
                unit_component_cost = (12 * 300 + 60 * 10 + 12 * 100 + 57 * 25) + (50 * 3)) = 6825
                unit_duration = 600 / 20 = 30
                unit_operation_cost = 100 * 30'unit_duration' = 50
                unit_cost = 6825 + 50 = 6875

            total_qty_produced = 30
            avg_unit_component_cost = ((5625 * 10) + (6825 * 20)) / 30 = $6425
            avg_unit_operation_cost = ((50*20) + (50*10)) / 30 = $50
            avg_unit_duration = (600 + 300) / 30 = 30
            avg_unit_cost = avg_unit_component_cost + avg_unit_operation_cost = $6525
        """
        self.table_head.categ_id = self.category_avco
        self.bom_2.type = 'normal'
        self.bom_2.product_uom_id = self.uom

        # MO_1
        mo_1 = self._create_mo(self.bom_2, 10)
        mo_1.button_plan()
        wo = mo_1.workorder_ids
        wo.button_start()
        wo.duration = 100  # 3 wo * 100 = 300
        wo.qty_producing = 10

        mo_1.button_mark_done()

        self.plywood_sheet.standard_price = 300
        # MO_2
        self.glass.standard_price = 30
        mo_2 = self._create_mo(self.bom_2, 20)
        mo_2.button_plan()
        wo = mo_2.workorder_ids
        wo.button_start()
        wo.duration = 200
        wo.qty_producing = 20

        mo_2.button_mark_done()

        # must flush else SQL request in report is not accurate
        self.env.flush_all()

        report = self.env['mrp.report']._read_group(
            [('product_id', '=', self.table_head.id)],
            aggregates=['unit_cost:avg', 'unit_component_cost:avg', 'unit_operation_cost:avg', 'unit_duration:avg'],
        )[0]
        unit_cost, unit_component_cost, unit_operation_cost, unit_duration = report
        self.assertEqual(self.company.currency_id.round(unit_cost), 6475)
        self.assertEqual(self.company.currency_id.round(unit_component_cost), 6425)
        self.assertEqual(self.company.currency_id.round(unit_operation_cost), 50)
        self.assertEqual(self.company.currency_id.round(unit_duration), 30)
