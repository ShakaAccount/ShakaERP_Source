from odoo import models, fields

class DimCompany(models.Model):
    _name = 'dim.company'
    _description = 'Company Dimension (Read-Only, from Shaka_DW)'
    _auto = False
    _log_access = False

    companyid = fields.Integer(string='Company ID', readonly=True)
    parentid = fields.Integer(string='Parent ID', readonly=True)
    entitle = fields.Char(string='English Title', readonly=True)
    level0 = fields.Char(string='Level 0', readonly=True)
    level1 = fields.Char(string='Level 1', readonly=True)
    level2 = fields.Char(string='Level 2', readonly=True)
    level3 = fields.Char(string='Level 3', readonly=True)
    companytitle = fields.Char(string='Company Title', readonly=True)

    def init(self):
        self._cr.execute("""
            DROP VIEW IF EXISTS dim_company CASCADE;
            CREATE VIEW dim_company AS (
                SELECT
                    companyid AS id,
                    companyid,
                    parentid,
                    entitle,
                    level0,
                    level1,
                    level2,
                    level3,
                    companytitle
                FROM dim_company_view
            )
        """)