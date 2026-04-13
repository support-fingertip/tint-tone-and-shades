# -*- coding: utf-8 -*-
"""
Migration 19.0.3.0.0 — BOQ Management v3.0
===========================================
Task 4.4: Add boq_type column to boq_boq table.
          Existing BOQs default to 'vendor' so they flow into the
          Vendor Manager Dashboard without any data loss.
Task 1:   Existing action reference 'action_boq_dashboard' is replaced by
          two new actions; old XML ID is removed via this migration to avoid
          orphaned ir.actions.client records.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # ── 1. Add boq_type column with default 'vendor' ─────────────────────
    cr.execute("""
        ALTER TABLE boq_boq
        ADD COLUMN IF NOT EXISTS boq_type VARCHAR(16) NOT NULL DEFAULT 'vendor'
    """)
    _logger.info("Migration 19.0.3.0.0: boq_type column ensured on boq_boq.")

    # ── 2. Remove old single-dashboard ir.actions.client record if present ─
    cr.execute("""
        DELETE FROM ir_act_client
        WHERE tag = 'boq_management_v19.boq_dashboard_action'
    """)
    _logger.info("Migration 19.0.3.0.0: old boq_dashboard_action client action removed.")
