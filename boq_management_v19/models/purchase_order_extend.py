# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


# ─── Approval threshold config-parameter key ─────────────────────────────────
_APPROVAL_THRESHOLD_KEY = 'boq.approval.margin_threshold'
_APPROVAL_THRESHOLD_DEFAULT = 15.0   # below 15% margin → needs approval


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with:
    ─ BOQ back-link (non-stored, BUG/Task 3)
    ─ Vendor rating trigger after receipt + invoice paid  (BUG 3)
    ─ Approval state machine for margin < threshold       (BUG 5)
    ─ Margin % computed from BOQ lines                    (BUG 4 / NEW TASK 3)
    ─ Payment status display                              (BUG 6)
    ─ Total tax alias                                     (existing)
    """
    _inherit = 'purchase.order'

    # ══════════════════════════════════════════════════════════════════════════
    # 1.  BOQ BACK-LINK  (non-stored — derived from rfq_ids M2M)
    # ══════════════════════════════════════════════════════════════════════════
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        compute='_compute_boq_id',
        store=False,
        help='BOQ that generated this RFQ (read from the BOQ ↔ RFQ M2M link).',
    )

    @api.depends()
    def _compute_boq_id(self):
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

    # ── BOQ description (non-stored display field) ────────────────────────
    total_tax = fields.Monetary(
        string='Total Tax',
        related='amount_tax',
        store=False,
        currency_field='currency_id',
        help='Total tax on all order lines (alias of amount_tax).',
    )

    boq_description = fields.Text(
        string='BOQ Description',
        compute='_compute_boq_description',
        store=False,
    )

    @api.depends('origin')
    def _compute_boq_description(self):
        """
        Non-stored display field — depends only on `origin` to avoid the
        Odoo 19 warning about non-searchable intermediate computed fields.
        `boq_id` is read live inside the method (it is also non-stored,
        so it is always recomputed on access and never stale).
        """
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

    # ══════════════════════════════════════════════════════════════════════════
    # 2.  MARGIN %  (BUG 4 / NEW TASK 3)
    #     Computed from BOQ lines when available, else from PO lines.
    # ══════════════════════════════════════════════════════════════════════════
    margin_percent = fields.Float(
        string='Margin %',
        compute='_compute_po_margin',
        store=False,
        digits='Discount',
        help='Average margin % computed from BOQ lines assigned to this vendor.',
    )

    @api.depends('order_line', 'order_line.price_unit', 'order_line.product_id',
                 'order_line.product_qty')
    def _compute_po_margin(self):
        for order in self:
            # Prefer BOQ-line margin (more accurate — uses BOQ unit_price as sale price)
            if order.boq_id:
                total_sell = 0.0
                total_cost = 0.0
                for line in order.boq_id.line_ids:
                    if order.partner_id in line.vendor_ids:
                        sell = line.unit_price * line.qty * (
                            1.0 - (line.discount or 0.0) / 100.0
                        )
                        cost = (line.cost_price or 0.0) * line.qty
                        total_sell += sell
                        total_cost += cost
                if total_sell > 0:
                    order.margin_percent = (
                        (total_sell - total_cost) / total_sell * 100.0
                    )
                    continue
            # Fallback: PO line (purchase price vs standard cost)
            total_sell = 0.0
            total_cost = 0.0
            for line in order.order_line:
                sell = line.price_unit * line.product_qty
                cost = (line.product_id.standard_price or 0.0) * line.product_qty
                total_sell += sell
                total_cost += cost
            order.margin_percent = (
                (total_sell - total_cost) / total_sell * 100.0
            ) if total_sell > 0 else 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # 3.  APPROVAL STATE MACHINE  (BUG 5)
    #     approval_state: False → 'pending' → 'approved' / 'rejected'
    #     'Request Approval' button visible when margin < threshold AND no prior approval
    #     'Approve / Reject' buttons visible to managers
    #     'Confirm Order' button remains locked until approved
    # ══════════════════════════════════════════════════════════════════════════
    approval_state = fields.Selection(
        selection=[
            ('pending',  'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Approval Status',
        copy=False,
        tracking=True,
        index=True,
        help='BOQ approval state for low-margin RFQs.',
    )

    needs_approval = fields.Boolean(
        string='Needs Approval',
        compute='_compute_needs_approval',
        store=False,
        help='True when margin is below threshold and approval has not been granted.',
    )

    show_request_approval = fields.Boolean(
        string='Show Request Approval',
        compute='_compute_needs_approval',
        store=False,
    )

    show_approve_btn = fields.Boolean(
        string='Show Approve Button',
        compute='_compute_needs_approval',
        store=False,
    )

    @api.depends('margin_percent', 'approval_state', 'state')
    def _compute_needs_approval(self):
        threshold = self._get_approval_threshold()
        is_manager = self.env.user.has_group(
            'boq_management_v19.group_boq_manager'
        )
        for order in self:
            below_threshold = order.margin_percent < threshold
            not_yet_approved = order.approval_state not in ('approved',)
            in_draft = order.state in ('draft', 'sent')

            order.needs_approval = below_threshold and not_yet_approved and in_draft
            order.show_request_approval = (
                below_threshold and
                not order.approval_state and
                in_draft
            )
            order.show_approve_btn = (
                order.approval_state == 'pending' and is_manager
            )

    @api.model
    def _get_approval_threshold(self):
        try:
            val = float(
                self.env['ir.config_parameter'].sudo().get_param(
                    _APPROVAL_THRESHOLD_KEY, str(_APPROVAL_THRESHOLD_DEFAULT)
                )
            )
        except (ValueError, TypeError):
            val = _APPROVAL_THRESHOLD_DEFAULT
        return val

    def action_request_approval(self):
        """
        BUG 5 — Vendor manager notified when margin < threshold.
        Sets approval_state = 'pending' and sends mail to BOQ Manager group.
        """
        self.ensure_one()
        if not self.show_request_approval:
            raise UserError(_('This order does not require approval.'))
        self.approval_state = 'pending'

        # Find BOQ manager users to notify
        manager_group = self.env.ref(
            'boq_management_v19.group_boq_manager', raise_if_not_found=False
        )
        manager_emails = []
        if manager_group:
            managers = self.env['res.users'].search(
                [('groups_id', 'in', manager_group.id)]
            )
            manager_emails = managers.mapped('partner_id.email')
            manager_emails = [e for e in manager_emails if e]

        body = _(
            'Approval requested for RFQ <b>%(name)s</b>.<br/>'
            'Margin: <b>%(margin).2f%%</b> is below the threshold of <b>%(threshold).2f%%</b>.<br/>'
            'Vendor: %(vendor)s<br/>'
            'Please review and approve or reject.'
        ) % {
            'name': self.name,
            'margin': self.margin_percent,
            'threshold': self._get_approval_threshold(),
            'vendor': self.partner_id.name,
        }
        self.message_post(
            body=body,
            subtype_xmlid='mail.mt_comment',
            partner_ids=[p.id for p in (manager_group.users.mapped('partner_id') if manager_group else [])],
        )
        return True

    def action_approve_rfq(self):
        """BUG 5 — Manager approves the low-margin RFQ."""
        self.ensure_one()
        if not self.env.user.has_group('boq_management_v19.group_boq_manager'):
            raise UserError(_('Only BOQ Managers can approve RFQs.'))
        self.approval_state = 'approved'
        self.message_post(
            body=_('RFQ approved by %s. Order can now be confirmed.') % self.env.user.name,
            subtype_xmlid='mail.mt_note',
        )
        return True

    def action_reject_rfq(self):
        """BUG 5 — Manager rejects the low-margin RFQ."""
        self.ensure_one()
        if not self.env.user.has_group('boq_management_v19.group_boq_manager'):
            raise UserError(_('Only BOQ Managers can reject RFQs.'))
        self.approval_state = 'rejected'
        self.message_post(
            body=_('RFQ rejected by %s.') % self.env.user.name,
            subtype_xmlid='mail.mt_note',
        )
        return True

    def button_confirm(self):
        """
        BUG 5 — Block order confirmation if approval is pending/rejected.
        """
        for order in self:
            if order.needs_approval and order.approval_state != 'approved':
                raise UserError(_(
                    'Cannot confirm order "%s": margin (%.2f%%) is below the '
                    'approval threshold (%.2f%%). '
                    'Please request and obtain manager approval first.'
                ) % (order.name, order.margin_percent, self._get_approval_threshold()))
        return super().button_confirm()

    # ══════════════════════════════════════════════════════════════════════════
    # 4.  VENDOR RATING TRIGGER  (BUG 3 / NEW TASK 4)
    #     'Rate Vendor' button appears ONLY when:
    #     • PO state == 'purchase' (confirmed)
    #     • invoice_status == 'invoiced' (fully invoiced)
    #     • ALL linked stock.picking records are 'done'
    # ══════════════════════════════════════════════════════════════════════════
    show_rate_vendor = fields.Boolean(
        string='Show Rate Vendor',
        compute='_compute_show_rate_vendor',
        store=False,
        help='True when PO is confirmed, fully received, and fully invoiced.',
    )
    vendor_rating_id = fields.Many2one(
        comodel_name='boq.vendor.rating',
        string='Vendor Rating',
        compute='_compute_vendor_rating_id',
        store=False,
    )

    @api.depends('state', 'invoice_status', 'picking_ids', 'picking_ids.state')
    def _compute_show_rate_vendor(self):
        for order in self:
            is_purchase = order.state == 'purchase'
            is_invoiced = order.invoice_status == 'invoiced'
            pickings_done = all(
                p.state == 'done'
                for p in order.picking_ids
            ) if order.picking_ids else False
            order.show_rate_vendor = is_purchase and is_invoiced and pickings_done

    @api.depends('partner_id')
    def _compute_vendor_rating_id(self):
        for order in self:
            rating = self.env['boq.vendor.rating'].search(
                [('purchase_order_id', '=', order.id)], limit=1
            )
            order.vendor_rating_id = rating

    def action_rate_vendor(self):
        """
        BUG 3 / NEW TASK 4 — Open the vendor rating popup form.
        Triggered from the 'Rate Vendor' button (visible only after receipt done + paid).
        """
        self.ensure_one()
        if not self.show_rate_vendor:
            raise UserError(_(
                'Vendor rating is available only after the receipt is done '
                'and the invoice is fully paid.'
            ))
        # If rating already exists, open it; otherwise open empty form
        existing = self.vendor_rating_id
        ctx = {
            'default_purchase_order_id': self.id,
            'default_partner_id': self.partner_id.id,
        }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rate Vendor — %s') % self.partner_id.name,
            'res_model': 'boq.vendor.rating',
            'view_mode': 'form',
            'res_id': existing.id if existing else False,
            'target': 'new',
            'context': ctx,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 5.  PAYMENT STATUS DISPLAY  (BUG 6)
    # ══════════════════════════════════════════════════════════════════════════
    payment_status_display = fields.Char(
        string='Payment Status',
        compute='_compute_payment_status_display',
        store=False,
    )

    @api.depends('invoice_ids', 'invoice_ids.payment_state')
    def _compute_payment_status_display(self):
        label_map = {
            'not_paid':   'Not Paid',
            'in_payment': 'In Payment',
            'paid':       'Fully Paid',
            'partial':    'Partially Paid',
            'reversed':   'Reversed',
            'invoicing_legacy': 'Legacy',
        }
        for order in self:
            states = order.invoice_ids.mapped('payment_state')
            if not states:
                order.payment_status_display = 'Not Paid'
            elif all(s in ('paid', 'in_payment') for s in states):
                order.payment_status_display = 'Fully Paid'
            elif any(s in ('paid', 'in_payment', 'partial') for s in states):
                order.payment_status_display = 'Partially Paid'
            else:
                order.payment_status_display = label_map.get(states[0], 'Not Paid')

    # ══════════════════════════════════════════════════════════════════════════
    # 6.  PORTAL QUOTATION SUBMIT  (NEW TASK 5)
    # ══════════════════════════════════════════════════════════════════════════
    def action_submit_quotation_portal(self):
        """
        NEW TASK 5 — Triggered when vendor clicks 'Submit' on the portal RFQ.
        Sends notification mail and posts to chatter.
        """
        self.ensure_one()
        template = self.env.ref(
            'boq_management_v19.mail_template_vendor_portal_submit',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Fallback: post to chatter
            self.message_post(
                body=_(
                    'The vendor <b>%(vendor)s</b> has submitted the quotation '
                    'successfully against RFQ <b>%(rfq)s</b>. '
                    'Please review and proceed further.'
                ) % {'vendor': self.partner_id.name, 'rfq': self.name},
                subtype_xmlid='mail.mt_comment',
            )
        return True


# ═════════════════════════════════════════════════════════════════════════════
# purchase.order.line EXTENSION  (NEW TASK 3 — margin on comparison view)
# ═════════════════════════════════════════════════════════════════════════════
class PurchaseOrderLineBoqExtend(models.Model):
    """
    NEW TASK 3 — Extend purchase.order.line with cost_price and margin_percent
    so the 'Compare Product Lines' view can display margin side-by-side.
    """
    _inherit = 'purchase.order.line'

    cost_price = fields.Float(
        string='Cost Price',
        compute='_compute_pol_cost_price',
        store=False,
        digits='Product Price',
        help='Product standard price (cost) at the time of quoting.',
    )
    margin_percent = fields.Float(
        string='Margin %',
        compute='_compute_pol_margin',
        store=False,
        digits='Discount',
        help='Margin % = ((price_unit - cost_price) / price_unit) × 100. '
             'Red background if below approval threshold.',
    )
    margin_warning = fields.Boolean(
        string='Below Threshold',
        compute='_compute_pol_margin',
        store=False,
        help='True when margin is below the configured approval threshold.',
    )

    @api.depends('product_id')
    def _compute_pol_cost_price(self):
        for line in self:
            line.cost_price = line.product_id.standard_price if line.product_id else 0.0

    @api.depends('price_unit', 'cost_price')
    def _compute_pol_margin(self):
        threshold = float(
            self.env['ir.config_parameter'].sudo().get_param(
                _APPROVAL_THRESHOLD_KEY, str(_APPROVAL_THRESHOLD_DEFAULT)
            )
        )
        for line in self:
            if line.price_unit > 0:
                margin = ((line.price_unit - (line.cost_price or 0.0)) / line.price_unit) * 100.0
            else:
                margin = 0.0
            line.margin_percent = margin
            line.margin_warning = margin < threshold
