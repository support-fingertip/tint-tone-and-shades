# -*- coding: utf-8 -*-
"""
Compatibility shim: registers `is_exact_move_duplicate` on account.move.

Odoo 19's standard account.move views reference this field in invisible/attrs
expressions for the duplicate-invoice warning banner. In some installations
(partial upgrades, patched builds) the field is present in the view XML but
absent from the model, causing every navigation to an account.move view to
crash with:

    "account.move"."is_exact_move_duplicate" field is undefined

Adding a non-stored, always-False compute satisfies the view parser so form
and list navigation works correctly.

No guard is used: redefining a non-stored compute field on a model is safe in
all Odoo versions — our definition is simply merged into the registry and
returns False (no duplicate flagging). If a later Odoo update ships the real
field with proper logic, removing this file restores the original behaviour.

IMPORTANT: changes to this file take effect only after:
    odoo -u tts_account_manager_dashboard
"""
from odoo import models, fields, api


class AccountMoveDuplicateShim(models.Model):
    _inherit = "account.move"

    is_exact_move_duplicate = fields.Boolean(
        string="Is Exact Duplicate",
        compute="_compute_is_exact_move_duplicate_shim",
        store=False,
    )

    @api.depends("name")
    def _compute_is_exact_move_duplicate_shim(self):
        for move in self:
            move.is_exact_move_duplicate = False
