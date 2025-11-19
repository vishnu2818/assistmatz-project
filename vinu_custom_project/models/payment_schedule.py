from odoo import models, fields

class PaymentSchedule(models.Model):
    _name = "payment.schedule"
    _description = "Payment Schedule"
    _order = "payment_date desc"

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Project",
        ondelete="cascade",
    )
    payment_description = fields.Text(string="Description")
    payment_date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today
    )
    amount = fields.Float(string="Amount")
    due_date = fields.Date(string="Due Date")
    status = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('paid', 'Paid'),
    ], string="Status", default='not_paid', required=True)