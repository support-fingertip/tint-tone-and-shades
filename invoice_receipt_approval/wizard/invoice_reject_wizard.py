# -*- coding: utf-8 -*-
from odoo import models, fields


class InvoiceRejectWizard(models.TransientModel):
    _name = 'invoice.reject.wizard'
    _description = 'Invoice / Receipt Rejection Wizard'

    move_id = fields.Many2one('account.move', required=True, ondelete='cascade')
    reason = fields.Text(string='Rejection Reason', required=True)

    def action_confirm_reject(self):
        self.move_id.write({
            'inv_receipt_approval_state': 'rejected',
            'inv_receipt_rejection_reason': self.reason,
        })
        self.move_id.message_post(
            body=f"Rejected by {self.env.user.name}. Reason: {self.reason}"
        )
        return {'type': 'ir.actions.act_window_close'}
