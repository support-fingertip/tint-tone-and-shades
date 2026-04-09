# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Existing BOQ relation ─────────────────────────────────────────────
    boq_ids = fields.One2many(
        comodel_name='boq.boq',
        inverse_name='partner_id',
        string='Bills of Quantities',
    )
    boq_count = fields.Integer(
        string='BOQ Count',
        compute='_compute_boq_count',
    )

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for partner in self:
            partner.boq_count = len(partner.boq_ids)

    def action_view_boqs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills of Quantities'),
            'res_model': 'boq.boq',
            'view_mode': 'list,kanban,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    # ── NEW TASK 1 — Partner Type ─────────────────────────────────────────
    # Determines how this partner is used in the BOQ workflow.
    # • vendor   → Vendor RFQ (material supply, trade execution)
    # • supplier → Supplier RFQ (procurement / main contractor)
    # • employee → Internal resource (no RFQ)
    # • customer → Customer (linked on BOQ header)
    partner_type = fields.Selection(
        selection=[
            ('vendor',   'Vendor'),
            ('supplier', 'Supplier'),
            ('employee', 'Employee'),
            ('customer', 'Customer'),
        ],
        string='Partner Type',
        index=True,
        help='Controls how this partner is used in BOQ workflows. '
             '"Vendor" creates Vendor RFQs; "Supplier" creates Supplier RFQs.',
    )

    # ── NEW — Work Categories (trades this partner handles) ───────────────
    # The user assigns one or more work categories to each vendor/supplier
    # in the contact master.  action_create_rfq() in boq.boq then matches
    # these assignments to the BOQ's selected categories and auto-creates
    # one RFQ per partner containing all BOQ lines from their categories.
    work_category_ids = fields.Many2many(
        comodel_name='boq.category',
        relation='boq_partner_category_rel',
        column1='partner_id',
        column2='category_id',
        string='Work Categories',
        help='Trades / work categories this partner handles.\n'
             'Used to auto-assign this partner to RFQs when Create RFQ is '
             'clicked on a BOQ that shares the same categories.',
    )

    # ── NEW TASK 4 — Vendor Rating ────────────────────────────────────────
    rating_ids = fields.One2many(
        comodel_name='boq.vendor.rating',
        inverse_name='partner_id',
        string='Vendor Ratings',
    )
    avg_rating = fields.Float(
        string='Average Rating',
        compute='_compute_avg_rating',
        store=False,
        digits=(2, 1),
        help='Average of all vendor ratings (1–5 scale).',
    )
    rating_count = fields.Integer(
        string='Rating Count',
        compute='_compute_avg_rating',
        store=False,
    )

    @api.depends('rating_ids', 'rating_ids.rating_int')
    def _compute_avg_rating(self):
        for partner in self:
            ratings = partner.rating_ids.mapped('rating_int')
            valid = [r for r in ratings if r > 0]
            if valid:
                partner.avg_rating = sum(valid) / len(valid)
                partner.rating_count = len(valid)
            else:
                partner.avg_rating = 0.0
                partner.rating_count = 0
