from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


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
        # Validate running payment before calling super
        if self.has_existing_bill:
            self.advance_payment_method = self.advance_payment_method_running

            # Calculate total already paid
            purchase_orders = self.env['purchase.order'].browse(
                self.env.context.get('active_ids', [])
            )
            total_paid = 0.0
            for order in purchase_orders:
                if hasattr(order, 'payment_invoice_ids'):
                    total_paid += sum(order.payment_invoice_ids.mapped('amount'))

            remaining = 100.0 - total_paid

            # Validate against remaining percentage
            if self.advance_payment_method_running == 'percentage':
                if self.amount > remaining:
                    raise UserError(_(
                        "Invalid Percentage!\n\n"
                        "Cannot create Running Bill Payment of %.2f%% because:\n"
                        "• Already paid: %.2f%%\n"
                        "• Maximum allowed: %.2f%%\n\n"
                        "Please enter a percentage between 1%% and %.2f%%."
                    ) % (self.amount, total_paid, remaining, remaining))

            elif self.advance_payment_method_running == 'fixed' and purchase_orders:
                order = purchase_orders[0]
                if order.amount_total > 0:
                    percentage = (self.fixed_amount / order.amount_total) * 100
                    if percentage > remaining:
                        raise UserError(_(
                            "Invalid Amount!\n\n"
                            "Cannot create Running Bill Payment of %.2f (%.2f%%) because:\n"
                            "• Already paid: %.2f%%\n"
                            "• Maximum allowed amount: %.2f"
                        ) % (self.fixed_amount, percentage, total_paid,
                             (remaining / 100) * order.amount_total))
        else:
            self.advance_payment_method = self.advance_payment_method_new

        # Temporarily modify amount to pass Odoo's core validation
        original_amount = self.amount
        if self.has_existing_bill and self.advance_payment_method_running == 'percentage':
            if self.amount > 100:
                self.amount = 100  # Temporarily set to valid value

        result = super().action_create_purchase_advance_payment()

        # Restore original amount
        self.amount = original_amount

        # Rest of your existing code for storing payment_invoice_ids and attachments...
        purchase_orders = self.env['purchase.order'].browse(
            self.env.context.get('active_ids', [])
        )

        for order in purchase_orders:
            bill = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', '=', order.name)
            ], order='id desc', limit=1)

            payment_amount = self.amount if self.advance_payment_method in ['percentage',
                                                                            'fixed'] and self.amount <= 100 else 0

            order.payment_invoice_ids = [(0, 0, {
                'order_id': order.id,
                'bill_id': bill.id if bill else False,
                'amount': payment_amount,
                'comment': self.comment,
                'payment_type': 'running' if self.has_existing_bill else 'down',
            })]

            if self.attachment_ids and bill:
                attachment_ids = []
                for attachment in self.attachment_ids:
                    new_attach = attachment.copy({
                        'name': attachment.name,
                        'res_model': 'account.move',
                        'res_id': bill.id,
                    })
                    attachment_ids.append(new_attach.id)
                bill.bill_attachment_ids = [(6, 0, attachment_ids)]

        return result



class AccountMove(models.Model):
    _inherit = 'account.move'

    bill_attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Bill Attachments",
        readonly=True,
    )