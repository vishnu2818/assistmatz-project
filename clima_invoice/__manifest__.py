# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'climatech Invoice',
    'version': '19.0.1.0.0',
    'category': 'sale',
    'sequence': 46,
    'summary': 'Climatech Invoice',
    'depends': [
        'base','mail','sale','account'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/account_move.xml',
        'views/invoice_approve.xml',
        'wizard/invoice_reject_wizard_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
