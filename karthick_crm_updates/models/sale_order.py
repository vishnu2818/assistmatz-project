from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)  # Define the logger


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    quote_completed = fields.Boolean(string='Quote Completed',default=False)
    
    def action_mark_quote_completed(self):
        print("\n====== BUTTON CLICKED: action_mark_quote_completed ======\n")
        _logger.info("BUTTON CLICKED: action_mark_quote_completed")

        for order in self:
            print("Processing order:", order.id)
            _logger.info("Processing Sale Order ID: %s", order.id)

            # 1) Check opportunity
            opportunity = order.opportunity_id
            print("Opportunity:", opportunity)
            _logger.info("Opportunity found: %s", opportunity)

            if not opportunity:
                print("ERROR: No opportunity linked!")
                _logger.error("No opportunity linked to sale order %s", order.id)
                raise ValidationError(_("This quotation is not linked to any opportunity."))

            # 2) Validate amount
            print("Quotation Amount:", order.amount_total)
            _logger.info("Quotation Amount: %s", order.amount_total)

            if order.amount_total <= 0:
                print("ERROR: Amount is zero!")
                _logger.error("Amount is zero for order %s", order.id)
                raise ValidationError(_("Expected revenue must be greater than 0."))

            # 3) Mark boolean
            print("Marking quote_completed = True")
            _logger.info("Setting quote_completed TRUE for order %s", order.id)
            order.quote_completed = True

            # 4) Find CRM Stage
            print("Searching CRM stage 'Quote Completed'...")
            _logger.info("Searching CRM stage 'Quote Completed'")

            stage = self.env['crm.stage'].sudo().search([
                ('name', '=', 'Quote Completed')
            ], limit=1)

            print("Stage found:", stage)
            _logger.info("Stage search result: %s", stage)

            if not stage:
                print("ERROR: Stage not found!")
                _logger.error("CRM stage 'Quote Completed' not found")
                raise ValidationError(_("CRM stage 'Quote Completed' not found."))

            # 5) Update opportunity stage
            print("Updating opportunity stage...")
            _logger.info("Updating stage for opportunity %s", opportunity.id)

            opportunity.sudo().write({'stage_id': stage.id})

            print("Stage updated successfully!")
            _logger.info("Stage updated successfully for opportunity %s", opportunity.id)

        print("\n====== ACTION FINISHED SUCCESSFULLY ======\n")
        _logger.info("action_mark_quote_completed FINISHED SUCCESSFULLY")

        # reload UI
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
 



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
















