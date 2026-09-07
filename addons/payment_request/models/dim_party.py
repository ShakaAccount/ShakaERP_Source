from odoo import models, fields

class RaesDimParty(models.Model):
    _name = 'odoo.raes.dim.party'
    _description = 'RAES Dimension Party (Read-Only, from Shaka_DW)'
    _auto = False
    _log_access = False
    _rec_name = 'title'

    partyid = fields.Integer(string='Party ID', readonly=True)
    typecode = fields.Integer(string='Type Code', readonly=True)
    typetitle = fields.Char(string='Type Title', size=10, readonly=True)
    englishtypetitle = fields.Char(string='English Type Title', size=10, readonly=True)
    title = fields.Char(string='Title', size=255, readonly=True)
    englishtitle = fields.Char(string='English Title', size=255, readonly=True)
    companyid = fields.Integer(string='Company ID', readonly=True)
    datasourceid = fields.Integer(string='Data Source ID', readonly=True)
    moduleid = fields.Integer(string='Module ID', readonly=True)
    lastupdate = fields.Datetime(string='Last Update', readonly=True)

    def init(self):
        self._cr.execute("""
            DROP VIEW IF EXISTS odoo_raes_dim_party CASCADE;
            CREATE VIEW odoo_raes_dim_party AS (
                SELECT
                    PartyID AS id,
                    PartyID,
                    TypeCode,
                    TypeTitle,
                    EnglishTypeTitle,
                    Title,
                    EnglishTitle,
                    CompanyID,
                    DataSourceID,
                    ModuleID,
                    LastUpdate
                FROM raes_dim_party_view
            )
        """)
