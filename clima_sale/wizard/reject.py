from odoo import models, fields, api, _


class SaleOrderRejectWizard(models.TransientModel):
    _name = "sale.order.reject.wizard"
    _description = "Sale Order Reject Wizard"

    approval_id = fields.Many2one('sale.order.approve', required=True)
    rejection_reason = fields.Text("Rejection Reason", required=True)

    def action_reject_confirm(self):
        self.approval_id.rejection_reason = self.rejection_reason
        self.approval_id.action_reject()
        return {'type': 'ir.actions.act_window_close'}