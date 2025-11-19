from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date 

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # --- 1. Standard Fields Overridden (Mandatory Status) ---
    email_from = fields.Char(
        string="Email",
        required=True,
    )
    phone = fields.Char(
        string="Phone",
        required=True,
    )
    is_warranty = fields.Boolean(string="Warranty", default=False)
    brand = fields.Char(string="Brand")
    serial_no = fields.Char(string="Serial No")
    purchase_date = fields.Date(string="Purchase Date")
    warranty_close_date = fields.Date(string="Warranty Close Date")
    extended_warranty_date = fields.Date(string="Extended Warranty Date")

    # --- 3. Computed Fields for UI/Logic ---
    
    # Required for Forecast Date highlighting
    # is_overdue = fields.Boolean(
    #     string="Is Overdue",
    #     compute="_compute_is_overdue",
    #     store=False
    # )
    
    # FIX for XML Error: This field MUST exist on crm.lead if referenced in crm_lead.xml
    show_warranty_tab = fields.Boolean(
        string="Show Warranty Tab",
        compute="_compute_show_warranty_tab",
        store=True,
    )
    x_studio_po_date = fields.Date(string="PO Date")
    x_studio_po_attachment = fields.Binary(string="PO Attachment") # Assuming Binary/Attachment type
    x_studio_po_ref = fields.Char(string="PO Reference")


    # @api.depends('order_ids.amount_total')
    # def _compute_expected_revenue_from_quote(self):
    #     for lead in self:
    #         if lead.order_ids:
    #             lead.expected_revenue = sum(lead.order_ids.mapped('amount_total'))
    #         else:
    #             lead.expected_revenue = 0.0

    is_forecast_overdue = fields.Boolean(
        compute="_compute_is_forecast_overdue",
        store=False,
    )

    def _compute_is_forecast_overdue(self):
        today = date.today()
        for rec in self:
            rec.is_forecast_overdue = False
            if rec.date_deadline and rec.date_deadline <= today:
                rec.is_forecast_overdue = True
   
    @api.constrains('stage_id')
    def _check_lost_stage(self):
        lost_stage = self.env['crm.stage'].search([('name', '=', 'Lost')], limit=1)
        not_in_scope_stage = self.env['crm.stage'].search([('name', '=', 'Not in Scope')], limit=1)

        for lead in self:
            if lost_stage and lead.stage_id == lost_stage:
                # Check if any quotation exists
                quotation = self.env['sale.order'].search([('opportunity_id', '=', lead.id)], limit=1)
                if not quotation:
                    # Prevent moving to Lost
                    raise ValidationError(_(
                        "Cannot move to 'Lost' because there is no quotation attached.\n"
                        "Please move it to 'Not in Scope' instead."
                    ))
    
    @api.model
    def create(self, vals_list):
        # Odoo 19 supports multi-create automatically
        leads = super().create(vals_list)
        leads._validate_stage_change()
        return leads

    def write(self, vals):
        """Covers every stage change — Kanban drag, Lost wizard, manual edit, etc."""
        stage_changed = 'stage_id' in vals
        res = super().write(vals)
        if stage_changed:
            self._validate_stage_change()
        return res

    def _validate_stage_change(self):
        """Central validation for all stage changes."""
        for lead in self:
            stage = lead.stage_id
            if not stage:
                continue

            # Count linked quotations
            quote_count = self.env["sale.order"].search_count([
                ("opportunity_id", "=", lead.id)
            ])

            # Lost → needs at least one quotation
            if stage.name.lower().strip() == "lost" and quote_count == 0:
                raise UserError("You cannot move this opportunity to 'Lost' because no quotation is attached.")

            # Not in Scope → only allowed if there are no quotations
            if stage.name.lower().strip() == "not in scope" and quote_count > 0:
                raise UserError("You cannot move to 'Not in Scope' because a quotation already exists.")
    
    @api.constrains('stage_id')
    def _check_sor_details_on_won(self):
        """
        Validates all three SOR Details fields when the opportunity's stage_id 
        changes to ANY stage flagged as 'Won' (even manually created ones).
        """
        
        for lead in self:
            # Check only records whose new stage is flagged as 'Won' in the database.
            if lead.stage_id.is_won: 
                
                # List of mandatory fields and their user-friendly labels
                required_sor_fields = {
                    'x_studio_po_date': 'PO Date',
                    'x_studio_po_attachment': 'PO Attachment',
                    'x_studio_po_ref': 'PO Reference',
                }
                
                missing_fields = []
                
                for field_name, field_label in required_sor_fields.items():
                    # Check the current value of the field on the record
                    if not lead[field_name]:
                        missing_fields.append(field_label)
                            
                if missing_fields:
                    # Raise an error, preventing the save operation and stage change
                    raise ValidationError(
                        _("The following SOR Details are mandatory to move the opportunity to the 'Won' stage:\n- {}")
                        .format("\n- ".join(missing_fields))
                    )
    # --- Compute Methods ---
    
    @api.depends('is_warranty')
    def _compute_show_warranty_tab(self):
        """Computes the visibility flag based on the warranty checkbox."""
        for rec in self:
            rec.show_warranty_tab = rec.is_warranty

    # --- Override Methods ---

    def _prepare_sale_order_values(self, partner):
        """Overrides method to pass all warranty fields to the new Sale Order."""
        values = super(CrmLead, self)._prepare_sale_order_values(partner)
        
        transfer_fields = [
            'is_warranty', 'brand', 'serial_no', 'purchase_date', 
            'warranty_close_date', 'extended_warranty_date'
        ]
        
        for field in transfer_fields:
            if self[field]:
                values[field] = self[field]
                
        return values

    @api.constrains('stage_id', 'date_deadline')
    def _check_forecast_date_for_probable(self):
        """
        Block moving a lead into the 'Probable Order' stage unless date_deadline exists.
        Constrains run after the write/create and will rollback the transaction if violated.
        """
        for lead in self:
            if not lead.stage_id:
                continue
            # Option A: name-based (quick)
            if lead.stage_id.name == 'Probable Order' and not lead.date_deadline:
                raise ValidationError(
                    _("Please set a Forecast Date (Deadline) before moving to the 'Probable Order' stage.")
                )




        
    def write(self, vals):
        for lead in self:
            if 'stage_id' in vals:
                new_stage = self.env['crm.stage'].browse(vals['stage_id'])
                if new_stage.name == 'Won':
                    quotations = lead.order_ids
                    sale_quotations = quotations.filtered(lambda q: q.state == 'sale')
                    if sale_quotations:
                        if not (lead.x_studio_po_date  or lead.x_studio_po_ref or lead.x_studio_po_attachment):
                            raise ValidationError(_(
                                "Please fill at least one of the following fields before moving to 'Won': "
                                "PO Date, PO Reference, or PO Attachment."
                            ))
                    else:
                        raise ValidationError(_(
                            "You cannot move manually to 'Won' stage. "
                            "Please use the 'Confirm' button in Quotation to move to 'Won' stage."
                        ))
        return super(CrmLead, self).write(vals)

# class CrmLeadLost(models.TransientModel):
#     _inherit = 'crm.lead.lost'

#     @api.model
#     def action_lost_reason_apply(self):
#         """Validate before marking opportunity as Lost."""
#         leads = self.env['crm.lead'].browse(self.env.context.get('active_ids', []))
#         for lead in leads:
#             quote_count = self.env['sale.order'].search_count([('opportunity_id', '=', lead.id)])
#             if quote_count == 0:
#                 raise UserError("You cannot move this opportunity to 'Lost' because no quotation is attached.")
#         return super().action_lost_reason_apply()


    


        




































































































