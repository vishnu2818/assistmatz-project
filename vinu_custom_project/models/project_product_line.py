from odoo import models, fields

class ProjectProductLine(models.Model):
    _name = "project.product.line"
    _description = "Project Product Line"

    project_id = fields.Many2one(
        "project.project",
        string="Project",
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )

    quotation_ids = fields.Many2many(
        "sale.order",
        "project_product_line_sale_order_rel",
        "project_product_line_id",
        "sale_order_id",
        string="Quotations",
    )

    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
    )

    # Cost coming from sale.order.line (price_subtotal sum OR price_total)
    cost = fields.Float(string="Cost")
