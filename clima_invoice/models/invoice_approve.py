from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InvoiceApprove(models.Model):
    _name = "invoice.approve"
    _description = "Invoice Approval"
    _rec_name = 'move_id'

    move_id = fields.Many2one('account.move', required=True)
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user)

    approver_id = fields.Many2one('res.users', string="Approver")
    approval_level = fields.Selection([
        ('invoice_manager', 'Invoice Manager'),
        ('gm', 'General Manager')
    ], required=True)

    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='pending')

    rejection_reason = fields.Text("Rejection Reason")

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'

            move = rec.move_id

            # Fetch all approval records for the invoice
            approvals = move.invoice_approval_ids

            # Check if BOTH approvals exist and are approved
            im_approved = approvals.filtered(
                lambda a: a.approval_level == 'invoice_manager' and a.state == 'approved'
            )
            gm_approved = approvals.filtered(
                lambda a: a.approval_level == 'gm' and a.state == 'approved'
            )

            # If both approved → post the invoice
            if im_approved and gm_approved:
                move.with_context(from_gm_approve=True).action_post()

    def action_reject(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Invoice',
            'res_model': 'invoice.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_approval_id': self.id,
            }
        }
