# -*- coding: utf-8 -*-
{
    'name': 'All Inventory Analysis Reports',
    'version': '19.0.1.0.0',
    'summary': 'BI Inventory Analysis — Current Stock, Movements, Aging, Valuation, Dead Stock & Expiry Reports',
    'description': """
All Inventory Analysis Reports
================================
Comprehensive BI inventory analysis reports for Odoo 19:

Reports Included
----------------
* **Current Stock Analysis** — On-hand, reserved, and available quantities with stock valuation
* **Stock Movement Analysis** — Full inbound/outbound/internal movement history with pivot & graph
* **Inventory Aging Analysis** — How long stock has been in each location, bucketed by age
* **Stock Valuation Report** — Layer-by-layer valuation history (AVCO / FIFO / Standard)
* **Dead / Slow-Moving Stock** — Products with no recent activity, flagged by severity
* **Stock Expiry Report** — Lot-tracked products near expiration or already expired

All Reports Include
-------------------
- List, Pivot, and Graph views
- Rich search filters (date, product, category, warehouse, location, lot)
- Group-by options for every key dimension
- Excel export via Odoo standard export

    """,
    'author': '',
    'website': '',
    'category': 'Inventory/Reporting',
    'license': 'OPL-1',
    'depends': [
        'stock',
        'stock_account',
        'product',
        'uom',
        'product_expiry',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/report_stock_inventory_views.xml',
        'views/report_stock_move_views.xml',
        'views/report_stock_aging_views.xml',
        'views/report_stock_valuation_views.xml',
        'views/report_stock_dead_views.xml',
        'views/report_stock_expiry_views.xml',
        'views/menu_views.xml',
    ],
    'images': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
