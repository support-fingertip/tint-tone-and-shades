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

    def _get_total_paid_percentage(self, purchase_orders):
        """
        Returns the total percentage already paid across all payment_invoice_ids.
        Down payment amounts are stored as percentage directly.
        Fixed running payments are converted to percentage based on order total.
        """
        total_percentage = 0.0
        for order in purchase_orders:
            if not hasattr(order, 'payment_invoice_ids'):
                continue
            for inv in order.payment_invoice_ids:
                if inv.payment_type == 'down':
                    total_percentage += inv.amount or 0.0
                elif inv.payment_type == 'running':
                    total_percentage += inv.amount or 0.0
        return total_percentage

    def action_create_purchase_advance_payment(self):
        purchase_orders = self.env['purchase.order'].browse(self.env.context.get('active_ids', []))
        if self.has_existing_bill:
            # ── Running payment path ──────────────────────────────────────────
            self.advance_payment_method = self.advance_payment_method_running
            payment_type = 'running'

            total_paid = self._get_total_paid_percentage(purchase_orders)
            remaining = 100.0 - total_paid

            if self.advance_payment_method_running == 'percentage':
                if self.amount <= 0:
                    raise UserError(_("Please enter a percentage greater than 0."))
                if self.amount > remaining:
                    raise UserError(_(
                        "Invalid Percentage!\n\n"
                        "Cannot create Running Bill Payment of %.2f%% because:\n"
                        "• Already paid: %.2f%%\n"
                        "• Maximum allowed: %.2f%%\n\n"
                        "Please enter a value between 1%% and %.2f%%."
                    ) % (self.amount, total_paid, remaining, remaining))
                payment_amount = self.amount

            elif self.advance_payment_method_running == 'fixed':
                if not purchase_orders:
                    raise UserError(_("No purchase order found."))
                order = purchase_orders[0]
                if order.amount_total <= 0:
                    raise UserError(_("Purchase order total must be greater than zero."))
                percentage = (self.fixed_amount / order.amount_total) * 100.0
                if percentage > remaining:
                    max_allowed = (remaining / 100.0) * order.amount_total
                    raise UserError(_(
                        "Invalid Amount!\n\n"
                        "Cannot create Running Bill Payment of %.2f (%.2f%%) because:\n"
                        "• Already paid: %.2f%%\n"
                        "• Maximum allowed amount: %.2f"
                    ) % (self.fixed_amount, percentage, total_paid, max_allowed))
                payment_amount = percentage

            else:
                # 'regular' running bill
                payment_amount = 0.0

        else:
            # ── First / Down payment path ─────────────────────────────────────
            self.advance_payment_method = self.advance_payment_method_new
            payment_type = 'down'

            if self.advance_payment_method_new == 'percentage':
                payment_amount = self.amount
            elif self.advance_payment_method_new == 'fixed':
                if purchase_orders and purchase_orders[0].amount_total > 0:
                    payment_amount = (self.fixed_amount / purchase_orders[0].amount_total) * 100.0
                else:
                    payment_amount = 0.0
            else:
                payment_amount = 0.0

        # ── Snapshot existing PO order lines and bills BEFORE super() ─────────
        existing_line_ids = {}
        for order in purchase_orders:
            existing_line_ids[order.id] = set(order.order_line.ids)

        existing_bill_ids = set(self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('invoice_origin', 'in', purchase_orders.mapped('name')),
        ]).ids)

        # ── Call Odoo core ────────────────────────────────────────────────────
        result = super().action_create_purchase_advance_payment()

        # ── Rename "Down Payment" → "Running Payment" for running bills ───────
        if payment_type == 'running':
            # 1. Fix PO order lines
            for order in purchase_orders:
                new_lines = order.order_line.filtered(
                    lambda l, oid=order.id: l.id not in existing_line_ids.get(oid, set())
                )
                new_section_lines = new_lines.filtered(
                    lambda l: l.display_type == 'line_section'
                )
                new_advance_lines = new_lines.filtered(
                    lambda l: not l.display_type
                )

                if new_section_lines:
                    # A new section was created — just rename it
                    new_section_lines.filtered(
                        lambda l: l.name == 'Down Payment'
                    ).write({'name': 'Running Payment'})
                elif new_advance_lines:
                    # No new section created (reused existing "Down Payment" section).
                    # Use max sequence of ALL existing lines so "Running Payment"
                    # section always appears AFTER the entire "Down Payment" block.
                    existing_lines = order.order_line.filtered(
                        lambda l, oid=order.id: l.id in existing_line_ids.get(oid, set())
                    )
                    max_existing_seq = max(existing_lines.mapped('sequence'), default=10)

                    # Push new advance lines to sit after the new section header
                    for i, line in enumerate(new_advance_lines.sorted('sequence')):
                        line.sequence = max_existing_seq + 2 + i

                    # Insert "Running Payment" section between existing and new advance lines
                    order.write({'order_line': [(0, 0, {
                        'display_type': 'line_section',
                        'name': 'Running Payment',
                        'sequence': max_existing_seq + 1,
                        'product_qty': 0,
                    })]})

                # Rename the advance payment line description on the PO
                for line in new_advance_lines:
                    if 'Down Payment' in (line.name or ''):
                        line.name = line.name.replace('Down Payment', 'Running Payment')

            # 2. Rename invoice line label on the newly created bill
            new_bills = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', 'in', purchase_orders.mapped('name')),
                ('id', 'not in', list(existing_bill_ids)),
            ])
            for bill in new_bills:
                for line in bill.invoice_line_ids:
                    if 'Down Payment' in (line.name or ''):
                        line.name = line.name.replace('Down Payment', 'Running Payment')

        # ── Store custom payment lines & attachments ──────────────────────────
        for order in purchase_orders:
            bill = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', '=', order.name)
            ], order='id desc', limit=1)

            order.payment_invoice_ids = [(0, 0, {
                'order_id': order.id,
                'bill_id': bill.id if bill else False,
                'amount': payment_amount,
                'comment': self.comment,
                'payment_type': payment_type,
            })]

            if self.attachment_ids and bill:
                new_attachment_ids = []
                for attachment in self.attachment_ids:
                    new_attach = attachment.copy({
                        'name': attachment.name,
                        'res_model': 'account.move',
                        'res_id': bill.id,
                    })
                    new_attachment_ids.append(new_attach.id)
                bill.bill_attachment_ids = [(6, 0, new_attachment_ids)]

        return result



class AccountMove(models.Model):
    _inherit = 'account.move'

    bill_attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Bill Attachments",
        readonly=True,
    )