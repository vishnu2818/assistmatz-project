from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)  # Define the logger


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    quote_completed = fields.Boolean(string='Quote Completed',default=False)
    
    def action_mark_quote_completed(self):
        CrmStage = self.env['crm.stage']
        for order in self:
            opportunity = order.opportunity_id
            if not opportunity:
                raise ValidationError(_("This quotation is not linked to any opportunity."))

            if order.amount_total <= 0:
                raise ValidationError(_("Expected revenue must be greater than 0 to mark as 'Quote Completed'."))

            # mark the flag on order using write (safer)
            if not order.quote_completed:
                order.write({'quote_completed': True})

            # --- Find the 'Quote Completed' stage ---
            # Prefer a stage in the same pipeline/team as the opportunity, fallback to any match by name.
            team_id = opportunity.team_id.id if opportunity.team_id else False

            stage_domain = [('name', '=', 'Quote Completed')]
            if team_id:
                # try to find stage in same team first (team-specific pipeline)
                stage = CrmStage.search([('name', '=', 'Quote Completed'), ('team_id', 'in', [team_id, False])],
                                         order='sequence asc', limit=1)
            else:
                stage = CrmStage.search(stage_domain, limit=1)

            if not stage:
                # Better error than silent failure
                raise ValidationError(_("Cannot find CRM stage 'Quote Completed'. Please ensure stage exists."))

            # Only update if current stage is 'Quote Preparation' (or if you want to force update always, remove the check)
            # Find current stage name safely
            current_stage_name = opportunity.stage_id.name if opportunity.stage_id else False
            if current_stage_name == 'Quote Preparation':
                # use sudo() to avoid access-rights problems if this is called by non-admin user
                opportunity.sudo().write({'stage_id': stage.id})
            else:
                # optional: if you want to force move regardless of current stage, uncomment next line
                # opportunity.sudo().write({'stage_id': stage.id})

                # for now, do nothing if not in Quote Preparation; you can change behaviour if needed
                _logger = self.env['ir.logging']
                # we don't raise here — just log a warning to server logs
                _logger.sudo().create({
                    'name': 'action_mark_quote_completed',
                    'type': 'server',
                    'dbname': self._cr.dbname,
                    'message': "Order %s linked opportunity stage '%s' not 'Quote Preparation' — not moved." % (order.name, current_stage_name),
                    'path': 'sale.order.action_mark_quote_completed',
                    'level': 'WARNING',
                    'func': 'action_mark_quote_completed',
                    'line': '0',
                })

        return True




    @api.model
    def write(self, vals):

        if 'state' in vals:

            if vals['state'] == 'sent':
                for order in self:
                    if order.opportunity_id:

                        if order.opportunity_id.stage_id.name == 'Quote Completed':
                            if order.opportunity_id.expected_revenue <= 0:
                                raise ValidationError(
                                    "First Add the Product line and Update the Amount , Then only You can send the Quotation.")

                            res = super(SaleOrder, self).write(vals)
                            mapping = self.env['quotation.stage.mapping'].search(
                                [('sale_order_state', '=', order.state)], limit=1)
                            if mapping:
                                order.opportunity_id.stage_id = mapping.crm_lead_stage
                                return res
                        else:
                            raise ValidationError(
                                "The opportunity stage must be 'Quote Completed' to send the quotation.")

            if vals['state'] == 'sale':
                for order in self:
                    if order.opportunity_id:

                        if order.opportunity_id.stage_id.name in ['Expecting (60%)', 'Commit (90%)']:
                            res = super(SaleOrder, self).write(vals)
                            mapping = self.env['quotation.stage.mapping'].search(
                                [('sale_order_state', '=', order.state)], limit=1)
                            if mapping:
                                order.opportunity_id.stage_id = mapping.crm_lead_stage
                                return res
                        else:
                            raise ValidationError(
                                "The opportunity stage must be 'Expecting (60%)' or 'Commit (90%)' to confirm the sale order.")

        rec = super(SaleOrder, self).write(vals)
        for order in self:
            if order.opportunity_id:
                total_amount = sum(order.order_line.mapped('price_subtotal'))
                order.opportunity_id.expected_revenue = total_amount
            if order.quote_completed:
                if order.opportunity_id and order.opportunity_id.stage_id.name == 'Quote Preparation':
                    stage = self.env['crm.stage'].search([('name', '=', 'Quote Completed')])
                    if stage:
                        order.opportunity_id.stage_id = stage.id

        return rec






















