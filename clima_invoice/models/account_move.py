from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_approval_ids = fields.One2many('invoice.approve', 'move_id')

    def action_post(self):

        invoice_manager_group = self.env.ref('clima_invoice.group_invoice_manager')
        gm_group = self.env.ref('clima_sale.group_general_manager')

        # Allow GM final action (from GM approval button)
        if self.env.context.get('from_gm_approve') or self.env.user.has_group('clima_sale.group_general_manager') or self.env.user.has_group('clima_invoice.group_invoice_manager'):
            return super().action_post()

        # --- 1. Check if approval exists already ---
        approvals = self.invoice_approval_ids

        # Case 1: No approval records → create fresh approval workflow
        if not approvals:
            self._create_initial_approvals(invoice_manager_group, gm_group)
            # raise UserError("Approval workflow created. Please wait for approvals.")

        # --- 2. There are approval records → check status ---
        approved = approvals.filtered(lambda a: a.state == 'approved')
        rejected = approvals.filtered(lambda a: a.state == 'rejected')
        pending = approvals.filtered(lambda a: a.state == 'pending')

        # If all approved → Allow posting
        if len(approved) == 2:
            return super().action_post()

        # If any rejected → re-create approval ONLY for those rejected users
        if rejected:
            self._regenerate_rejected_approvals(rejected)
            # raise UserError("Some approvals were rejected. New approval request created for rejected approvers.")

        # If any pending → stop
        if pending:
            raise UserError("Approval is still pending. Cannot post invoice.")

        # raise UserError("Unknown approval state.")

    # -----------------------------
    # Create Initial Approval Records
    # -----------------------------
    def _create_initial_approvals(self, invoice_manager_group, gm_group):
        im_user = invoice_manager_group.user_ids[:1]
        gm_user = gm_group.user_ids[:1]

        if not im_user or not gm_user:
            raise UserError("Approvers not configured properly.")

        # Create IM approval
        self.env['invoice.approve'].create({
            'move_id': self.id,
            'approver_id': im_user.id,
            'approval_level': 'invoice_manager',
        })

        # Create GM approval
        self.env['invoice.approve'].create({
            'move_id': self.id,
            'approver_id': gm_user.id,
            'approval_level': 'gm',
        })

    # -----------------------------
    # Re-generate approvals for rejected users
    # -----------------------------
    def _regenerate_rejected_approvals(self, rejected_records):
        for rec in rejected_records:
            self.env['invoice.approve'].create({
                'move_id': self.id,
                'approver_id': rec.approver_id.id,
                'approval_level': rec.approval_level,
            })

