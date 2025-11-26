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
   
        for lead in self:
            # Backup current values
            old_user_id = lead.user_id.id
            old_stage_name = lead.stage_id.name
            old_stage_sequence = lead.stage_id.sequence
            team_leader = lead.team_id.user_id

            
            if 'stage_id' in vals:
                new_stage = LeadStage.browse(vals['stage_id'])
                new_stage_sequence = new_stage.sequence
                quotation=None
                if  new_stage.name != 'New':
                    quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
                
                _logger.warning(f"This is old_stage_name {old_stage_name} and new stage  {new_stage.name} ")  

                if not is_admin:

                    if new_stage_sequence < old_stage_sequence:
                        if not (old_stage_name == 'Hold' and new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']) :
                            raise ValidationError("You cannot move to an Backward stage.")

                    # Quote Submitted
                    if new_stage.name == 'Quote Submitted':
                        if ( old_stage_name != 'Quote Completed' or not quotation or quotation.state != 'sent'):
                            raise ValidationError("Only records in 'Quote Completed' with a valid 'sent' quotation can move to 'Quote Submitted'.")

                    # Quote Completed
                    if new_stage.name in ['Quote Completed']:
                        if old_stage_name != 'Quote Preparation' or not quotation:
                            raise ValidationError("Only records in 'Quote Preparation' with a valid quotation can move to Quote Completed.")
                        if not quotation.quote_completed and new_stage.name == 'Quote Completed' :
                            raise ValidationError("Please Use Quote Completed Button In Quotation for Move to Quote Completed")
                                
                    # Quote Preparation
                    if new_stage.name == 'Quote Preparation':
                        if old_stage_name != 'New':
                            raise ValidationError("Only records in 'New' can move to 'Quote Preparation'.")

                    # Advanced stages
                    if new_stage.name in ['Expecting (60%)', 'Commit (90%)', 'Won']:
                        if old_stage_name in ['Quote Completed', 'New', 'Quote Preparation']:
                            raise ValidationError(f"Only 'Quote Submitted' records can move to '{new_stage.name}'.")

                    if new_stage.name in ['Hold']:
                        if old_stage_name not in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']:
                            raise ValidationError(f"Only ['Quote Submitted' , 'Expecting (60%)', 'Commit (90%)'] records can move to '{new_stage.name}'.")

                    
                    if new_stage.name in ['Expecting (60%)', 'Commit (90%)','Lost' ] :
                        if not quotation or quotation.state != 'sent':
                            raise ValidationError( f"Only leads with a 'sent' quotation can be moved to '{new_stage.name}'.")
                        
                    # Hold stage restriction
                    if old_stage_name == 'Hold' and new_stage.name not in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']:
                            raise ValidationError("From 'Hold', you can move only to 'Expecting (60%)', 'Commit (90%)', 'Quote Submitted' ")

                

                    # Regret: Only allowed from Bid Team
                    if new_stage.name == 'Not in Scope':
                        if old_stage_name != 'Quote Preparation':
                            raise ValidationError("Please contact Administration. The 'Not in Scope' stage only accepts leads from the 'Quote Prepation' stage.")




                    
                    if old_stage_name == 'Won' and new_stage.name != 'Won':
                        raise ValidationError("Only Admin can move records from the 'Won' stage to another stage.")

                

                if is_admin or not is_admin :
                            
                    if old_stage_name == 'New' and new_stage.name != 'New':
                        for lead in self:
                            missing_fields = lead._check_required_fields_on_stage_change()
                            if missing_fields:
                                raise ValidationError(
                                    "Please fill the following fields before moving to 'Quote Preparation':\n- " + "\n- ".join(missing_fields)
                                )

                     # Forecast requirement for Commit 90%
                    if new_stage.name == 'Commit (90%)':
                        forecast_valid = lead.date_deadline
                        if not forecast_valid:
                            raise ValidationError("Forecast Date required to move to this stage.")
                    
            
                    if new_stage.name == 'Won':
                        for lead in self:
                            
                            if  quotation.state == 'sale':
                                if not lead.po_date or not lead.po_ref or not lead.po_attachment:
                                    raise ValidationError("Please fill at least one of the following fields before moving to 'Won': PO Date, PO Reference, or PO Attachment.")
                                
                            else:
                                raise ValidationError("You connot move manually to 'Won' stage. Please use the 'Confirm' button in Quotation to move to 'Won' stage.")
                                

            if 'active' in vals and not vals['active']:
                for lead in self:
                    quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
                    if not quotation: 
                         raise ValidationError("You cannot manually move to the 'Lost' stage when the Lead has no Quotation.")
                    lost = self.env['crm.stage'].search([('name', '=', 'Lost')], limit=1)
                    if lost:
                        vals['stage_id'] = lost.id


            if 'date_deadline' in vals:
                new_date = fields.Date.from_string(vals['date_deadline']) if isinstance(vals['date_deadline'], str) else vals['date_deadline']
                is_date = vals['date_deadline']
                if is_date:
                    if new_date < fields.Date.today():
                        raise ValidationError("Forecast date cannot be in the past.")
                        
                        
        record = super().write(vals)

        for lead in self:
            if lead.stage_id.name == 'New':
                missing_fields = lead._check_required_fields_on_stage_change()
                if not missing_fields:
                    stage = self.env['crm.stage'].search([('name', '=', 'Quote Preparation')], limit=1)
                    if stage:
                        lead.stage_id = stage.id
                        
        return record









