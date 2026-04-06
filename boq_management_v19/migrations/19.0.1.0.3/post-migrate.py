# -*- coding: utf-8 -*-
"""
Migration 19.0.1.0.2 → 19.0.1.0.3
====================================
Restores tax_ids (Many2many → account.tax) on boq.order.line.

The relation table boq_order_line_tax_rel was created in migration 19.0.1.0.2.
This migration ensures it also exists for installations that skipped 19.0.1.0.2
or are upgrading directly from an older version.

All statements use IF NOT EXISTS / IF EXISTS so re-runs are always safe.
"""


def migrate(cr, version):
    # Ensure the M2M relation table for boq.order.line ↔ account.tax exists.
    # The ORM column definition uses explicit relation='boq_order_line_tax_rel'.
    cr.execute("""
        CREATE TABLE IF NOT EXISTS boq_order_line_tax_rel (
            line_id INTEGER NOT NULL
                REFERENCES boq_order_line(id) ON DELETE CASCADE,
            tax_id  INTEGER NOT NULL
                REFERENCES account_tax(id)    ON DELETE CASCADE,
            PRIMARY KEY (line_id, tax_id)
        );
    """)
