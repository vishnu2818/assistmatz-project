from odoo import models, fields

class ProjectProject(models.Model):
    _inherit = "project.project"

    assigned_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Assigned Employees",
        relation="project_employee_rel",
        column1="project_id", #fk for my model
        column2="employee_id",#fk for comodel
        help="Employees assigned to this project (multi-select)."
    )

    daily_update_ids = fields.One2many(
        comodel_name="daily.update",
        inverse_name="project_id",
        string="Daily Updates",
        help="Daily updates linked to this project"
    )

    payment_schedule_ids = fields.One2many(
        comodel_name="payment.schedule",
        inverse_name="project_id",
        string="Payment Schedules",
        help="Payment schedule lines for this project"
    )

    def action_view_payment_schedule(self):
        """Open payment schedules for this project in a popup."""
        self.ensure_one()
        action = self.env.ref("vinu_custom_project.action_payment_schedule_popup").read()[0]
        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {"default_project_id": self.id}
        return action

    cost = fields.Float("Cost")