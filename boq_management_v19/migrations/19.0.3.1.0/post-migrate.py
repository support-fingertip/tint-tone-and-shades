# -*- coding: utf-8 -*-
"""
Post-migration script for boq_management_v19 v19.0.3.1.0
=========================================================
Changes introduced in 3.1.0 (no raw SQL needed — all handled by
_register_hook() / _auto_init() which run on every server startup):

  • get_vendor_boq_lines() — now respects allowed_company_ids (multi-company fix)
  • get_approval_pending_pos() — defensive guard for approval_line_ids field
  • CSS duplicate .boq_totals_chip / .boq_totals_value definitions removed
  • Two truly separate OWL dashboard components retained (no regression)

This file exists to satisfy Odoo's migration framework so the stored
module version is updated cleanly from 19.0.3.0.0 → 19.0.3.1.0.
"""


def migrate(cr, version):
    """No schema changes needed in 3.1.0."""
    pass
