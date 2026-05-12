# -*- coding: utf-8 -*-
{
    "name": "TTS Accounts Manager Dashboard",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "summary": "Accounts Manager Dashboard — 5 financial widgets with role-based access control",
    "description": """
        Accounts Manager Dashboard provides a real-time financial overview for the Accounts Manager role.

        Widgets:
        ─────────────────────────────────────────────────────────
        1. Monthly Revenue Collection   — bar chart, last 12 months
        2. Monthly Overheads            — bar chart, last 12 months
        3. Office Expenses & Maintenance — categorised horizontal bars, YTD
        4. Pending Approvals            — count + drill-down list (invoices, bills, POs)
        5. Vendor Payment Requests      — pending bills from Procurement / Vendor modules

        Access Control:
        ─────────────────────────────────────────────────────────
        • Only users in  account.group_account_manager  see the dashboard menu.
        • Associate-level users have no access — the menu is not rendered for them.
    """,
    "author": "Tint Tone & Shades",
    "license": "LGPL-3",
    "depends": ["base", "account", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tts_account_manager_dashboard/static/src/dashboard.scss",
            "tts_account_manager_dashboard/static/src/dashboard.xml",
            "tts_account_manager_dashboard/static/src/dashboard.js",
        ],
    },
    "images": [
        "static/description/icon.png",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
