# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with:
    - BOQ back-link (non-stored, from M2M table)
    - Vendor Rating (stored, editable after all receipts done)
    - All Receipts Done flag (non-stored, controls rating visibility)
    - Payment Status Display (non-stored computed)
    """
    _inherit = 'purchase.order'

    # ── BOQ Back-link (non-stored — derived from rfq_ids M2M) ────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        compute='_compute_boq_id',
        store=False,
        help='BOQ that generated this RFQ (read from the BOQ ↔ RFQ M2M link).',
    )

    @api.depends()
    def _compute_boq_id(self):
        """
        Derive boq_id by querying the boq_boq_purchase_order_rel table
        which is owned by boq.boq.rfq_ids (Many2many, already exists).
        Single batch query — no N+1 problem.
        """
        if not self.ids:
            return
        self.env.cr.execute(
            """
            SELECT purchase_id, boq_id
              FROM boq_boq_purchase_order_rel
             WHERE purchase_id IN %s
            """,
            (tuple(self.ids),)
        )
        mapping = {row[0]: row[1] for row in self.env.cr.fetchall()}
        for order in self:
            order.boq_id = mapping.get(order.id, False)

    # ── Total Tax (non-stored related — reads live from amount_tax) ───────
    total_tax = fields.Monetary(
        string='Total Tax',
        related='amount_tax',
        store=False,
        currency_field='currency_id',
        help='Total tax on all order lines (alias of amount_tax).',
    )

    # ── BOQ description (non-stored computed display field) ───────────────
    boq_description = fields.Text(
        string='BOQ Description',
        compute='_compute_boq_description',
        store=False,
        help='Combines origin and BOQ details for display on RFQ forms.',
    )

    @api.depends('origin', 'boq_id', 'boq_id.name', 'boq_id.project_name')
    def _compute_boq_description(self):
        for order in self:
            parts = []
            if order.boq_id:
                parts.append(_('BOQ: %s') % order.boq_id.name)
                if order.boq_id.project_name:
                    parts.append(_('Project: %s') % order.boq_id.project_name)
            if order.origin:
                parts.append(order.origin)
            order.boq_description = '\n'.join(parts) if parts else ''

    # ── Vendor Rating (STORED — user fills in after receipt is done) ──────
    # Persisted on purchase_order table. Only visible/editable when
    # all_receipts_done is True (controlled via invisible in the view).
    vendor_rating = fields.Selection(
        selection=[
            ('1', '1 - Poor'),
            ('2', '2 - Fair'),
            ('3', '3 - Good'),
            ('4', '4 - Very Good'),
            ('5', '5 - Excellent'),
        ],
        string='Vendor Rating',
        tracking=True,
        help='Rate vendor delivery, quality and responsiveness.\n'
             'Becomes editable once all goods receipts are completed.',
    )

    # ── All Receipts Done (non-stored — drives vendor_rating visibility) ──
    all_receipts_done = fields.Boolean(
        string='All Receipts Done',
        compute='_compute_all_receipts_done',
        store=False,
    )

    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_all_receipts_done(self):
        for order in self:
            # Only consider non-cancelled receipts
            active_picks = order.picking_ids.filtered(lambda p: p.state != 'cancel')
            if active_picks:
                order.all_receipts_done = all(
                    p.state == 'done' for p in active_picks
                )
            else:
                order.all_receipts_done = False

    # ── Payment Status Display (non-stored computed) ───────────────────────
    payment_status_display = fields.Char(
        string='Payment Status',
        compute='_compute_payment_status_display',
        store=False,
    )

    @api.depends('invoice_ids', 'invoice_ids.payment_state', 'invoice_ids.state',
                 'invoice_status')
    def _compute_payment_status_display(self):
        for order in self:
            posted = order.invoice_ids.filtered(lambda i: i.state == 'posted')
            if not posted:
                order.payment_status_display = 'Not Invoiced'
            else:
                states = posted.mapped('payment_state')
                if all(s == 'paid' for s in states):
                    order.payment_status_display = 'Fully Paid'
                elif any(s in ('paid', 'partial') for s in states):
                    order.payment_status_display = 'Partially Paid'
                else:
                    order.payment_status_display = 'Unpaid'

    # ── Open BOQ ───────────────────────────────────────────────────────────
    def action_open_boq(self):
        """Open the linked BOQ record in form view."""
        self.ensure_one()
        if not self.boq_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ — %s') % self.boq_id.name,
            'res_model': 'boq.boq',
            'res_id': self.boq_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
