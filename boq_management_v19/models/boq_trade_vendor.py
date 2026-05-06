# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqTradeVendor(models.Model):
    """
    Trade-level vendor/supplier assignment for a BOQ.

    One row per (BOQ, trade, type) triple.
    • partner_type = 'vendor'   → vendor_ids  M2M is shown; supplier_ids hidden
    • partner_type = 'supplier' → supplier_ids M2M is shown; vendor_ids hidden

    Create RFQ on the parent BOQ reads these rows and creates one PO per
    partner, containing ALL lines from that category.
    """
    _name = 'boq.trade.vendor'
    _description = 'Trade-Level Vendor/Supplier Assignment'
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
        string='Work Category',
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
        help='Controls which partner field is visible and which partners '
             'receive RFQs for this category.',
    )
    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_trade_vendor_vendor_rel',
        column1='trade_vendor_id',
        column2='partner_id',
        string='Vendors',
        domain=[('partner_type', '=', 'vendor')],
        help='Visible when Type = Vendor. Each vendor gets a separate RFQ '
             'with all lines from this category.',
    )
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_trade_vendor_supplier_rel',
        column1='trade_vendor_id',
        column2='partner_id',
        string='Suppliers',
        domain=[('partner_type', '=', 'supplier')],
        help='Visible when Type = Supplier. Each supplier gets a separate RFQ '
             'with all lines from this category.',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_line_count',
        store=False,
<<<<<<< HEAD
    )

    # One vendor row + one supplier row allowed per trade per BOQ
    _unique_boq_category_type = models.Constraint(
        'unique(boq_id, category_id, partner_type)',
        'Each trade + type combination can only appear once per BOQ.',
    )

=======
    )

    _sql_constraints = [
        (
            'unique_boq_category_type',
            'unique(boq_id, category_id, partner_type)',
            'Each trade + type combination can only appear once per BOQ.',
        ),
    ]

>>>>>>> main
    @api.depends('boq_id.line_ids', 'category_id')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(
                rec.boq_id.line_ids.filtered(
                    lambda l: l.category_id == rec.category_id
                )
            )
