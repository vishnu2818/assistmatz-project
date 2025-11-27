{
    'name': 'Custom Header Footer',
    'version': '1.0',
    'category': 'Customization',
    'summary': 'Custom report header and footer',
    'depends': ['base', 'web', 'account', 'sale'],
    'data': [
        'views/res_company_views.xml',
        'views/external_layout_inherit.xml',
        'views/report_sno_inherit.xml',
    ],
    'installable': True,
    'application': False,
}
