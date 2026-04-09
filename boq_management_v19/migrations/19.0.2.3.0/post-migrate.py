# -*- coding: utf-8 -*-
"""
Migration 19.0.2.2.0 → 19.0.2.3.0
=====================================
1. Remove stale ir.rule on boq.vendor.rating
   ─ A legacy rule with domain_force [('res_model','=','res.partner')] crashes
     every res.partner read because boq.vendor.rating has no res_model field.
   ─ Permanent DB delete; the _register_hook + _auto_init cleanups on the
     model also run on every startup / upgrade as a belt-and-suspenders guard.

2. Reset obsolete BOQ states to 'draft'
   ─ The approval workflow (submitted / approved / rejected) has been removed.
   ─ Any BOQ still in those states is reset to 'draft' so users can continue
     editing and mark them done via the new simplified flow.

3. Add partner_type column to boq_vendor_rating (stored related field)
   ─ The ORM will create the column automatically, but we add it here in case
     the table already exists and the column is missing.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # ── 1. Remove stale ir.rule ────────────────────────────────────────────
    cr.execute("""
        DELETE FROM ir_rule
         WHERE domain_force LIKE %s
           AND model_id IN (
               SELECT id FROM ir_model
                WHERE model IN ('boq.vendor.rating', 'vendor.po.rating')
           )
    """, ('%res_model%',))
    deleted = cr.rowcount
    if deleted:
        _logger.info('BOQ migration 19.0.2.3.0: deleted %d stale ir.rule(s) '
                     'with res_model domain on boq.vendor.rating', deleted)

    # ── 2. Reset obsolete BOQ states ──────────────────────────────────────
    cr.execute("""
        UPDATE boq_boq
           SET state = 'draft'
         WHERE state IN ('submitted', 'approved', 'rejected')
    """)
    reset = cr.rowcount
    if reset:
        _logger.info('BOQ migration 19.0.2.3.0: reset %d BOQ record(s) '
                     'from submitted/approved/rejected → draft', reset)

    # ── 3. Ensure partner_type column exists on boq_vendor_rating ─────────
    cr.execute("""
        ALTER TABLE boq_vendor_rating
            ADD COLUMN IF NOT EXISTS partner_type VARCHAR
    """)
