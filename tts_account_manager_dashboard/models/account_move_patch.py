# -*- coding: utf-8 -*-
"""
Compatibility shim for `is_exact_move_duplicate` on account.move.

Odoo 19's standard account.move list/form views reference this field in
`invisible` / `attrs` expressions for the duplicate-invoice warning banner.
In some installations (partial upgrades, patched builds) the field is present
in the view XML but absent from the model, causing every navigation to an
account.move view to crash with:

    "account.move"."is_exact_move_duplicate" field is undefined

This inherit adds a non-stored, always-False compute so the view parser finds
the field and navigation works correctly.

Guard: we only define the class (and therefore the field) when the `account`
module itself has NOT already registered `is_exact_move_duplicate` on
account.move. This prevents overriding the real duplicate-detection logic in
installations / future Odoo releases that do ship the field natively.
"""
from odoo import models, fields, api
from odoo.addons.account.models import account_move as _account_move_module

_base_move_cls = getattr(_account_move_module, "AccountMove", None)
_field_already_defined = (
    _base_move_cls is not None
    and "is_exact_move_duplicate" in getattr(_base_move_cls, "_fields", {})
)

if not _field_already_defined:

    class AccountMoveDuplicateShim(models.Model):
        _inherit = "account.move"

        is_exact_move_duplicate = fields.Boolean(
            string="Is Exact Duplicate",
            compute="_compute_is_exact_move_duplicate_shim",
            store=False,
            help="Compatibility shim — always False. "
                 "Satisfies view references before the core account module "
                 "ships this field natively.",
        )

        @api.depends("name")
        def _compute_is_exact_move_duplicate_shim(self):
            for move in self:
                move.is_exact_move_duplicate = False
