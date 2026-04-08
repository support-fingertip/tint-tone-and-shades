# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqTradeVendor(models.Model):
    """
    Trade-level vendor/supplier assignment for a BOQ.

    One row per (BOQ, trade/category) pair. The user selects which vendors
    (partner_type = vendor or unset) and which suppliers (partner_type = supplier)
    cover that trade. Clicking 'Apply to Lines' writes the combined selection
    onto vendor_ids of every boq.order.line in that trade.
    """
    _name = 'boq.trade.vendor'
    _description = 'Trade-Level Vendor Assignment'
    _order = 'category_id'
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
    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_trade_vendor_vendor_rel',
        column1='trade_vendor_id',
        column2='partner_id',
        string='Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors (partner_type = vendor or unset) for this trade.',
    )
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_trade_vendor_supplier_rel',
        column1='trade_vendor_id',
        column2='partner_id',
        string='Suppliers',
        domain=[('supplier_rank', '>', 0), ('partner_type', '=', 'supplier')],
        help='Suppliers (partner_type = supplier) for this trade.',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_line_count',
        store=False,
    )

    _unique_boq_category = models.Constraint(
        'unique(boq_id, category_id)',
        'Each trade can only have one vendor assignment row per BOQ.',
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
        """Write vendor+supplier selection onto all matching BOQ lines."""
        for rec in self:
            all_partners = rec.vendor_ids | rec.supplier_ids
            lines = rec.boq_id.line_ids.filtered(
                lambda l: l.category_id == rec.category_id
            )
            lines.write({'vendor_ids': [(6, 0, all_partners.ids)]})
        return True
