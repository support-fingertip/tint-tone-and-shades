from odoo import fields, models, api

class PurchaseAdvancePaymentInv(models.TransientModel):
    _inherit = 'purchase.advance.payment.inv'

    comment = fields.Text(string="Remarks")

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Attachments"
    )

    has_existing_bill = fields.Boolean(
        string="Has Existing Bill",
        store=False,
    )

    # Shown when NO existing bill
    advance_payment_method_new = fields.Selection([
        ('regular', 'Regular Invoice'),
        ('percentage', 'Down Payment by Percentage'),
        ('fixed', 'Down Payment by Amount'),
    ], string='Create Invoice', default='regular')

    # Shown when existing bill IS found
    advance_payment_method_running = fields.Selection([
        ('regular', 'Regular Invoice'),
        ('percentage', 'Running Bill Payment Percentage'),
        ('fixed', 'Running Bill Payment Amount'),
    ], string='Create Invoice', default='regular')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        has_bill = False

        if active_ids:
            orders = self.env['purchase.order'].browse(active_ids)
            order_names = orders.mapped('name')
            existing_bill = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', 'in', order_names),
            ], limit=1)
            has_bill = bool(existing_bill)

        res['has_existing_bill'] = has_bill

        # Sync default value to both fields
        default_method = res.get('advance_payment_method', 'regular')
        res['advance_payment_method_new'] = default_method
        res['advance_payment_method_running'] = default_method

        return res

    def action_create_purchase_advance_payment(self):

        if self.has_existing_bill:
            self.advance_payment_method = self.advance_payment_method_running
            payment_type = 'running'
        else:
            self.advance_payment_method = self.advance_payment_method_new
            payment_type = 'down'

        result = super().action_create_purchase_advance_payment()

        purchase_orders = self.env['purchase.order'].browse(
            self.env.context.get('active_ids', [])
        )

        for order in purchase_orders:
            bill = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', '=', order.name)
            ], order='id desc', limit=1)

            # Store your custom line
            order.payment_invoice_ids = [(0, 0, {
                'order_id': order.id,
                'bill_id': bill.id if bill else False,
                'amount': self.amount,
                'comment': self.comment,
                'payment_type': payment_type,
            })]

            # ✅ STEP 1: Attach + store in field
            if self.attachment_ids and bill:
                attachment_ids = []

                for attachment in self.attachment_ids:
                    new_attach = attachment.copy({
                        'name': attachment.name,
                        'res_model': 'account.move',
                        'res_id': bill.id,
                    })
                    attachment_ids.append(new_attach.id)

                # 👉 Store into your field
                bill.bill_attachment_ids = [(6, 0, attachment_ids)]

        return result



class AccountMove(models.Model):
    _inherit = 'account.move'

    bill_attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Bill Attachments",
        readonly=True,
    )