from odoo import fields, models


class DailySalesBranch(models.Model):
    _name = 'daily.sales.branch'
    _description = 'Shaka DW Branch'
    _table = 'dw_dim_branch'
    _auto = False
    _log_access = False
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Branch Name', readonly=True)
    company_id = fields.Integer(string='Company', readonly=True)
    data_source_id = fields.Integer(string='Data Source', readonly=True)
    def init(self):
        # dw_dim_branch is maintained by the DW connector and reads directly
        # from Shaka_DW.BI.DimBranch. This model is intentionally read-only.
        return True
