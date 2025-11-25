from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    custom_header_image = fields.Image(string="Custom Header Image")
    custom_footer_image = fields.Image(string="Custom Footer Image")
