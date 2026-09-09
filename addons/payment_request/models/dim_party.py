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
        # alias view (raes_dim_party_view) is created by the DW Connection
        # bootstrap (Settings -> DW Connections) or by hand; it may legitimately
        # be absent (fresh DB / DW not wired yet) -> skip instead of blocking
        # module install
        self.env.cr.execute(
            "SELECT 1 FROM pg_views WHERE viewname = 'raes_dim_party_view'")
        if not self.env.cr.fetchone():
            return
        self.env.cr.execute("DROP VIEW IF EXISTS odoo_raes_dim_party CASCADE")
        self.env.cr.execute("""
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
