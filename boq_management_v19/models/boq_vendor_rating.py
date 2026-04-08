# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BoqVendorRating(models.Model):
    """
    NEW TASK 4 / BUG 3 — Vendor Rating after receipt.

    A rating record is created after the PO is fully received (stock.picking
    state = 'done') AND the invoice is fully paid.  The rating popup (form view)
    is triggered by the 'Rate Vendor' button on purchase.order, which is only
    visible when those conditions are met.
    """
    _name = 'boq.vendor.rating'
    _description = 'Vendor Rating'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _rec_name = 'partner_id'

    # ── Relations ────────────────────────────────────────────────────────
    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        required=True,
        index=True,
    )

    # ── Rating ───────────────────────────────────────────────────────────
    rating = fields.Selection(
        selection=[
            ('1', '1 — Poor'),
            ('2', '2 — Below Average'),
            ('3', '3 — Average'),
            ('4', '4 — Good'),
            ('5', '5 — Excellent'),
        ],
        string='Rating',
        required=True,
        default='3',
        tracking=True,
    )
    rating_int = fields.Integer(
        string='Rating (int)',
        compute='_compute_rating_int',
        store=True,
    )

    # ── Details ──────────────────────────────────────────────────────────
    comments = fields.Text(string='Comments / Remarks')
    date = fields.Date(string='Rating Date', default=fields.Date.today)

    # ── Context fields (read-only, from PO) ──────────────────────────────
    company_id = fields.Many2one(
        related='purchase_order_id.company_id',
        store=True,
        index=True,
    )

    # ── Constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('unique_po_rating', 'unique(purchase_order_id)',
         'A rating already exists for this Purchase Order. Edit the existing rating.'),
    ]

    @api.depends('rating')
    def _compute_rating_int(self):
        for rec in self:
            try:
                rec.rating_int = int(rec.rating or 0)
            except (ValueError, TypeError):
                rec.rating_int = 0

    @api.constrains('rating')
    def _check_rating(self):
        for rec in self:
            if rec.rating and int(rec.rating) not in range(1, 6):
                raise ValidationError(_('Rating must be between 1 and 5.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.purchase_order_id.message_post(
                body=_('Vendor rated: %s/5 — %s') % (
                    rec.rating, rec.comments or _('No comment.')
                ),
                subtype_xmlid='mail.mt_note',
            )
        return records
