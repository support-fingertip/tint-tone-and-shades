# -*- coding: utf-8 -*-
{
    "name": "Infinys Purchase Order Approval",
    "summary": "Adds a multi-level approval workflow for purchase orders based on the total amount.",
    "description": """
        This module introduces a dynamic, multi-level approval workflow for purchase orders, enhancing control over procurement processes.

        The system allows for the configuration of sequential approval tiers, each tied to specific total order amount ranges. When a purchase order's total value falls within a configured range, it is automatically routed through the corresponding approval steps before it can be confirmed.
        
        Each approval level can be assigned to specific users, who are then notified of pending approvals. The module integrates seamlessly into the purchase order form, adding a dedicated tab for managing the approval process. It also includes a personalized 'My Approvals' menu, giving users a clear overview of orders awaiting their action and their approval history.
    """,
    "author": "Infinys System Indonesia",
    "website": "https://www.infinyscloud.com/platform/odoo/",
    "live_test_url": "https://odoo-ce.atisicloud.com/",
    "license": "LGPL-3",
    "category": "Purchases",
    "version": "19.0.1.0.0",
    "depends": ["base", "purchase", "mail", "infinys_margin_validation"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/purchase_approval_level_views.xml",
        "views/purchase_order_views.xml",
        "views/purchase_reporting_views.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
}
