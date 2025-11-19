from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    date_deadline = fields.Date(string="Forecast Date")
    is_warranty = fields.Boolean(string="Warranty", default=False)
    brand = fields.Char(string="Brand")
    serial_no = fields.Char(string="Serial No")
    purchase_date = fields.Date(string="Purchase Date")
    warranty_close_date = fields.Date(string="Warranty Close Date")
    extended_warranty_date = fields.Date(string="Extended Warranty Date")

    show_warranty_tab = fields.Boolean(
        string="Show Warranty Tab",
        compute="_compute_show_warranty_tab",
        store=True,
    )
    @api.depends('is_warranty')
    def _compute_show_warranty_tab(self):
        for order in self:
            order.show_warranty_tab = bool(order.is_warranty)

    # @api.depends('is_warranty')
    # def _compute_show_warranty_tab(self):
    #     for rec in self:
    #         rec.show_warranty_tab = rec.is_warranty

    # @api.onchange('is_warranty')
    # def _onchange_is_warranty(self):
    #     if not self.is_warranty:
    #         self.brand = False
    #         self.serial_no = False
    #         self.purchase_date = False
    #         self.warranty_close_date = False
    #         self.extended_warranty_date = False

    @api.model
    def create(self, vals):
        order = super().create(vals)
        order._update_lead_expected_revenue()
        return order

    def write(self, vals):
        res = super().write(vals)
        self._update_lead_expected_revenue()
        return res

    def _update_lead_expected_revenue(self):
        """Update CRM Lead expected_revenue to the quotation's total."""
        for order in self:
            if order.opportunity_id:
                # Just replace with the current quotation total
                order.opportunity_id.expected_revenue = order.amount_total

    def action_confirm(self):
        """Block confirmation if warranty is enabled and required details are missing."""
        for order in self:
            if order.is_warranty:  # ✅ Only check if warranty is enabled
                missing_fields = []
                # Check required warranty fields
                if not order.brand:
                    missing_fields.append("Brand")
                if not order.serial_no:
                    missing_fields.append("Serial No")
                if not order.purchase_date:
                    missing_fields.append("Purchase Date")
                if not order.warranty_close_date:
                    missing_fields.append("Warranty Close Date")
    
                if missing_fields:
                    raise UserError(
                        _("Please fill the following Warranty Details before confirming the quotation:\n- {}")
                        .format("\n- ".join(missing_fields))
                    )
    
        return super(SaleOrder, self).action_confirm()

    
    # @api.constrains('is_warranty', 'brand', 'serial_no', 'purchase_date')
    # def _check_warranty_data_consistency(self):
    #     """
    #     Prevents saving the record if warranty data is present but the 'Warranty' 
    #     checkbox is unchecked, enforcing the UI requirement via backend logic.
    #     """
    #     for order in self:
    #         # Check if ANY required warranty field has data
    #         if any([order.brand, order.serial_no, order.purchase_date, order.warranty_close_date, order.extended_warranty_date]):
                
    #             # If data exists but the main warranty flag is False, raise an error
    #             if not order.is_warranty:
    #                 raise ValidationError(
    #                     _("Cannot save warranty details without checking the 'Warranty' box in the Quotation header.")
    #                 )
