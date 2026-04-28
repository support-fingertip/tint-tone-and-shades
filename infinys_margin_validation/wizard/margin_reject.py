from odoo import models, fields, _
from odoo.exceptions import UserError


class MarginRejectWizard(models.TransientModel):
    _name = 'margin.reject.wizard'
    _description = 'Margin Rejection Wizard'

    purchase_id = fields.Many2one('purchase.order', required=True)
    approval_line_id = fields.Many2one('purchase.order.approval.line')
    remarks = fields.Char(string="Remarks", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        order = self.purchase_id

        # --- Approval Line rejection ---
        if self.approval_line_id:
            line = self.approval_line_id

            if line.status != 'current':
                raise UserError(_("You can only reject the current approval level."))

            if self.env.user not in line.user_ids:
                raise UserError(
                    _("You are not authorized to reject level '%s'.") % line.level_id.name)

            line.write({
                'status': 'rejected',
                'rejected_by_user_id': self.env.user.id,
            })
            order.write({
                'state': 'cancel',
                'margin_rejection_reason': self.remarks,
                'margin_approval_status': 'rejected',
            })
            order.message_post(
                body=_("Approval Level '%s' rejected by %s. Reason: %s")
                % (line.level_id.name, self.env.user.name, self.remarks)
            )

            todo_type = self.env.ref('mail.mail_activity_data_todo')
            activities = self.env['mail.activity'].search([
                ('res_model', '=', 'purchase.order'),
                ('res_id', '=', order.id),
                ('activity_type_id', '=', todo_type.id),
                ('user_id', 'in', line.user_ids.ids),
            ])
            if activities:
                activities.action_feedback(
                    feedback=_("Rejected by %s. Reason: %s") % (self.env.user.name, self.remarks)
                )

            return order._get_refresh_action()

        # --- Margin Approval rejection (original flow) ---
        if order.margin_approval_status != 'to_approve':
            raise UserError(_("This order is not waiting for margin approval."))

        order.write({
            'margin_approval_status': 'rejected',
            'margin_rejection_reason': self.remarks,
        })