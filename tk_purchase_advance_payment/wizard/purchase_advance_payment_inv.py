# -*- coding: utf-8 -*-
from odoo import models, fields, _, api
from odoo.exceptions import UserError


class PurchaseAdvancePaymentInv(models.TransientModel):
    """
     This wizard facilitates the creation of vendor bills (invoices) for purchase orders,
     allowing users to generate invoices based on different payment methods:
     - Regular Invoice (delivered products)
     - Down Payment by Percentage
     - Down Payment by Fixed Amount
     """
    _name = 'purchase.advance.payment.inv'
    _description = "Purchase Advance Payment Invoice"

    advance_payment_method = fields.Selection([
        ('delivered', 'Regular invoice'),
        ('percentage', 'Down Payment by Percentage'),
        ('fixed', 'Down Payment by Amount')],
        string='Create Invoice',
        default='delivered',
        required=True)
    amount = fields.Float('Down Payment Percentage')
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company.id)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related="company_id.currency_id")
    fixed_amount = fields.Monetary(
        'Down Payment Amount',
        currency_field='currency_id')
    invoice_draft_message = fields.Char(
        default='Bill will be created in draft so that you can review them before validation.')
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string="Purchase Order",
        required=True
    )
    invoice_status_message = fields.Html(string="Invoice Status Message", readonly=True)

    @api.model
    def default_get(self, fields_list):
        """
        Override default_get to prefill purchase_order_id and show an alert message
        if the Purchase Order is fully or partially invoiced.
        """
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        purchase_order = self.env['purchase.order'].browse(active_id)

        if purchase_order and 'invoice_status_message' in fields_list:
            # Find related invoices
            existing_invoices = self.env['account.move'].search([
                ('invoice_origin', '=', purchase_order.name),
                ('move_type', '=', 'in_invoice'),
                ('state', 'not in', ['cancel']),
            ])
            total_invoiced = sum(existing_invoices.mapped('amount_total'))
            if total_invoiced == 0:
                res['invoice_status_message'] = ''
            elif total_invoiced >= purchase_order.amount_total:
                res['invoice_status_message'] = (
                    '<div class="alert alert-success text-center" role="alert">'
                    'This Purchase Order is fully invoiced.'
                    '</div>'
                )
            else:
                res['invoice_status_message'] = ''
            res['purchase_order_id'] = active_id

        return res

    def action_process_purchase_advance_payment_bill(self, downpayment_amount, purchase_order,
                                                     purchase_advance_product):
        """
        Create a vendor bill and a corresponding down payment line on the purchase order.
        """
        existing_section = self.env['purchase.order.line'].search([
            ('order_id', '=', purchase_order.id),
            ('display_type', '=', 'line_section'),
            ('name', '=', 'Down Payment'),
        ])
        if not existing_section:
            # Create a section line
            self.env['purchase.order.line'].create({
                'display_type': 'line_section',
                'name': 'Down Payment',
                'order_id': purchase_order.id,
                'product_qty': 0,
                'sequence': 90
            })
        # Create the down payment line
        po_line_id = self.env['purchase.order.line'].create({
            'product_id': purchase_advance_product.id,
            'name': f"Down Payment\n{purchase_order.name}",
            'product_qty': 0,
            'qty_invoiced': 1,
            'price_unit': round(downpayment_amount, 2),
            'order_id': purchase_order.id,
            'tax_ids': [(6, 0, [])],
            'sequence': 90
        })
        # Create Vendor Bill
        vendor_bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': purchase_order.partner_id.id,
            'invoice_origin': purchase_order.name,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': purchase_advance_product.id,
                    'name': f"Down Payment\n{purchase_order.name}",
                    'quantity': 1,
                    'price_unit': round(downpayment_amount, 2),
                    'purchase_line_id': po_line_id.id,
                    'tax_ids': [(6, 0, [])],
                }),
            ]
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': vendor_bill.id,
            'target': 'current',
        }

    def action_create_purchase_advance_payment(self):
        """
        Creates a vendor bill for selected purchase orders based on the advance payment method.
        Validates:
           - Full invoicing: Prevents duplicate invoices if the total amount is covered.
           - Payment method: Processes percentage or fixed down payments.
           - Down Payment section: Adds if missing.
           - Product reception: Requires full receipt before final invoicing.
        Returns:
            dict: Action to open the created vendor bill.
        Raises:
            UserError: On invalid payment details, or premature final invoicing.
        """
        purchase_order = self.env['purchase.order'].browse(self.env.context.get('active_id'))
        # Get the Down Payment Product from settings
        purchase_advance_product_id = self.env['ir.config_parameter'].sudo().get_param(
            'purchase.advance_payment_product_id'
        )
        purchase_advance_product = self.env['product.product'].browse(
            int(purchase_advance_product_id)
        )
        if (self.advance_payment_method in ('percentage', 'fixed')
                and not purchase_advance_product_id):
            raise UserError("No Purchase Advance Payment Product configured in settings.")
        existing_invoices = self.env['account.move'].search([
            ('invoice_origin', '=', purchase_order.name),
            ('move_type', '=', 'in_invoice'),
            ('state', 'not in', ['cancel'])
        ])
        remaining_amount = (
                purchase_order.amount_total - sum(existing_invoices.mapped('amount_total')))
        downpayment_amount = 0
        if self.advance_payment_method == 'percentage':
            if not 0 < self.amount <= 100:
                raise UserError("Invalid percentage! Must be between 1% and 100%.")
            downpayment_amount = (self.amount / 100) * remaining_amount

        if self.advance_payment_method == 'fixed':
            if self.fixed_amount > remaining_amount:
                raise UserError(_(
                    f"The down payment amount must be less than the purchase order amount due : "
                    f"{purchase_order.currency_id.symbol} {remaining_amount:.2f}."
                ))
            downpayment_amount = self.fixed_amount

        if self.advance_payment_method in ('percentage', 'fixed'):
            vendor_bill = (
                self.action_process_purchase_advance_payment_bill(
                    downpayment_amount,
                    purchase_order,
                    purchase_advance_product))
            return vendor_bill

        existing_down_payment = self.env['account.move'].search([
            ('invoice_origin', '=', purchase_order.name),
            ('move_type', '=', 'in_invoice'),
            ('state', '!=', 'cancel')
        ], limit=1)

        # Check if products are received (all lines must be received)
        all_products_received = all(
            line.qty_received >= line.product_qty
            for line in purchase_order.order_line)
        if existing_down_payment and not all_products_received:
            raise UserError(
                _("You must receive and validate the ordered products "
                  "before generating the final invoice."))
        purchase_order.action_create_invoice()
