# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqTradeVendor(models.Model):
    """
    Trade-level vendor/supplier assignment for a BOQ.

    One row per (BOQ, trade, type) triple.  The user picks the Type first
    (Vendor or Supplier), then the matching partner field becomes visible.
    Clicking 'Apply to Lines' writes that selection onto vendor_ids of every
    boq.order.line in that trade.
    """
    _name = 'boq.trade.vendor'
    _description = 'Trade-Level Vendor Assignment'
    _order = 'category_id, partner_type'
    _rec_name = 'category_id'

    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ',
        required=True,
        ondelete='cascade',
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name='boq.category',
        string='Trade',
        required=True,
        ondelete='restrict',
    )
    partner_type = fields.Selection(
        selection=[
            ('vendor',   'Vendor'),
            ('supplier', 'Supplier'),
        ],
        string='Type',
        required=True,
        default='vendor',
        help='Vendor = standard partner; Supplier = partner_type set to "supplier".',
    )
    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_trade_vendor_vendor_rel',
        column1='trade_vendor_id',
        column2='partner_id',
        string='Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Visible when Type = Vendor.',
    )
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_trade_vendor_supplier_rel',
        column1='trade_vendor_id',
        column2='partner_id',
        string='Suppliers',
        domain=[('supplier_rank', '>', 0), ('partner_type', '=', 'supplier')],
        help='Visible when Type = Supplier.',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_line_count',
        store=False,
    )

    # One vendor row + one supplier row allowed per trade per BOQ
    _unique_boq_category_type = models.Constraint(
        'unique(boq_id, category_id, partner_type)',
        'Each trade + type combination can only appear once per BOQ.',
    )

    @api.depends('boq_id.line_ids', 'category_id')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(
                rec.boq_id.line_ids.filtered(
                    lambda l: l.category_id == rec.category_id
                )
            )

    def action_apply_to_lines(self):
        """Write the selected partners onto vendor_ids of all matching lines."""
        for rec in self:
            partners = rec.vendor_ids if rec.partner_type == 'vendor' else rec.supplier_ids
            lines = rec.boq_id.line_ids.filtered(
                lambda l: l.category_id == rec.category_id
            )
            lines.write({'vendor_ids': [(4, p.id) for p in partners]})
        return True
