from odoo import models, api, exceptions, fields
from odoo.exceptions import ValidationError, UserError
import datetime
from collections import defaultdict
from odoo.tools.float_utils import float_is_zero
import re
import logging
_logger = logging.getLogger(__name__)  # Define the logger


class Lead(models.Model):
    _inherit = 'crm.lead'


    expected_quotation_date = fields.Date( string='Quote Expected On' )
    project_id = fields.Many2one('project.project', string='Project')
 


   


    @api.onchange('stage_id')
    def _onchange_stage_restrict_quote_completed(self):
        if self.stage_id and self.stage_id.name == 'Quote Completed':
            raise UserError("Manual move to 'Quote Completed' stage is restricted.")



    def _check_required_fields_on_stage_change(self):
        missing_fields = []
        for lead in self:
            if not lead.partner_id:
                missing_fields.append("Customer")
            if not lead.x_studio_job_type:
                missing_fields.append("Job Type")

            if not lead.x_studio_project:
                missing_fields.append("Project")

            if not lead.email_from:
                missing_fields.append("Email")

            if not lead.phone:
                missing_fields.append("Phone")
                
            if not lead.date_deadline:
                missing_fields.append("Forecast Date")
      

        return missing_fields






    def write(self, vals):
        user = self.env.user
        is_admin = user.has_group('base.group_system')
        LeadStage = self.env['crm.stage']
        SaleOrder = self.env['sale.order']
    
        # ---------------------------------------------------------
        # 1️⃣ AUTO STAGE UPDATE – NEW → QUOTE PREPARATION
        # ---------------------------------------------------------
        for lead in self:
            if lead.stage_id.name == 'New':
                missing_fields = lead._check_required_fields_on_stage_change()
    
                # All mandatory fields filled AND user not manually changing stage
                if not missing_fields and 'stage_id' not in vals:
                    next_stage = LeadStage.search([('name', '=', 'Quote Preparation')], limit=1)
                    if next_stage:
                        vals['stage_id'] = next_stage.id
        # ---------------------------------------------------------
        # END AUTO STAGE BLOCK
        # ---------------------------------------------------------
    
        # ---------------------------------------------------------
        # 2️⃣ VALIDATIONS ON MANUAL STAGE CHANGE
        # ---------------------------------------------------------
        for lead in self:
            old_stage_name = lead.stage_id.name
            old_stage_sequence = lead.stage_id.sequence
    
            if 'stage_id' in vals:
                new_stage = LeadStage.browse(vals['stage_id'])
                new_stage_sequence = new_stage.sequence
    
                quotation = None
                if new_stage.name != 'New':
                    quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
    
                # ADMIN CAN DO ANYTHING — skip restrictions
                if not is_admin:
    
                    # ---------- BLOCK BACKWARD ----------
                    if new_stage_sequence < old_stage_sequence:
                        if not (old_stage_name == 'Hold' and new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']):
                            raise ValidationError("You cannot move to a backward stage.")
    
                    # ---------- QUOTE SUBMITTED ----------
                    if new_stage.name == 'Quote Submitted':
                        if (old_stage_name != 'Quote Completed' or not quotation or quotation.state != 'sent'):
                            raise ValidationError("Only records in 'Quote Completed' with a valid 'sent' quotation can move to 'Quote Submitted'.")
    
                    # ---------- QUOTE COMPLETED ----------
                    if new_stage.name == 'Quote Completed':
                        if old_stage_name != 'Quote Preparation' or not quotation:
                            raise ValidationError("Only records in 'Quote Preparation' with a valid quotation can move to Quote Completed.")
                        if not quotation.quote_completed:
                            raise ValidationError("Use 'Quote Completed' button in the quotation to move to this stage.")
    
                    # ---------- QUOTE PREPARATION ----------
                    if new_stage.name == 'Quote Preparation':
                        if old_stage_name != 'New':
                            raise ValidationError("Only 'New' records can move to 'Quote Preparation'.")
    
                    # ---------- ADVANCED STAGES ----------
                    if new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Won']:
                        if old_stage_name in ['Quote Completed', 'New', 'Quote Preparation']:
                            raise ValidationError(f"Only 'Quote Submitted' records can move to '{new_stage.name}'.")
    
                    # ---------- HOLD ----------
                    if new_stage.name == 'Hold':
                        if old_stage_name not in ['Quote Submitted', 'Expecting (60%)', 'Commit (90%)']:
                            raise ValidationError("Only ['Quote Submitted', 'Expecting (60%)', 'Commit (90%)'] can move to Hold.")
    
                    # ---------- EXPECTING / COMMIT / LOST ----------
                    if new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Lost']:
                        if not quotation or quotation.state != 'sent':
                            raise ValidationError(f"Only leads with a 'sent' quotation can move to '{new_stage.name}'.")
    
                    # ---------- FROM HOLD ----------
                    if old_stage_name == 'Hold':
                        if new_stage.name not in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']:
                            raise ValidationError("From Hold, you can move only to Expecting (60%), Commit (90%), Quote Submitted.")
    
                    # ---------- NOT IN SCOPE ----------
                    if new_stage.name == 'Not in Scope':
                        if old_stage_name != 'Quote Preparation':
                            raise ValidationError("Only leads in 'Quote Preparation' can move to 'Not in Scope'.")
    
                    # ---------- WON RESTRICTION ----------
                    if old_stage_name == 'Won' and new_stage.name != 'Won':
                        raise ValidationError("Only Admin can move records out of 'Won' stage.")
    
                # ---------- FORECAST DATE REQUIRED FOR COMMIT ----------
                if new_stage.name == 'Commit (90%)':
                    if not lead.date_deadline:
                        raise ValidationError("Forecast Date is required to move to this stage.")
    
                # ---------- WON VALIDATION ----------
                if new_stage.name == 'Won':
                    if quotation and quotation.state == 'sale':
                        if not lead.po_date and not lead.po_ref and not lead.po_attachment:
                            raise ValidationError("Please fill PO Date / PO Reference / PO Attachment before moving to 'Won'.")
                    else:
                        raise ValidationError("Cannot move manually to 'Won'. Use the 'Confirm' button in Quotation.")
    
            # ---------- LOST STAGE BLOCK ----------
            if 'active' in vals and not vals['active']:
                quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
                if not quotation:
                    raise ValidationError("You cannot move to Lost when no quotation exists.")
                lost_stage = LeadStage.search([('name', '=', 'Lost')], limit=1)
                vals['stage_id'] = lost_stage.id if lost_stage else vals.get('stage_id')
    
            # ---------- FORECAST DATE CHECK ----------
            if 'date_deadline' in vals:
                new_date = fields.Date.to_date(vals['date_deadline'])
                if new_date < fields.Date.today():
                    raise ValidationError("Forecast date cannot be in the past.")
    
        # ---------------------------------------------------------
        # SAVE THE RECORD
        # ---------------------------------------------------------
        record = super().write(vals)
        return record











