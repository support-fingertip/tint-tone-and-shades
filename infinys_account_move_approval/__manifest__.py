# -*- coding: utf-8 -*-
{
    "name": "Infinys Account Move Approval",
    "summary": "Adds a multi-level approval workflow for account moves (invoices/bills) based on the total amount.",
    "description": """
        This module introduces a dynamic, multi-level approval workflow for account moves (invoices and vendor bills),
        enhancing control over accounting processes.

        The system allows for the configuration of sequential approval tiers, each tied to specific total amount ranges.
        When an invoice or bill's total value falls within a configured range, it is automatically routed through the
        corresponding approval steps before it can be posted.

        Each approval level can be assigned to specific users, who are then notified of pending approvals. The module
        integrates seamlessly into the invoice/bill form, adding a dedicated tab for managing the approval process.
        It also includes a personalized 'My Approvals' menu, giving users a clear overview of invoices awaiting their
        action and their approval history.
    """,
    "author": "Infinys System Indonesia",
    "website": "https://www.infinyscloud.com/platform/odoo/",
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "19.0.1.0.0",
    "depends": ["base", "account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_approval_level_views.xml",
        "views/account_move_views.xml",
        "views/account_reporting_views.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
}
