from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)  # Define the logger


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    quote_completed = fields.Boolean(string='Quote Completed',default=False)
    
    def action_mark_quote_completed(self):
        """Button action: validate, set quote_completed flag and move linked opportunity
           from 'Quote Preparation' -> 'Quote Completed' (only if currently in 'Quote Preparation')."""
        CrmStage = self.env['crm.stage']

        # --- TWO LINES you asked for: locate the stages once (before loop) ---
        stage_quote_preparation = CrmStage.search([('name', '=', 'Quote Preparation')], limit=1)
        stage_quote_completed   = CrmStage.search([('name', '=', 'Quote Completed')], limit=1)

        # If stages missing, raise so admin can create them or adjust names
        if not stage_quote_preparation or not stage_quote_completed:
            raise UserError(_("CRM stages 'Quote Preparation' and/or 'Quote Completed' were not found. "
                               "Make sure they exist with exact names or update the code to use correct names."))

        for order in self:
            opportunity = order.opportunity_id

            # VALIDATIONS
            if not opportunity:
                raise ValidationError(_("This quotation is not linked to any opportunity."))
            if order.amount_total <= 0:
                raise ValidationError(_("Expected revenue must be greater than 0 to mark as 'Quote Completed'."))

            # MARK QUOTE COMPLETED FLAG (if not already)
            if not order.quote_completed:
                order.quote_completed = True

            # --- check current stage and change it if it is exactly 'Quote Preparation' ---
            # (we grab current stage once to make sure it's comparable)
            current_stage = opportunity.stage_id
            if current_stage and current_stage.id == stage_quote_preparation.id:
                # write() is safer for many frameworks (triggers ORM write hooks)
                opportunity.write({'stage_id': stage_quote_completed.id})
                # optional: post a message to chatter for traceability
                opportunity.message_post(body=_("Moved to '%s' because quotation %s was marked Quote Completed.")
                                               % (stage_quote_completed.name, order.name))

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



























