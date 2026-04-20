from odoo import fields, models

class PurchaseAdvancePaymentInv(models.TransientModel):
    _inherit = 'purchase.advance.payment.inv'

    comment = fields.Text(string="Remarks")

    def action_create_purchase_advance_payment(self):
        result = super().action_create_purchase_advance_payment()

        purchase_orders = self.env['purchase.order'].browse(
            self.env.context.get('active_ids', [])
        )

        for order in purchase_orders:

            # ✅ Get latest vendor bill for this PO
            bill = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', '=', order.name)
            ], order='id desc', limit=1)

            order.payment_invoice_ids = [(0, 0, {
                'order_id': order.id,
                'bill_id': bill.id if bill else False,   # ✅ FIX
                'amount': self.amount,
                'comment': self.comment,
            })]

        return result