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
