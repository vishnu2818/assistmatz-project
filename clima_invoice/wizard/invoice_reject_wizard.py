from odoo import models, fields, api, _
from odoo.exceptions import UserError

class InvoiceRejectWizard(models.TransientModel):
    _name = 'invoice.reject.wizard'
    _description = 'Invoice Rejection Wizard'

    rejection_reason = fields.Text("Rejection Reason", required=True)
    approval_id = fields.Many2one('invoice.approve')

    def action_confirm_reject(self):
        if not self.approval_id:
            raise UserError("Approval record missing.")

        self.approval_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason
        })

        # Do NOT post invoice — just return to draft
        self.approval_id.move_id.state = 'draft'
