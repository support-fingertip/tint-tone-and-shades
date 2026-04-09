# -*- coding: utf-8 -*-
"""
Migration 19.0.2.1.0 → 19.0.2.2.0 — Remove stale ir.rule on boq.vendor.rating
───────────────────────────────────────────────────────────────────────────────
A legacy ir.rule was created on the boq.vendor.rating model with:

    domain_force = [('res_model', '=', 'res.partner')]

boq.vendor.rating has no `res_model` field, so Odoo raises:

    ValueError: Invalid field boq.vendor.rating.res_model in condition
                ('res_model', '=', 'res.partner')

on every res.partner read that triggers the rating_ids One2many.

This migration permanently removes that stale rule (and any similar one on
the former vendor.po.rating model) from the database.
"""


def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_rule
         WHERE domain_force ILIKE '%res_model%'
           AND model_id IN (
               SELECT id FROM ir_model
                WHERE model IN ('boq.vendor.rating', 'vendor.po.rating')
           )
    """)
