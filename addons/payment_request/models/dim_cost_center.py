from odoo import models, fields


class OdooRaesDimCostCenter(models.Model):
    _name = 'odoo.raes.dim.cost_center'
    _description = 'RAES Dimension Cost Center (Read-Only, from Shaka_DW)'
    _auto = False
    _log_access = False
    _rec_name = 'title'

    costcenterid = fields.Integer(string='Cost Center ID', readonly=True)
    code = fields.Char(string='Code', readonly=True)
    title = fields.Char(string='Title', readonly=True)
    grouptitle = fields.Char(string='Group Title', readonly=True)
    englishtitle = fields.Char(string='English Title', readonly=True)
    englishgrouptitle = fields.Char(string='English Group Title', readonly=True)
    companyid = fields.Integer(string='Company ID', readonly=True)
    datasourceid = fields.Integer(string='Data Source ID', readonly=True)
    moduleid = fields.Integer(string='Module ID', readonly=True)
    lastupdate = fields.Datetime(string='Last Update', readonly=True)

    def init(self):
        self._cr.execute("DROP VIEW IF EXISTS odoo_raes_dim_cost_center CASCADE")
        self._cr.execute("""
            CREATE VIEW odoo_raes_dim_cost_center AS (
                SELECT
                    costcenterid AS id,
                    costcenterid,
                    code,
                    title,
                    grouptitle,
                    englishtitle,
                    englishgrouptitle,
                    companyid,
                    datasourceid,
                    moduleid,
                    lastupdate
                FROM raes_dim_cost_center_view
            )
        """)
