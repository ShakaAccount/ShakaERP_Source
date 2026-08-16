try:
    import jdatetime
except ImportError:
    jdatetime = None

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    calendar_type = fields.Selection(
        selection=[("gregorian", "Gregorian"), ("jalali", "Jalali (Persian)")],
        string="Calendar Type",
        default="gregorian",
        help="Controls which calendar system dates are displayed in "
        "throughout the interface for this user. Storage is always "
        "Gregorian; this only affects presentation.",
    )


class IrQweb(models.AbstractModel):
    """Small helper so QWeb report templates can print Jalali dates
    without touching every field individually. Storage stays Gregorian;
    this only formats the printed representation.

    Usage in a report template:
        <span t-esc="jalali_date(o.date_order)"/>
        <span t-esc="jalali_datetime(o.create_date)"/>
    """

    _inherit = "ir.qweb"

    def jalali_date(self, value, fmt="%Y/%m/%d"):
        if not value or jdatetime is None:
            return ""
        gdate = fields.Date.to_date(value)
        return jdatetime.date.fromgregorian(date=gdate).strftime(fmt)

    def jalali_datetime(self, value, fmt="%Y/%m/%d %H:%M"):
        if not value or jdatetime is None:
            return ""
        gdt = fields.Datetime.to_datetime(value)
        return jdatetime.datetime.fromgregorian(datetime=gdt).strftime(fmt)

    @api.model
    def _get_template_context_functions(self):
        # Whitelist our helpers so `t-esc="jalali_date(o.date_order)"`
        # is callable from inside QWeb report templates.
        return super()._get_template_context_functions() + [
            "jalali_date",
            "jalali_datetime",
        ]


class IrHttp(models.AbstractModel):
    """Custom fields on res.users are NOT automatically visible to the JS
    web client - they only reach the frontend if explicitly added to the
    session_info payload sent at boot. This is that wiring."""

    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        result["calendar_type"] = self.env.user.calendar_type
        return result
