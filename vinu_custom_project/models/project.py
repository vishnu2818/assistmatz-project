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

    product_line_ids = fields.One2many(
        "project.product.line",
        "project_id",
        string="Products"
    )

    cost = fields.Float(
        string="Cost",
        compute="_compute_total_product_cost",
        store=False,
    )

    # BEFORE TAX
    # def _compute_total_product_cost(self):
    #     SaleOrderLine = self.env["sale.order.line"]
    #     for project in self:
    #         # FIXED DOMAIN → match your working product logic
    #         sol_lines = SaleOrderLine.search([
    #             ("order_id.project_id", "=", project.id)
    #         ])
    #
    #         # Total cost = sum of price_subtotal
    #         project.cost = sum(sol_lines.mapped("price_subtotal"))

    # AFTER TAX
    def _compute_total_product_cost(self):
        SaleOrderLine = self.env["sale.order.line"]
        for project in self:
            # Get all sale order lines linked to this project
            sol_lines = SaleOrderLine.search([
                ("order_id.project_id", "=", project.id)
            ])

            # After-tax total = price_total
            project.cost = sum(sol_lines.mapped("price_total"))

    def action_view_product_list(self):
        self.ensure_one()

        ProductLine = self.env["project.product.line"]
        SaleOrderLine = self.env["sale.order.line"]

        # 1) Clear old product lines for this project
        ProductLine.search([("project_id", "=", self.id)]).unlink()

        # 2) Find all sale order lines belonging to this project
        # 👉 FIXED DOMAIN
        sol_lines = SaleOrderLine.search([
            ("order_id.project_id", "=", self.id)
        ])

        # 3) Group by product: qty, quotations, and cost
        product_map = {}
        for line in sol_lines:
            product = line.product_id
            if not product:
                continue
            info = product_map.setdefault(product.id, {
                "product": product,
                "qty": 0.0,
                "quotation_ids": set(),
                "cost": 0.0,
            })
            info["qty"] += line.product_uom_qty or 0.0
            info["cost"] += line.price_subtotal or 0.0
            if line.order_id:
                info["quotation_ids"].add(line.order_id.id)

        # 👉 4) Create project product lines WITH SEQUENCE
        sequence = 1  # start SI:NO from 1

        for product_id, info in product_map.items():
            rec = ProductLine.create({
                "project_id": self.id,
                "product_id": product_id,
                "quantity": info["qty"],
                "cost": info["cost"],
                "sequence": sequence,  # ★ add sequence here
            })

            # increment sequence
            sequence += 1
            if info["quotation_ids"]:
                rec.quotation_ids = [(6, 0, list(info["quotation_ids"]))]

        # 5) Open popup filtered by this project
        action = self.env.ref("vinu_custom_project.action_project_product_line_popup").read()[0]
        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {"default_project_id": self.id}
        return action