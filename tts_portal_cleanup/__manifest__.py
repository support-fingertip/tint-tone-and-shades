# -*- coding: utf-8 -*-
{
    "name": "TTS Portal Cleanup",
    "version": "19.0.1.0.0",
    "category": "Website/Portal",
    "summary": "Hide top navbar and invoice sidebar for portal users.",
    "description": """
        For users with share=True (portal users and public visitors viewing a
        document via a token URL), this module hides the standard Odoo portal
        chrome on the invoice / bill detail page:

          • The top 'Your logo' / user-menu navbar.
          • The left sidebar card (breadcrumb, amount summary, Pay Now,
            Download, Salesperson, 'Powered by odoo').

        Internal users (employees, accounts managers previewing the portal
        page) continue to see the full layout so they can navigate normally.
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
