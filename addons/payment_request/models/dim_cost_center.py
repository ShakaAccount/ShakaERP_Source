from odoo import models, fields

from .dim_base import refresh_dim_view


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
        # rebuild the read-only view; missing/partial DW source -> empty view
        refresh_dim_view(
            self.env, 'odoo_raes_dim_cost_center', 'costcenterid',
            {'costcenterid': 'integer', 'code': 'text', 'title': 'text',
             'grouptitle': 'text', 'englishtitle': 'text',
             'englishgrouptitle': 'text', 'companyid': 'integer',
             'datasourceid': 'integer', 'moduleid': 'integer',
             'lastupdate': 'timestamp'},
            ['raes_dim_cost_center_view', 'raes_dim_cost_center',
             'raees_dim_cost_center_view', 'raes_dimcostcenter'],
            'DimCostCenter')
