# wizard/margin_reject_wizard.py

from odoo import models, fields, _
from odoo.exceptions import UserError

class MarginRejectWizard(models.TransientModel):
    _name = 'margin.reject.wizard'
    _description = 'Margin Rejection Wizard'

    purchase_id = fields.Many2one('purchase.order', required=True)
    remarks = fields.Char(string="Remarks", required=True)

    def action_confirm_reject(self):
        self.ensure_one()

        order = self.purchase_id

        if order.margin_approval_status != 'to_approve':
            raise UserError(_("This order is not waiting for margin approval."))

        order.write({
            'margin_approval_status': 'rejected',
            'margin_rejection_reason': self.remarks,
        })