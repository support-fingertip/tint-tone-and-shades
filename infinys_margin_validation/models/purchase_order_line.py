# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    margin_percentage = fields.Float(
        string="Margin (%)",
        compute='_compute_margin_percentage',
        store=True,
        digits=(5, 2),
    )
    is_margin_below_threshold = fields.Boolean(
        string="Margin Below Threshold",
        compute='_compute_margin_percentage',
        store=True,
    )

    @api.depends('price_unit', 'product_id.standard_price', 'product_id.categ_id', 'display_type', 'is_downpayment')
    def _compute_margin_percentage(self):
        ThresholdConfig = self.env['margin.threshold.config']
        for line in self:
            # Skip down payment and section/note lines
            if line.display_type or line.is_downpayment:
                line.margin_percentage = 0.0
                line.is_margin_below_threshold = False
                continue

            product_cost = line.product_id.standard_price
            vendor_price = line.price_unit
            if product_cost:
                line.margin_percentage = ((product_cost - vendor_price) / product_cost) * 100
            else:
                line.margin_percentage = 0.0

            # Check against trade-wise threshold
            threshold = ThresholdConfig.search([
                ('category_id', '=', line.product_id.categ_id.id),
                ('company_id', '=', line.order_id.company_id.id),
            ], limit=1)
            if threshold and line.margin_percentage < threshold.minimum_margin:
                line.is_margin_below_threshold = True
            else:
                line.is_margin_below_threshold = False
