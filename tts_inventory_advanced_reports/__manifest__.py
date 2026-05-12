# -*- coding: utf-8 -*-
{
    "name": "TTS Inventory Advanced Reports",
    "version": "19.0.1.0.0",
    "category": "Inventory/Reporting",
    "summary": "8 advanced inventory analytics reports: Aging, FSN, XYZ, Overstock, Out-of-Stock, Movement — PDF & Excel export",
    "author": "TTS",
    "depends": ["stock", "base_setup"],
    "data": [
        "security/ir.model.access.csv",
        "report/report_templates.xml",
        "views/inventory_report_wizard_views.xml",
        "views/inventory_report_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tts_inventory_advanced_reports/static/src/scss/reports.scss",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
