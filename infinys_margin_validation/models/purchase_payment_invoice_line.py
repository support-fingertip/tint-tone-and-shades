from odoo import api, fields, models

class PurchasePaymentInvoiceLine(models.Model):
    _name = 'purchase.payment.invoice.line'
    _description = 'Purchase Payment Invoice Line'

    order_id = fields.Many2one(
        'purchase.order',
        string="Purchase Order",
        required=True,
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        related='order_id.partner_id',
        store=True,
        readonly=True
    )

    amount = fields.Float(string="Down Payment (%)")
    comment = fields.Text(string="Remarks")

    bill_id = fields.Many2one(
        'account.move',
        string="Vendor Bill",
        domain="[('move_type','=','in_invoice'), ('invoice_origin','=',order_id.name)]"
    )

    bill_state = fields.Selection(
        related='bill_id.state',
        string="Status",
        store=True,
        readonly=True
    )


