# -*- coding: utf-8 -*-
"""
Migration 19.0.1.0.1 → 19.0.1.0.2
===================================
Adds all new columns introduced in Tasks 1–2 that require ALTER TABLE.
Uses ADD COLUMN IF NOT EXISTS so re-runs are safe.

Columns added
-------------
boq_boq
  project_id          INTEGER           (M2O → project.project)

boq_category
  is_dynamic          BOOLEAN           (dynamic sub-category flag, default FALSE)
  parent_id           INTEGER           (self-referential M2O for hierarchy)

boq_order_line
  cost_price          NUMERIC           (unit cost from product.standard_price)
  tax_amount          NUMERIC           (computed tax portion)
  total_value         NUMERIC           (subtotal + tax)
  margin_percent      NUMERIC           (gross margin %)

Note: boq_order_line_tax_rel (M2M to account.tax) is a new table created
by Odoo ORM automatically — no manual DDL required for relation tables.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE boq_boq
            ADD COLUMN IF NOT EXISTS project_id INTEGER;
    """)

    cr.execute("""
        ALTER TABLE boq_category
            ADD COLUMN IF NOT EXISTS is_dynamic BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    cr.execute("""
        ALTER TABLE boq_category
            ADD COLUMN IF NOT EXISTS parent_id INTEGER;
    """)

    cr.execute("""
        ALTER TABLE boq_order_line
            ADD COLUMN IF NOT EXISTS cost_price     NUMERIC,
            ADD COLUMN IF NOT EXISTS tax_amount     NUMERIC,
            ADD COLUMN IF NOT EXISTS total_value    NUMERIC,
            ADD COLUMN IF NOT EXISTS margin_percent NUMERIC;
    """)

    # M2M relation table for tax_ids on boq.order.line
    cr.execute("""
        CREATE TABLE IF NOT EXISTS boq_order_line_tax_rel (
            line_id INTEGER NOT NULL
                REFERENCES boq_order_line(id) ON DELETE CASCADE,
            tax_id  INTEGER NOT NULL
                REFERENCES account_tax(id)    ON DELETE CASCADE,
            PRIMARY KEY (line_id, tax_id)
        );
    """)
