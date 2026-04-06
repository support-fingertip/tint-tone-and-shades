# -*- coding: utf-8 -*-
{
    'name': 'Purchase Advance Payment | Rfq advance payment | Purchase Payment',
    'description': "Purchase Advance Payment",
    'summary': 'Purchase Advance Payment',
    'version': '1.0',
    'category': 'Purchases',
    'author': 'TechKhedut Inc.',
    'company': 'TechKhedut Inc.',
    'maintainer': 'TechKhedut Inc.',
    'website': "https://www.techkhedut.com",
    'depends': [
        'purchase',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Wizard
        'wizard/purchase_advance_payment_inv_views.xml',
        # views
        'views/res_config_settings_views.xml',
        'views/purchase_order_details_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}
