# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseOrderBoqExtend(models.Model):
    
    _inherit = 'purchase.order'

    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        compute='_compute_boq_id',
        store=False,
        help='BOQ that generated this RFQ (read from the BOQ ↔ RFQ M2M link).',
    )

    @api.depends()
    def _compute_boq_id(self):
      
        real = self.filtered(lambda r: isinstance(r.id, int))
        (self - real).update({'boq_id': False})   

        if not real:
            return

        self.env.cr.execute(
            """
            SELECT purchase_id, boq_id
              FROM boq_boq_purchase_order_rel
             WHERE purchase_id IN %s
            """,
            (tuple(real.ids),)
        )
        mapping = {row[0]: row[1] for row in self.env.cr.fetchall()}
        for order in real:
            order.boq_id = mapping.get(order.id, False)

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
          
            total_std = 0.0
            total_po = 0.0
            for line in order.order_line:
                std = (line.product_id.standard_price or 0.0) * line.product_qty
                po = line.price_unit * line.product_qty
                total_std += std
                total_po += po
            order.margin_percent = (
                (total_std - total_po) / total_std * 100.0
            ) if total_std > 0 else 0.0

   
    partner_type = fields.Selection(
        related='partner_id.partner_type',
        string='Partner Type',
        store=False,
    )

    show_rate_vendor = fields.Boolean(
        string='Show Rate Button',
        compute='_compute_show_rate_vendor',
        store=False,
        help='True when PO is confirmed, fully received, and fully invoiced.',
    )
    vendor_rating_id = fields.Many2one(
        comodel_name='boq.vendor.rating',
        string='Partner Rating',
        compute='_compute_vendor_rating_id',
        store=False,
    )

    @api.depends('state', 'picking_ids', 'picking_ids.state')
    def _compute_show_rate_vendor(self):
        for order in self:
            is_purchase = order.state == 'purchase'
            pickings_done = (
                all(p.state == 'done' for p in order.picking_ids)
                if order.picking_ids else True
            )
            order.show_rate_vendor = is_purchase and pickings_done

    @api.depends('partner_id')
    def _compute_vendor_rating_id(self):
        for order in self:
            rating = self.env['boq.vendor.rating'].search(
                [('purchase_order_id', '=', order.id)], limit=1
            )
            order.vendor_rating_id = rating

    def action_rate_vendor(self):
        """
        Open the rating popup form for the PO partner (vendor or supplier).
        Button is visible only after: receipt done + invoice fully paid.
        Works for both partner_type = 'vendor' and 'supplier'.
        """
        self.ensure_one()
        if not self.show_rate_vendor:
            raise UserError(_(
                'Rating is available only after the Purchase Order is confirmed '
                'and all deliveries are received.'
            ))
        title = _('Rate Vendor — %s') % self.partner_id.name

        existing = self.vendor_rating_id
        ctx = {
            'default_purchase_order_id': self.id,
            'default_partner_id': self.partner_id.id,
        }
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'boq.vendor.rating',
            'view_mode': 'form',
            'res_id': existing.id if existing else False,
            'target': 'new',
            'context': ctx,
        }

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

    def action_submit_quotation_portal(self):
        
        self.ensure_one()
        template = self.env.ref(
            'boq_management_v19.mail_template_vendor_portal_submit',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            self.message_post(
                body=_(
                    'The vendor <b>%(vendor)s</b> has submitted the quotation '
                    'successfully against RFQ <b>%(rfq)s</b>. '
                    'Please review and proceed further.'
                ) % {'vendor': self.partner_id.name, 'rfq': self.name},
                subtype_xmlid='mail.mt_comment',
            )
        return True

class PurchaseOrderLineBoqExtend(models.Model):
    
    _inherit = 'purchase.order.line'

    cost_price = fields.Float(
        string='Std Cost',
        compute='_compute_pol_cost_price',
        store=False,
        digits='Product Price',
        help='Product standard cost (internal reference price).',
    )
    margin_percent = fields.Float(
        string='Savings %',
        compute='_compute_pol_margin',
        store=False,
        digits='Discount',
        help='Savings % = (standard_cost − vendor_price) / standard_cost × 100.\n'
             'Positive = vendor is cheaper than our internal standard (good deal).\n'
             'Negative = vendor is quoting above our standard cost.',
    )
    customer_price = fields.Float("Customer Price")

    @api.depends('product_id')
    def _compute_pol_cost_price(self):
        for line in self:
            line.cost_price = line.product_id.standard_price if line.product_id else 0.0

    @api.depends('price_unit', 'customer_price', 'product_id')
    def _compute_pol_margin(self):
        for line in self:
            std = line.customer_price or 0.0
            if not std:
                std = line.product_id.standard_price or 0.0
            if std > 0:
                line.margin_percent = (std - line.price_unit) / std * 100.0
            else:
                line.margin_percent = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('customer_price'):
                vals['price_unit'] = 0.0
        return super().create(vals_list)

    @api.onchange('product_id')
    def onchange_product_id(self):
        parent = super()
        res = parent.onchange_product_id() if hasattr(parent, 'onchange_product_id') else None
        self.price_unit = 0.0
        return res

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        existing_price = self.price_unit
        parent = super()
        if hasattr(parent, '_onchange_quantity'):
            parent._onchange_quantity()
        self.price_unit = existing_price
