from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrderApprove(models.Model):
    _name = 'sale.order.approve'
    _rec_name = 'sale_order_id'
    _description = 'Sale Order Approve'

    sale_order_id = fields.Many2one('sale.order', required=True)
    requested_by = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user)
    gm_id = fields.Many2one('res.users', string="General Manager", required=False)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')
    rejection_reason = fields.Text("Rejection Reason")

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'

            # Temporarily mark order as GM-approved
            rec.sale_order_id.is_confirmed = True

            # Now confirm as system user but bypass approval logic
            rec.sale_order_id.with_context(from_gm_approve=True).action_confirm()

    def action_reject(self):
        for rec in self:
            if not rec.rejection_reason:
                raise UserError("Please provide a rejection reason.")
            rec.sale_order_id.state = 'sent'  # move back to Quotation Sent
            rec.state = 'rejected'

    def action_open_reject_wizard(self):
        return {
            'name': "Reject Sale Order",
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_approval_id': self.id},
        }


class SaleOrder(models.Model):
    _inherit = "sale.order"

    gm_approval_id = fields.One2many('sale.order.approve', 'sale_order_id')
    is_confirmed = fields.Boolean(default=False)

    def write(self, vals):
        res = super().write(vals)

        # Check if state changed to 'sent'
        if 'state' in vals and vals.get('state') == 'sent':
            for order in self:
                order._create_gm_approval()

        return res

    def _create_gm_approval(self):
        """Creates GM approval record only once"""
        gm_group = self.env.ref('clima_sale.group_general_manager')

        # Prevent duplicates
        if self.gm_approval_id.filtered(lambda r: r.state == 'pending'):
            return

        gm_users = gm_group.user_ids
        if not gm_users:
            raise UserError(_("No GM assigned in group General Manager."))

        # Create approval
        self.env['sale.order.approve'].create({
            'sale_order_id': self.id,
            'gm_id': gm_users[0].id,
            'state': 'pending',
        })

        self.is_confirmed = False

        # Rainbow effect only for UI calls
        if not self._context.get('from_gm_approve'):
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'Request sent to GM for approval.',
                    'type': 'rainbow_man',
                }
            }

    def action_confirm(self):
        """Control confirmation process"""

        # GM is allowed to confirm
        if self.env.context.get('from_gm_approve') or \
           self.env.user.has_group('clima_sale.group_general_manager'):
            return super().action_confirm()

        # Others: ensure GM approved
        if self.gm_approval_id.filtered(lambda a: a.state == 'rejected'):
            raise UserError(_("Quotation has Rejected by GM please re send the quotation."))
        if not self.gm_approval_id.filtered(lambda a: a.state == 'approved'):
            raise UserError(_("Quotation cannot be confirmed until GM approves."))

        return super().action_confirm()


