# -*- coding: utf-8 -*-

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
