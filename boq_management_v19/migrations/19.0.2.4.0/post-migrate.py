# -*- coding: utf-8 -*-
"""
Migration 19.0.2.3.0 → 19.0.2.4.0
=====================================
Partner Work Category Assignment feature.

1. Create boq_partner_category_rel Many2many table (if not already created
   by the ORM) — links res.partner to boq.category for work category assignment.

2. Ensure partner_type column exists on res_partner (it should already exist
   from previous migrations, but this is a safety net).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # ── 1. Create Many2many junction table for partner ↔ category ─────────
    cr.execute("""
        CREATE TABLE IF NOT EXISTS boq_partner_category_rel (
            partner_id  INTEGER NOT NULL
                REFERENCES res_partner(id) ON DELETE CASCADE,
            category_id INTEGER NOT NULL
                REFERENCES boq_category(id) ON DELETE CASCADE,
            PRIMARY KEY (partner_id, category_id)
        )
    """)
    _logger.info('BOQ migration 19.0.2.4.0: ensured boq_partner_category_rel table exists')

    # ── 2. Ensure partner_type column exists on res_partner ───────────────
    cr.execute("""
        ALTER TABLE res_partner
            ADD COLUMN IF NOT EXISTS partner_type VARCHAR
    """)
    _logger.info('BOQ migration 19.0.2.4.0: ensured partner_type column on res_partner')
