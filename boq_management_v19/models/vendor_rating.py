# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VendorPoRating(models.Model):
    """
    Stores individual vendor ratings per Purchase Order.
    Rating is collected only after the PO is fully completed AND payment
    is released (all invoices paid). Only BOQ Managers can submit ratings.
    """
    _name = 'vendor.po.rating'
    _description = 'Vendor PO Rating'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    vendor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        required=True,
        index=True,
        ondelete='cascade',
    )
    rated_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Rated By',
        default=lambda self: self.env.user,
        readonly=True,
    )

    # Overall rating
    rating = fields.Selection(
        selection=[
            ('1', '1 - Poor'),
            ('2', '2 - Below Average'),
            ('3', '3 - Average'),
            ('4', '4 - Good'),
            ('5', '5 - Excellent'),
        ],
        string='Rating',
        required=True,
    )
    rating_value = fields.Integer(
        string='Rating Value',
        compute='_compute_rating_value',
        store=True,
    )

    # Detailed rating criteria
    quality_rating = fields.Selection(
        selection=[
            ('1', '1 - Poor'),
            ('2', '2 - Below Average'),
            ('3', '3 - Average'),
            ('4', '4 - Good'),
            ('5', '5 - Excellent'),
        ],
        string='Quality',
    )
    delivery_rating = fields.Selection(
        selection=[
            ('1', '1 - Poor'),
            ('2', '2 - Below Average'),
            ('3', '3 - Average'),
            ('4', '4 - Good'),
            ('5', '5 - Excellent'),
        ],
        string='Delivery',
    )
    pricing_rating = fields.Selection(
        selection=[
            ('1', '1 - Poor'),
            ('2', '2 - Below Average'),
            ('3', '3 - Average'),
            ('4', '4 - Good'),
            ('5', '5 - Excellent'),
        ],
        string='Pricing',
    )
    communication_rating = fields.Selection(
        selection=[
            ('1', '1 - Poor'),
            ('2', '2 - Below Average'),
            ('3', '3 - Average'),
            ('4', '4 - Good'),
            ('5', '5 - Excellent'),
        ],
        string='Communication',
    )

    feedback = fields.Text(string='Feedback / Comments')
    rating_date = fields.Datetime(
        string='Rating Date',
        default=fields.Datetime.now,
        readonly=True,
    )

    # PO related info (non-stored for display)
    po_amount_total = fields.Monetary(
        string='PO Amount',
        related='purchase_order_id.amount_total',
        store=False,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='purchase_order_id.currency_id',
        store=False,
    )
    po_state = fields.Selection(
        string='PO Status',
        related='purchase_order_id.state',
        store=False,
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=False,
    )

    _sql_constraints = [
        (
            'unique_po_rating',
            'UNIQUE(purchase_order_id)',
            'A rating already exists for this Purchase Order. '
            'Only one rating per PO is allowed.'
        ),
    ]

    @api.depends('rating')
    def _compute_rating_value(self):
        for rec in self:
            rec.rating_value = int(rec.rating) if rec.rating else 0

    @api.depends('vendor_id', 'purchase_order_id')
    def _compute_display_name(self):
        for rec in self:
            vendor = rec.vendor_id.name or ''
            po = rec.purchase_order_id.name or ''
            rec.display_name = '%s — %s' % (vendor, po)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            po = self.env['purchase.order'].browse(vals.get('purchase_order_id'))
            if po.exists() and po.state not in ('purchase', 'done'):
                raise UserError(_(
                    'Cannot rate vendor: Purchase Order "%s" is not yet confirmed.'
                ) % po.name)
        records = super().create(vals_list)
        # Trigger recompute of vendor average rating
        records.mapped('vendor_id')._compute_vendor_rating()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in (
            'rating', 'quality_rating', 'delivery_rating',
            'pricing_rating', 'communication_rating',
        )):
            self.mapped('vendor_id')._compute_vendor_rating()
        return res

    def unlink(self):
        vendors = self.mapped('vendor_id')
        res = super().unlink()
        vendors._compute_vendor_rating()
        return res
