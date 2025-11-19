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

    is_deadline_overdue = fields.Boolean(
        compute="_compute_is_deadline_overdue",
        store=False
    )
    
    @api.depends('date_deadline')
    def _compute_is_deadline_overdue(self):
        today = fields.Date.today()
        for lead in self:
            lead.is_deadline_overdue = bool(lead.date_deadline and lead.date_deadline <= today)

   
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


    def _check_required_fields_on_stage_change(self):
        """
        Checks mandatory fields before moving out of 'New' stage.
        Required fields: partner_id, email_from, phone, x_studio_job_type, 
        x_studio_project, date_deadline.
        """
        self = self.ensure_one()
        missing = []

        if not self.partner_id:
            missing.append(_('Customer'))
        if not self.email_from:
            missing.append(_('Email'))
        if not self.phone:
            missing.append(_('Phone'))
        if not self.x_studio_job_type:
            missing.append(_('Job Type')) 
        if not self.x_studio_project:
            missing.append(_('Project'))
        if not self.date_deadline:
            missing.append(_('Forecast Date'))

        return missing

    # --- Overridden write Method ---
    def write(self, vals):
        """
        Overrides the write method to enforce custom stage transition and 
        field validation rules.
        """
        
        user = self.env.user
        is_admin = user.has_group('base.group_system') 
        LeadStage = self.env['crm.stage']
        SaleOrder = self.env['sale.order']
        
        for lead in self:
            old_stage_name = lead.stage_id.name
            old_stage_sequence = lead.stage_id.sequence

            # 1. Check Stage Change Validations
            if 'stage_id' in vals:
                new_stage = LeadStage.browse(vals['stage_id'])
                new_stage_sequence = new_stage.sequence
                quotation = None
                
                if new_stage.name != 'New':
                    quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
                
                _logger.warning(f"This is old_stage_name {old_stage_name} and new stage {new_stage.name} ")

                # --- VALIDATION LOGIC FOR NON-ADMIN USERS ---
                if not is_admin:
                    # Backward movement restriction
                    if new_stage_sequence < old_stage_sequence:
                        allowed_backward = (
                            old_stage_name == 'Hold' and 
                            new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']
                        )
                        if not allowed_backward:
                            raise ValidationError("You cannot move to an Backward stage.")

                    # Quote Submitted
                    if new_stage.name == 'Quote Submitted':
                        if old_stage_name != 'Quote Completed' or not quotation or quotation.state != 'sent':
                            raise ValidationError("Only records in 'Quote Completed' with a valid 'sent' quotation can move to 'Quote Submitted'.")

                    # Quote Completed
                    if new_stage.name == 'Quote Completed':
                        if old_stage_name != 'Quote Preparation' or not quotation:
                            raise ValidationError("Only records in 'Quote Preparation' with a valid quotation can move to Quote Completed.")
                        # NOTE: Requires 'quote_completed' field on sale.order model
                        if not quotation.quote_completed: 
                            raise ValidationError("Please Use Quote Completed Button In Quotation for Move to Quote Completed")
                    
                    # Quote Preparation
                    if new_stage.name == 'Quote Preparation':
                        if old_stage_name != 'New':
                            raise ValidationError("Only records in 'New' can move to 'Quote Preparation'.")

                    # Advanced stages
                    if new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Won']:
                        if old_stage_name in ['Quote Completed', 'New', 'Quote Preparation']:
                            raise ValidationError(f"Only 'Quote Submitted' records can move to '{new_stage.name}'.")

                    # Hold stage entry restriction
                    if new_stage.name == 'Hold':
                        if old_stage_name not in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']:
                            raise ValidationError(f"Only ['Quote Submitted' , 'Expecting (60%)', 'Commit (90%)'] records can move to '{new_stage.name}'.")

                    # Quotation state requirement for Expecting/Commit/Lost
                    if new_stage.name in ['Expecting (60%)', 'Commit (90%)','Lost' ]:
                        if not quotation or quotation.state != 'sent':
                            raise ValidationError( f"Only leads with a 'sent' quotation can be moved to '{new_stage.name}'.")
                            
                    # Hold stage exit restriction
                    if old_stage_name == 'Hold' and new_stage.name not in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']:
                        raise ValidationError("From 'Hold', you can move only to 'Expecting (60%)', 'Commit (90%)', 'Quote Submitted' ")

                    # Not in Scope (Lost)
                    if new_stage.name == 'Not in Scope':
                        if old_stage_name != 'Quote Preparation':
                             raise ValidationError("Please contact Administration. The 'Not in Scope' stage only accepts leads from the 'Quote Prepation' stage.")

                    # Won stage restriction
                    if old_stage_name == 'Won' and new_stage.name != 'Won':
                        raise ValidationError("Only Admin can move records from the 'Won' stage to another stage.")

                # --- VALIDATION LOGIC FOR ALL USERS (Admin/Non-Admin) ---
                if old_stage_name == 'New' and new_stage.name != 'New':
                    missing_fields = lead._check_required_fields_on_stage_change()
                    if missing_fields:
                        raise ValidationError(
                            "Please fill the following fields before moving to 'Quote Preparation':\n- " + "\n- ".join(missing_fields)
                        )

                # Forecast requirement for Commit 90%
                if new_stage.name == 'Commit (90%)':
                    forecast_valid = vals.get('date_deadline') or lead.date_deadline
                    if not forecast_valid:
                        raise ValidationError("Forecast Date required to move to this stage.")

                # Won stage
                if new_stage.name == 'Won':
                    if quotation and quotation.state == 'sale':
                        # Check PO fields (custom fields)
                        po_date = vals.get('po_date') or lead.po_date
                        po_ref = vals.get('po_ref') or lead.po_ref
                        po_attachment = vals.get('po_attachment') or lead.po_attachment

                        if not po_date and not po_ref and not po_attachment:
                            raise ValidationError("Please fill at least one of the following fields before moving to 'Won': PO Date, PO Reference, or PO Attachment.")
                    else:
                        raise ValidationError("You connot move manually to 'Won' stage. Please use the 'Confirm' button in Quotation to move to 'Won' stage.")

            # 2. Check Lost/Archiving Logic
            if 'active' in vals and not vals['active']:
                quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
                if not quotation:
                    raise ValidationError("You cannot manually move to the 'Lost' stage when the Lead has no Quotation.")
                
                lost_stage = LeadStage.search([('name', '=', 'Lost')], limit=1)
                if lost_stage:
                    vals['stage_id'] = lost_stage.id

            # 3. Check Forecast Date Validation
            if 'date_deadline' in vals and vals['date_deadline']:
                date_str = vals['date_deadline']
                new_date = fields.Date.from_string(date_str) if isinstance(date_str, str) else date_str
                
                if new_date and new_date < fields.Date.today():
                    raise ValidationError("Forecast date cannot be in the past.")

        # Execute the database write operation
        record = super().write(vals)

        # --- Post-Write Logic (Auto-move from 'New') ---
        for lead in self:
            if lead.stage_id.name == 'New':
                missing_fields = lead._check_required_fields_on_stage_change()
                if not missing_fields:
                    stage = LeadStage.search([('name', '=', 'Quote Preparation')], limit=1)
                    if stage:
                        # Write the stage ID directly to skip re-validation in this case
                        lead.stage_id = stage.id
                        
        return record

   

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


    


        








































































































