# -*- coding: utf-8 -*-
{
    "name": "Infinys Margin Validation",
    "summary": "Calculates margin on RFQ lines and triggers approval workflow when margin is below trade-wise thresholds.",
    "author": "Infinys System Indonesia",
    "website": "https://www.infinyscloud.com/platform/odoo/",
    "license": "LGPL-3",
    "category": "Purchases",
    "version": "19.0.1.0.0",
    "depends": ["purchase", "mail", "tk_purchase_advance_payment"],
    "data": [
        "security/ir.model.access.csv",
        "views/margin_threshold_views.xml",
        "views/purchase_order_views.xml",
        'wizard/purchase_advance_payment_views.xml',
    ],
    "installable": True,
    "application": False,
}
