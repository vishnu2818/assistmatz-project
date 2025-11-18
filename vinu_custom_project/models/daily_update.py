from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class DailyUpdate(models.Model):
    _name = "daily.update"
    _description = "Daily Update"
    _rec_name = "update_date"
    _order = "update_date desc"

    project_id = fields.Many2one('project.project', string="Project", ondelete="cascade", index=True)
    update_date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True,
                                  default=lambda self: self._default_employee())
    description = fields.Text(string="Description")
    # Multiple attachments
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'daily_update_ir_attachments_rel',  # relation table name
        'daily_update_id',  # column linking to this model
        'attachment_id',  # column linking to ir.attachment
        string="Attachments"
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('completed', 'Completed')
        ],
        string="Status",
        default='pending',
    )

    allow_edit_after_edit = fields.Boolean(
        string="Allow edit",
        compute="_compute_allow_edit_after_create",
        store=False,
        readonly=True
    )

    @api.depends_context()
    def _compute_allow_edit_after_create(self):
        """True only if CURRENT USER is in editor group"""
        user_is_editor = self.env.user.has_group('vinu_custom_project.group_daily_update_editor')
        for rec in self:
            rec.allow_edit_after_edit = bool(user_is_editor)

    @api.model
    def _default_employee(self):
        emp = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return emp.id or False

    def _user_is_editor_group(self):
        # matches security/groups.xml record id
        return self.env.user.has_group('vinu_custom_project.group_daily_update_editor')

    @api.model_create_multi
    def create(self, vals_list):
        # create allowed for any user; uniqueness enforced by constraint below
        return super(DailyUpdate, self).create(vals_list)

    def write(self, vals):
        """
        After create:
         - description/attachment cannot be modified by anyone
         - only editor group members can modify 'update_date' and 'employee_id'
        """
        allowed_for_editors = {'update_date', 'employee_id'}

        for rec in self:
            if rec.id:  # existing record
                forbidden_after_create = {'description', 'attachment', 'attachment_filename'}
                if forbidden_after_create.intersection(vals.keys()):
                    raise UserError(_("Description or attachment cannot be modified after creation."))

                if not self._user_is_editor_group():
                    raise UserError(_("You are not allowed to modify Daily Updates once created."))

                extra = set(vals.keys()) - allowed_for_editors
                if extra:
                    raise UserError(_("Editors may only change Date and Employee on existing records. Tried to change: %s") % (', '.join(extra),))

        return super(DailyUpdate, self).write(vals)

    def unlink(self):
        """Only users in editor group can delete Daily Updates."""
        if not self._user_is_editor_group():
            # you can also use AccessError, but you are already using UserError above
            raise UserError(_("You are not allowed to delete Daily Updates."))

        return super(DailyUpdate, self).unlink()


    #Unique check
    @api.constrains('project_id', 'update_date', 'employee_id')
    def _check_unique_project_date_employee(self):
        """Prevent duplicate Daily Update with the same project + update_date + employee."""
        for rec in self:
            if not rec.project_id or not rec.update_date or not rec.employee_id:
                continue
            domain = [
                ('project_id', '=', rec.project_id.id),
                ('update_date', '=', rec.update_date),
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_("A Daily Update for this Project, Date and Employee already exists."))
