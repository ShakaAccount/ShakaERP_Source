from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CompanyFiscalYear(models.Model):
    _name = 'company.fiscal.year'
    _inherit = ['shaka.access.mixin']
    _description = 'Company Fiscal Year'
    _order = 'date_start desc, company_id, name desc'

    name = fields.Char(string='سال مالی', required=True, index=True)
    company_id = fields.Many2one(
        'res.company',
        string='شرکت',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    date_start = fields.Date(string='از تاریخ', required=True)
    date_end = fields.Date(string='تا تاریخ', required=True)
    active = fields.Boolean(string='فعال', default=True)
    note = fields.Text(string='توضیحات')

    _rec_name = 'name'

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise ValidationError('تاریخ شروع سال مالی باید قبل از تاریخ پایان باشد.')

    @api.constrains('name', 'company_id')
    def _check_duplicate_year(self):
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
                ('name', '=', record.name),
            ], limit=1)
            if duplicate:
                raise ValidationError('این سال مالی قبلاً برای این شرکت ثبت شده است.')
