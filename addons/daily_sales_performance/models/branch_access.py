from odoo import api, fields, models


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
        return True


class ShakaUserBranchAccess(models.Model):
    _name = 'shaka.user.branch.access'
    _description = 'Shaka User Branch Access'
    _order = 'branch_id, id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    branch_id = fields.Many2one('daily.sales.branch', required=True, ondelete='cascade')
    _user_branch_unique = models.Constraint('unique(user_id, branch_id)', 'A branch cannot be assigned twice to one user.')

    def _sync_legacy_branch_field(self, users):
        for user in users:
            branches = self.search([('user_id', '=', user.id)]).mapped('branch_id')
            user.sudo().write({'daily_sales_branch_id': branches.id if len(branches) == 1 else False})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._sync_legacy_branch_field(records.mapped('user_id'))
        return records

    def write(self, vals):
        users = self.mapped('user_id')
        result = super().write(vals)
        self._sync_legacy_branch_field(users | self.mapped('user_id'))
        return result

    def unlink(self):
        users = self.mapped('user_id')
        result = super().unlink()
        self._sync_legacy_branch_field(users)
        return result


class ResUsersBranchAccess(models.Model):
    _inherit = 'res.users'

    daily_sales_branch_id = fields.Many2one('daily.sales.branch', string='Assigned Branch')
    shaka_branch_access_ids = fields.One2many('shaka.user.branch.access', 'user_id', string='Branch Access')

    def _shaka_branch_ids(self):
        self.ensure_one()
        if self.env.is_superuser() or self.env.user.has_group('base.group_system'):
            return []
        self.env.cr.execute('SELECT branch_id FROM shaka_user_branch_access WHERE user_id = %s', [self.id])
        return [row[0] for row in self.env.cr.fetchall()]
