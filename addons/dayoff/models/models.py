from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError


class LeaveRequest(models.Model):
    _name = 'leave.request'
    _description = 'Leave Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # gives chatter + log for free
    _order = 'create_date desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    employee_id = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True,
        tracking=True, readonly=True,
    )
    date_from = fields.Date(string='From', required=True, tracking=True)
    date_to = fields.Date(string='To', required=True, tracking=True)
    reason = fields.Text(string='Reason', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True, required=True)

    admin_note = fields.Text(string='Admin Note', tracking=True)

    # --- Workflow actions ---

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Only draft requests can be submitted.")
            if rec.employee_id != self.env.user and not self.env.user.has_group('base.group_system'):
                raise AccessError("You can only submit your own leave request.")
            rec.state = 'submitted'
            rec.message_post(body=f"Leave request submitted by {rec.employee_id.name}.")

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError("Only submitted requests can be approved.")
            rec.state = 'approved'
            rec.message_post(body=f"Approved by {self.env.user.name}.")

    def action_reject(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError("Only submitted requests can be rejected.")
            rec.state = 'rejected'
            rec.message_post(body=f"Rejected by {self.env.user.name}.")

    def action_reset_to_draft(self):
        # optional: lets admin send it back for edits
        for rec in self:
            rec.state = 'draft'
            rec.message_post(body=f"Reset to draft by {self.env.user.name}.")

    def write(self, vals):
        for rec in self:
            is_admin = self.env.user.has_group('base.group_system') or self.env.user.has_group('leave_request.group_leave_admin')
            # Once submitted, only admins can edit (approve/reject/edit fields)
            if rec.state != 'draft' and not is_admin:
                # allow state-only changes performed via the action_* methods (they call write internally via field assignment)
                raise AccessError("This request has been submitted and can no longer be edited by you.")
            # Non-admins can only edit their own draft
            if rec.state == 'draft' and rec.employee_id != self.env.user and not is_admin:
                raise AccessError("You can only edit your own draft requests.")
        return super().write(vals)
