# -*- coding: utf-8 -*-
"""
Migration 19.0.2.0.0 — Add new stored columns introduced in v2.0.0
─────────────────────────────────────────────────────────────────────
Columns added here with IF NOT EXISTS so the migration is idempotent:
  res_partner  : partner_type (VARCHAR), avg_rating (NUMERIC), rating_count (INTEGER)
  boq_category : is_down_payment (BOOLEAN)

The boq_vendor_rating table is a brand-new model and is created
automatically by the ORM — no manual DDL needed for it.
"""


def migrate(cr, version):
    # ── res_partner ─────────────────────────────────────────────────────
    cr.execute("""
        ALTER TABLE res_partner
            ADD COLUMN IF NOT EXISTS partner_type VARCHAR,
            ADD COLUMN IF NOT EXISTS avg_rating   NUMERIC(6, 2) DEFAULT 0.0,
            ADD COLUMN IF NOT EXISTS rating_count INTEGER       DEFAULT 0;
    """)

    # ── boq_category ────────────────────────────────────────────────────
    cr.execute("""
        ALTER TABLE boq_category
            ADD COLUMN IF NOT EXISTS is_down_payment BOOLEAN DEFAULT FALSE;
    """)
