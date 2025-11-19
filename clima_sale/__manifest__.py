# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'climatech sale',
    'version': '19.0.1.0.0',
    'category': 'sale',
    'sequence': 46,
    'summary': 'Climatech sale',
    'depends': [
        'base','mail','sale'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/sale_view.xml',
        'wizard/reject.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
