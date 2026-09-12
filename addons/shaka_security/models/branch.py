from odoo import fields, models


class DailySalesBranch(models.Model):
    _name = 'daily.sales.branch'
    _description = 'Shaka DW Branch'
    _table = 'daily_sales_branch_external'
    _auto = False
    _log_access = False
    _rec_name = 'name'
    _order = 'name'

    branchid = fields.Char(string='BranchID', readonly=True)
    name = fields.Char(string='Branch Name', readonly=True)
    companyid = fields.Integer(string='Company', readonly=True)
    datasourceid = fields.Integer(string='Data Source', readonly=True)
    user_ids = fields.One2many('res.users', 'daily_sales_branch_id', string='Branch Users')

    def init(self):
        self.env.cr.execute("""
            DO $body$
            BEGIN
                IF to_regclass('daily_sales_branch_external') IS NULL THEN
                    EXECUTE $view$CREATE VIEW daily_sales_branch_external AS
                        SELECT row_number() OVER (ORDER BY id)::integer AS id,
                               id::varchar AS branchid,
                               name,
                               company_id AS companyid,
                               data_source_id AS datasourceid
                        FROM dw_dim_branch$view$;
                END IF;
            END $body$;
        """)
