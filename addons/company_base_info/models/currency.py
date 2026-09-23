from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CompanyCurrency(models.Model):
    _name = 'company.currency'
    _description = 'Company Currency'
    _order = 'name'

    name = fields.Char(string='عنوان ارز', required=True, index=True)
    code = fields.Char(string='کد ارز', index=True)
    active = fields.Boolean(string='فعال', default=True)
    note = fields.Text(string='توضیحات')

    _currency_name_unique = models.Constraint(
        'unique(name)',
        'این عنوان ارز قبلاً ثبت شده است.',
    )


class CompanyCurrencyIntroduction(models.Model):
    _name = 'company.currency.introduction'
    _description = 'Company Currency Introduction'
    _order = 'registration_date desc, id desc'

    company_id = fields.Many2one(
        'res.company',
        string='شرکت',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    fiscal_year_id = fields.Many2one(
        'company.fiscal.year',
        string='سال مالی',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    registration_date = fields.Date(
        string='تاریخ ثبت',
        required=True,
        default=fields.Date.context_today,
    )
    line_ids = fields.One2many(
        'company.currency.introduction.line',
        'introduction_id',
        string='ارزها',
        copy=True,
    )
    note = fields.Text(string='توضیحات')


class CompanyCurrencyIntroductionLine(models.Model):
    _name = 'company.currency.introduction.line'
    _description = 'Company Currency Introduction Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='ترتیب', default=10)
    introduction_id = fields.Many2one(
        'company.currency.introduction',
        string='معرفی ارز',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(
        'company.currency',
        string='عنوان ارز',
        required=True,
        ondelete='restrict',
    )
    conversion_type_id = fields.Many2one(
        'lookup.value',
        string='نوع تبدیل ارز',
        required=True,
        domain="[('type_id.code', '=', 'currency_conversion_type')]",
        ondelete='restrict',
    )
    rial_value_per_unit = fields.Float(
        string='ارزش ریالی هر واحد ارز',
        required=True,
        digits=(16, 4),
    )

    _currency_line_unique = models.Constraint(
        'unique(introduction_id, currency_id, conversion_type_id)',
        'این ارز با همین نوع تبدیل قبلاً در این فرم ثبت شده است.',
    )

    @api.constrains('rial_value_per_unit')
    def _check_rial_value(self):
        for record in self:
            if record.rial_value_per_unit <= 0:
                raise ValidationError('ارزش ریالی هر واحد ارز باید بیشتر از صفر باشد.')
