# -*- coding: utf-8 -*-
{
    'name': 'BOQ Management — Bill of Quantities (Odoo 19)',
    'version': '19.0.3.0.0',
    'summary': 'BOQ with trade-type RFQ creation, vendor+supplier ratings, dual manager dashboards',
    'description': """
        BOQ Management v3.0
        ====================
        ✅ BUG 1  — Margin formula fixed: (sale - cost) / sale × 100
        ✅ BUG 2  — Trade Assignments dashboard section (grouped by work_category_id)
        ✅ BUG 3  — Rating triggered AFTER receipt done + invoice paid (vendor & supplier)
        ✅ BUG 4  — Margin % prominently shown on dashboard vendor cards
        ✅ BUG 5  — RPC crash (stale ir.rule on boq.vendor.rating) permanently fixed
        ✅ BUG 6  — Payment status column on dashboard trade-wise & vendor rows
        ✅ NEW 1  — Partner type: Vendor / Supplier split (Vendor RFQ / Supplier RFQ menus)
        ✅ NEW 2  — Dashboard Vendor | Supplier toggle tab → now TWO separate menu pages
        ✅ NEW 3  — Margin % on RFQ comparison (purchase.order.line)
        ✅ NEW 4  — boq.vendor.rating model; avg_rating on res.partner (vendor & supplier)
        ✅ NEW 5  — Mail template for vendor portal quotation submission
        ✅ NEW 6  — Trade-level vendor/supplier assignment tab in BOQ form
        ✅ NEW 7  — Create RFQ uses trade-type assignments (all trade lines → partner RFQ)
        ✅ NEW 8  — Approval workflow removed (Draft → Done directly)
        ✅ NEW 9  — Rate Vendor / Rate Supplier button adapts to partner_type
        ✅ NEW 10 — Partner work_category_ids: assign categories on Contact; Create RFQ
                    auto-matches partners to BOQ lines by category + partner_type

        v3.0 Changes (Tasks 1–5)
        ========================
        TASK 1  — Replaced single BOQ Dashboard with two separate menu pages:
                    • Vendor Manager Dashboard   (dashboard_type = vendor)
                    • Procurement Manager Dashboard (dashboard_type = supplier)
        TASK 2  — Expandable 3-level tree: Trade → Vendor → RFQ status breakdown
                    • Pending RFQ indicators (vendors with no quotation yet)
                    • Bell notification on recently submitted quotations (< 7 days)
                    • No payment info inside vendor-expanded section
        TASK 3  — BOQ category duplication bug fixed (compare by ID set, not recordset)
        TASK 4  — Dashboard renamed per page; "lines" removed; line details removed;
                    boq_type toggle on BOQ form (Vendor / Supplier);
                    payment status shown at vendor-row level;
                    "Draft" relabelled to "Quote Requested"
        TASK 5  — Multi-company: uses allowed_company_ids from context for all queries
    """,
    'author': 'Senior Odoo Developer',
    'category': 'Industries/Construction',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
        'product',
        'contacts',
        'web',
        'uom',
        'purchase',
        'purchase_stock',
        'account',
        'project',
        'stock',
    ],
    'data': [
        'security/boq_groups.xml',
        'security/ir.model.access.csv',
        'data/boq_sequence_data.xml',
        'data/boq_category_data.xml',
        'data/mail_template_data.xml',
        'views/boq_dashboard_views.xml',
        'views/boq_boq_views.xml',
        'views/boq_category_views.xml',
        'views/boq_order_line_views.xml',
        'views/boq_vendor_rating_views.xml',
        'views/res_partner_views.xml',
        'views/purchase_order_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'boq_management_v19/static/src/css/boq_enterprise.css',
            'boq_management_v19/static/src/css/boq_dashboard.css',
            'boq_management_v19/static/src/js/boq_dashboard.js',
            'boq_management_v19/static/src/xml/boq_dashboard.xml',
        ],
    },
    'images': ['static/src/img/boq_icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
