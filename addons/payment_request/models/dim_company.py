from odoo import models, fields

from .dim_base import refresh_dim_view

class DimCompany(models.Model):
    _name = 'odoo.raes.dim.company'
    _description = 'Company Dimension (Read-Only, from Shaka_DW)'
    _auto = False
    _log_access = False
    _rec_name = 'companytitle'

    companyid = fields.Integer(string='Company ID', readonly=True)
    parentid = fields.Integer(string='Parent ID', readonly=True)
    entitle = fields.Char(string='English Title', readonly=True)
    level0 = fields.Char(string='Level 0', readonly=True)
    level1 = fields.Char(string='Level 1', readonly=True)
    level2 = fields.Char(string='Level 2', readonly=True)
    level3 = fields.Char(string='Level 3', readonly=True)
    companytitle = fields.Char(string='Company Title', readonly=True)

    def init(self):
        # rebuild the read-only view; missing/partial DW source -> empty view
        refresh_dim_view(
            self.env, 'odoo_raes_dim_company', 'companyid',
            {'companyid': 'integer', 'parentid': 'integer',
             'entitle': 'text', 'level0': 'text', 'level1': 'text',
             'level2': 'text', 'level3': 'text', 'companytitle': 'text'},
            ['raes_dim_company_view', 'raes_dim_company',
             'raees_dim_company_view', 'raes_dimcompany'],
            'DimCompany')
