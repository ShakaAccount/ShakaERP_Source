from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CompanyOwnership(models.Model):
    _name = 'company.ownership'
    _description = 'Company Ownership Structure'
    _order = 'effective_date desc, id desc'

    name = fields.Char(string='عنوان فرم', required=True, default='درصد مالکیت سهام')
    owner_company_id = fields.Many2one(
        'res.company',
        string='شرکت مالک/هلدینگ',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    effective_date = fields.Date(
        string='تاریخ اثرگذاری',
        required=True,
        default=fields.Date.context_today,
    )
    fiscal_year_id = fields.Many2one(
        'company.fiscal.year',
        string='سال مالی',
        domain="[('company_id', '=', owner_company_id)]",
    )
    note = fields.Text(string='توضیحات')
    line_ids = fields.One2many(
        'company.ownership.line',
        'ownership_id',
        string='شرکت‌های زیرمجموعه',
        copy=True,
    )

class CompanyOwnershipLine(models.Model):
    _name = 'company.ownership.line'
    _description = 'Company Ownership Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='ترتیب', default=10)
    ownership_id = fields.Many2one(
        'company.ownership',
        string='فرم مالکیت',
        required=True,
        ondelete='cascade',
    )
    owner_company_id = fields.Many2one(
        related='ownership_id.owner_company_id',
        string='شرکت مالک',
        store=True,
        readonly=True,
    )
    subsidiary_company_id = fields.Many2one(
        'res.company',
        string='شرکت زیرمجموعه',
        required=True,
        ondelete='restrict',
        index=True,
    )
    shares_count = fields.Integer(string='تعداد سهام', required=True, default=0)
    ownership_percent = fields.Float(string='درصد مالکیت مستقیم', required=True, digits=(16, 4))
    note = fields.Text(string='توضیحات')

    _ownership_line_unique = models.Constraint(
        'unique(ownership_id, subsidiary_company_id)',
        'این شرکت قبلاً در همین فرم ثبت شده است.',
    )

    @api.constrains('owner_company_id', 'subsidiary_company_id')
    def _check_not_self_owned(self):
        for record in self:
            if record.owner_company_id and record.owner_company_id == record.subsidiary_company_id:
                raise ValidationError('شرکت مالک نمی‌تواند خودش را به‌عنوان زیرمجموعه انتخاب کند.')

    @api.constrains('shares_count', 'ownership_percent')
    def _check_ownership_values(self):
        for record in self:
            if record.shares_count < 0:
                raise ValidationError('تعداد سهام نمی‌تواند منفی باشد.')
            if record.ownership_percent < 0 or record.ownership_percent > 100:
                raise ValidationError('درصد مالکیت باید بین صفر تا صد باشد.')
