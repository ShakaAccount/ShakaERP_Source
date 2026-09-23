from odoo import fields, models


class CompanyBoardRole(models.Model):
    _name = 'company.board.role'
    _description = 'Company Board Role'
    _order = 'name'

    name = fields.Char(string='نقش در شرکت', required=True, index=True)
    active = fields.Boolean(string='فعال', default=True)
    description = fields.Text(string='توضیحات')

    _role_name_unique = models.Constraint(
        'unique(name)',
        'این نقش قبلاً ثبت شده است.',
    )


class CompanyBoardMember(models.Model):
    _name = 'company.board.member'
    _description = 'Company Board Member'
    _order = 'sequence, id'

    sequence = fields.Integer(string='ترتیب', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='شرکت',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='عضو هیئت‌مدیره',
        required=True,
        ondelete='restrict',
        index=True,
    )
    member_identifier = fields.Char(
        string='شماره ثبت عضو حقوقی/کد ملی',
        help='برای عضو حقیقی کد ملی و برای عضو حقوقی شماره ثبت را وارد کنید.',
    )
    company_type_id = fields.Many2one(
        'lookup.value',
        string='نوع شرکت',
        domain="[('type_id.code', '=', 'board_company_type')]",
        ondelete='restrict',
    )
    membership_type_id = fields.Many2one(
        'lookup.value',
        string='نوع عضویت',
        domain="[('type_id.code', '=', 'board_membership_type')]",
        ondelete='restrict',
    )
    legal_representative_name = fields.Char(string='نام نماینده عضو حقوقی')
    legal_representative_national_id = fields.Char(string='کد ملی نماینده عضو حقوقی')
    role_id = fields.Many2one(
        'company.board.role',
        string='نقش در شرکت',
        required=True,
        ondelete='restrict',
        index=True,
    )
    executive_status_id = fields.Many2one(
        'lookup.value',
        string='موظف/غیر موظف',
        domain="[('type_id.code', '=', 'board_executive_status')]",
        ondelete='restrict',
    )
    education_level_id = fields.Many2one(
        'lookup.value',
        string='مقطع تحصیلی',
        domain="[('type_id.code', '=', 'board_education_level')]",
        ondelete='restrict',
    )
    field_of_study = fields.Char(string='رشته تحصیلی')
    note = fields.Text(string='توضیحات')
    active = fields.Boolean(string='فعال', default=True)

    _member_role_unique = models.Constraint(
        'unique(company_id, partner_id, role_id)',
        'این عضو با همین نقش قبلاً برای شرکت ثبت شده است.',
    )

class ResCompany(models.Model):
    _inherit = 'res.company'

    board_member_ids = fields.One2many(
        'company.board.member',
        'company_id',
        string='اعضای هیئت‌مدیره',
    )
