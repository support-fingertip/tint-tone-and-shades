# -*- coding: utf-8 -*-
{
    "name": "TTS Portal Cleanup",
    "version": "19.0.1.0.0",
    "category": "Website/Portal",
    "summary": "Hide the portal logo and invoice sidebar for portal users.",
    "description": """
        This module hides the standard Odoo portal chrome:

          • The 'Your logo' brand in the top navbar. The bar itself and the
            user-menu / Logout dropdown stay visible so portal users keep
            their account access.
          • On the invoice / bill detail page, the left sidebar card
            (breadcrumb, amount summary, Pay Now, Download, Salesperson,
            'Powered by odoo').

        Applied to all portal frontend visitors, including internal users
        previewing the portal page.
    """,
    "author": "",
    "license": "LGPL-3",
    "depends": ["portal", "account"],
    "data": [
        "views/portal_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
