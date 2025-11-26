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


    expected_quotation_date = fields.Date(string='Quote Expected On')
    project_id = fields.Many2one('project.project', string='Project')

    @api.onchange('stage_id')
    def _onchange_stage_restrict_quote_completed(self):
        # Prevent user manually selecting Quote Completed in UI
        if self.stage_id and self.stage_id.name == 'Quote Completed':
            raise UserError("Manual move to 'Quote Completed' stage is restricted.")

    def _check_required_fields_on_stage_change(self):
        """Return list of missing mandatory field labels."""
        missing = []
        for lead in self:
            if not lead.partner_id:
                missing.append("Customer")
            if not getattr(lead, 'x_studio_job_type', False):
                missing.append("Job Type")
            if not getattr(lead, 'x_studio_project', False):
                missing.append("Project")
            if not lead.email_from:
                missing.append("Email")
            if not lead.phone:
                missing.append("Phone")
            if not lead.date_deadline:
                missing.append("Forecast Date")
        return missing

    @api.model_create_multi
    def create(self, vals_list):
        # Create records normally first
        records = super().create(vals_list)

        # After creation, attempt auto-stage move for any new record in 'New'
        # Use flags to avoid recursive auto logic & skip validations for programmatic stage set
        for rec in records:
            try:
                # only attempt if currently in New and all mandatory fields are present
                if rec.stage_id and rec.stage_id.name == 'New':
                    missing = rec._check_required_fields_on_stage_change()
                    if not missing:
                        next_stage = self.env['crm.stage'].search([('name', '=', 'Quote Preparation')], limit=1)
                        if next_stage:
                            rec.with_context(
                                skip_auto_stage=True,
                                bypass_stage_validations=True
                            ).write({'stage_id': next_stage.id})
                            _logger.info("Auto-moved newly created lead %s -> Quote Preparation", rec.id)
            except Exception as e:
                _logger.exception("Failed auto move on create for lead %s: %s", rec.id, e)
        return records

    def write(self, vals):
        """
        Full write with:
         - auto-move New -> Quote Preparation before validation (if all required filled)
         - robust manual stage change validation
         - uses context flags to avoid recursion when programmatically setting stage
        """
        LeadStage = self.env['crm.stage']
        SaleOrder = self.env['sale.order']
        user = self.env.user
        is_admin = user.has_group('base.group_system')

        # If this call is a programmatic bypass, just perform normal write (avoid validations)
        if self.env.context.get('bypass_stage_validations'):
            return super(Lead, self).write(vals)

        # ---------- AUTO MOVE BLOCK ----------
        # Only run if not already in a recursive auto-move
        if not self.env.context.get('skip_auto_stage'):
            for lead in self:
                try:
                    # Only auto move if record currently in 'New', user not explicitly changing stage,
                    # and all mandatory fields are present
                    if lead.stage_id and lead.stage_id.name == 'New' and 'stage_id' not in vals:
                        missing = lead._check_required_fields_on_stage_change()
                        if not missing:
                            next_stage = LeadStage.search([('name', '=', 'Quote Preparation')], limit=1)
                            if next_stage:
                                # Programmatically set stage using flags to avoid re-running auto logic
                                lead.with_context(
                                    skip_auto_stage=True,
                                    bypass_stage_validations=True
                                ).write({'stage_id': next_stage.id})
                                _logger.info("Auto-moved lead %s -> Quote Preparation (pre-write)", lead.id)
                except Exception as e:
                    _logger.exception("Auto-move failed for lead %s: %s", lead.id, e)
        # ---------- END AUTO MOVE BLOCK ----------

        # ---------- VALIDATIONS FOR MANUAL STAGE CHANGE ----------
        # At this point, we validate stage transitions present in incoming vals.
        for lead in self:
            old_stage = lead.stage_id
            old_stage_name = old_stage.name if old_stage else False
            old_stage_sequence = old_stage.sequence if old_stage else 0

            # if active -> False indicates marking lost (soft-delete)
            if 'active' in vals and vals.get('active') is False:
                # Ensure quotation exists before allowing lost
                quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)
                if not quotation:
                    raise ValidationError("You cannot move to Lost when no quotation exists.")
                lost_stage = LeadStage.search([('name', '=', 'Lost')], limit=1)
                if lost_stage:
                    vals['stage_id'] = lost_stage.id

            # Manual stage change validations (only if stage_id present in vals)
            if 'stage_id' in vals:
                new_stage = LeadStage.browse(vals['stage_id'])
                new_stage_name = new_stage.name
                new_stage_sequence = new_stage.sequence

                # Find related quotation if needed
                quotation = None
                if new_stage_name != 'New':
                    quotation = SaleOrder.search([('opportunity_id', '=', lead.id)], limit=1)

                if not is_admin:
                    # Block backward moves (except allowed Hold->Expecting/Commit/Quote Submitted)
                    if new_stage_sequence < old_stage_sequence:
                        if not (old_stage_name == 'Hold' and new_stage_name in ['Expecting (60%)', 'Commit (90%)', 'Quote Submitted']):
                            raise ValidationError("You cannot move to a backward stage.")

                    # Quote Submitted rule
                    if new_stage_name == 'Quote Submitted':
                        if old_stage_name != 'Quote Completed' or not quotation or quotation.state != 'sent':
                            raise ValidationError("Only records in 'Quote Completed' with a valid 'sent' quotation can move to 'Quote Submitted'.")

                    # Quote Completed rule
                    if new_stage_name == 'Quote Completed':
                        if old_stage_name != 'Quote Preparation' or not quotation:
                            raise ValidationError("Only records in 'Quote Preparation' with a valid quotation can move to Quote Completed.")
                        if not getattr(quotation, 'quote_completed', False):
                            raise ValidationError("Please use 'Quote Completed' button in the quotation to move to Quote Completed stage.")

                    # Quote Preparation rule
                    if new_stage_name == 'Quote Preparation':
                        if old_stage_name != 'New':
                            raise ValidationError("Only 'New' records can move to 'Quote Preparation'.")

                    # Advanced stages rules
                    if new_stage_name in ['Expecting (60%)', 'Commit (90%)', 'Won']:
                        if old_stage_name in ['Quote Completed', 'New', 'Quote Preparation']:
                            raise ValidationError(f"Only 'Quote Submitted' records can move to '{new_stage_name}'.")

                    # Hold rules
                    if new_stage_name == 'Hold':
                        if old_stage_name not in ['Quote Submitted', 'Expecting (60%)', 'Commit (90%)']:
                            raise ValidationError("Only ['Quote Submitted', 'Expecting (60%)', 'Commit (90%)'] can move to Hold.")

                    # Expecting/Commit/Lost require sent quotation
                    if new_stage_name in ['Expecting (60%)', 'Commit (90%)', 'Lost']:
                        if not quotation or quotation.state != 'sent':
                            raise ValidationError(f"Only leads with a 'sent' quotation can move to '{new_stage_name}'.")

                    # Not in Scope rule
                    if new_stage_name == 'Not in Scope':
                        if old_stage_name != 'Quote Preparation':
                            raise ValidationError("Only leads in 'Quote Preparation' can move to 'Not in Scope'.")

                    # Won locked
                    if old_stage_name == 'Won' and new_stage_name != 'Won':
                        raise ValidationError("Only Admin can move records out of 'Won' stage.")

                # Forecast requirement for Commit (90%)
                if new_stage_name == 'Commit (90%)' and not lead.date_deadline:
                    raise ValidationError("Forecast Date is required to move to this stage.")

                # Won validations
                if new_stage_name == 'Won':
                    if quotation and quotation.state == 'sale':
                        if not lead.po_date and not lead.po_ref and not lead.po_attachment:
                            raise ValidationError("Please provide PO Date or PO Reference or PO Attachment before moving to 'Won'.")
                    else:
                        raise ValidationError("Cannot move manually to 'Won'. Use the 'Confirm' button in Quotation.")

            # Forecast date in vals should not be past
            if 'date_deadline' in vals:
                try:
                    # normalize date (string or date)
                    new_date = vals.get('date_deadline')
                    if isinstance(new_date, str):
                        # let Odoo transform it normally; but simplest check:
                        new_date = fields.Date.from_string(new_date)
                    if new_date and new_date < fields.Date.today():
                        raise ValidationError("Forecast date cannot be in the past.")
                except ValidationError:
                    raise
                except Exception:
                    # If parsing fails, let Odoo raise later but log it
                    _logger.exception("Failed to parse date_deadline in write vals: %s", vals.get('date_deadline'))

        # ---------- FINALLY SAVE ----------
        res = super(Lead, self).write(vals)
        return res











