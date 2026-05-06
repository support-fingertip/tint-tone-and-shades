# -*- coding: utf-8 -*-
"""
Migration 19.0.1.1.0 – populate the two new stored computed fields that
power the three role-based approval dashboards.

  current_approval_type  (VARCHAR column on purchase_order)
  current_approver_ids   (relation table purchase_order_current_approver_rel)

Odoo's ORM creates the column and relation table during the upgrade step.
This post-migrate script then forces a recompute so that every existing PO
in 'to approve' state has the correct values before users open the dashboards.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recompute current_approval_type / current_approver_ids on all POs."""
    if not version:
        return

    env = None
    try:
        from odoo import api, registry as reg_factory
        from odoo.modules.registry import Registry

        db_name = cr.dbname
        registry = Registry(db_name)
        with registry.cursor() as new_cr:
            env = api.Environment(new_cr, 1, {})
            orders = env['purchase.order'].search([])
            if orders:
                _logger.info(
                    "post-migrate 19.0.1.1.0: recomputing approval dashboard "
                    "fields on %d purchase order(s).", len(orders)
                )
                orders._compute_current_approval_info()
                new_cr.commit()
                _logger.info("post-migrate 19.0.1.1.0: recompute complete.")
    except Exception as exc:
        _logger.warning(
            "post-migrate 19.0.1.1.0: could not recompute stored fields "
            "automatically (%s). Run Settings > Technical > "
            "Scheduled Actions → 'Recompute stored fields' or upgrade "
            "the module again.", exc
        )
