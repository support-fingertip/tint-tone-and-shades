# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with a back-link to the originating BOQ record
    and a convenience total_tax field.

    Task 3 — RFQ inside BOQ.

    IMPORTANT — no stored fields on purchase.order:
    Both boq_id and total_tax are non-stored so they never need a DB column
    and no module upgrade / ALTER TABLE is required on purchase_order.

    boq_id   — computed from the existing boq_boq_purchase_order_rel M2M table
                that is created by boq.boq.rfq_ids (already exists after install).
    total_tax — non-stored related alias of amount_tax (reads live, no column).
    """
    _inherit = 'purchase.order'

    # ── BOQ Back-link (non-stored — derived from rfq_ids M2M) ────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        compute='_compute_boq_id',
        store=False,          # No DB column on purchase_order table
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
        store=False,          # No DB column on purchase_order table
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
