from odoo import models, fields, api

class ProjectProductLine(models.Model):
    _name = "project.product.line"
    _description = "Project Product Line"

    sequence = fields.Integer(string="SI.No", default=0, readonly=True)
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

    @api.model
    def create(self, vals):
        # assign a sequence number per project (incremental within a project)
        if 'project_id' in vals and not vals.get('sequence'):
            project_id = vals.get('project_id')
            # find the current max sequence for this project
            last = self.search([('project_id', '=', project_id)], order='sequence desc', limit=1)
            vals['sequence'] = (last.sequence or 0) + 1
        return super().create(vals)

    def write(self, vals):
        # optionally protect a sequence from being overwritten by UI
        if 'sequence' in vals:
            vals.pop('sequence')
        return super().write(vals)
