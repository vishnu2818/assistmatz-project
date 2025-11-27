from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)  # Define the logger


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    quote_completed = fields.Boolean(string='Quote Completed',default=False)
    
    def action_mark_quote_completed(self):
        for order in self:
            # 1. Ensure Quotation is linked to Opportunity
            opportunity = order.opportunity_id
            if not opportunity:
                # Rationale: Stops if no linked opportunity.
                raise ValidationError("This quotation is not linked to any opportunity.")
            
            # 2. Ensure Amount > 0
            if order.amount_total <= 0:
                # Rationale: Ensures a valid quote value.
                raise ValidationError("Expected revenue must be greater than 0 to mark as 'Quote Completed'.")
            
            # 3. Mark the Boolean (ensures it's only written once)
            if not order.quote_completed:
                order.write({'quote_completed': True})
            
            # 4. Get "Quote Completed" Stage (Stage to move TO)
            # Assuming 'crm.stage' is the correct model for CRM pipeline stages
            stage = self.env['crm.stage'].search([('name', '=', 'Quote Completed')], limit=1)
            if not stage:
                raise ValidationError("CRM stage 'Quote Completed' not found. Please create it in CRM settings.")
            
            # 5. Update Opportunity Stage using sudo() (The core stage change)
            opportunity.sudo().write({'stage_id': stage.id})
                
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












