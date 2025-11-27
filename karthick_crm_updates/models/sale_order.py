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
    
            # --- validations (your original checks) ---
            if not opportunity:
                raise ValidationError("This quotation is not linked to any opportunity.")
            if order.amount_total <= 0:
                raise ValidationError("Expected revenue must be greater than 0 to mark as 'Quote Completed'.")
    
            # --- keep your flag behavior ---
            if not order.quote_completed:
                order.write({'quote_completed': True})
    
            # ====== the two lines you asked to add BEFORE changing stage ======
            current_stage = opportunity.stage_id                # 1) capture current stage
            prep_stage = CrmStage.search([('name', 'ilike', 'Quote Preparation')], limit=1)  # 2) find the "Quote Preparation" stage
            # =================================================================
    
            # find the target "Quote Completed" stage (try exact then ilike fallback)
            target_stage = CrmStage.search([('name', '=', 'Quote Completed')], limit=1) or \
                           CrmStage.search([('name', 'ilike', 'Quote Completed')], limit=1)
    
            if not target_stage:
                # fail loud so you know to create the stage or fix the name
                raise ValidationError("CRM stage 'Quote Completed' not found. Please create it or update the stage name used in code.")
    
            # Only move when current stage is Quote Preparation (safety)
            if prep_stage and current_stage and current_stage.id == prep_stage.id:
                opportunity.write({'stage_id': target_stage.id})
                _logger.info(
                    "Moved opportunity %s from '%s' to '%s' (triggered by Sale Order %s).",
                    opportunity.id, current_stage.name, target_stage.name, order.id
                )
            else:
                _logger.info(
                    "No stage change for opportunity %s (current: '%s'). Expected 'Quote Preparation' to move to 'Quote Completed'.",
                    opportunity.id, current_stage.name if current_stage else 'None'
                )
    
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

























