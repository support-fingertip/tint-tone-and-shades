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

        # ── Flow 1: Multi-level approval line rejection ──────────────────────
        if self.approval_line_id:
            line = self.approval_line_id

            if line.status != 'current':
                raise UserError(_("You can only reject the current approval level."))

            if self.env.user not in line.user_ids:
                raise UserError(
                    _("You are not authorized to reject level '%s'.") % line.level_id.name
                )

            line.write({
                'status': 'rejected',
                'rejected_by_user_id': self.env.user.id,
            })

        # ── Flow 2: Simple margin approval rejection ─────────────────────────
        else:
            if order.margin_approval_status != 'to_approve':
                raise UserError(_("This order is not waiting for margin approval."))

            # Validate that the current user is an authorized approver
            low_lines = order.order_line.filtered(
                lambda l: l.is_margin_below_threshold and not l.display_type
            )
            approvers = self.env['res.users']
            for ol in low_lines:
                threshold = self.env['margin.threshold.config'].search([
                    ('category_id', '=', ol.product_id.categ_id.id),
                    ('company_id', '=', order.company_id.id),
                ])
                if threshold and threshold.approver_id:
                    approvers |= threshold.approver_id

            if self.env.user not in approvers:
                raise UserError(
                    _("Only the authorized approver (%s) can reject this margin.")
                    % ', '.join(approvers.mapped('name'))
                )
        order.write({
            'state': 'cancel',
            'margin_approval_status': 'rejected',
            'margin_rejection_reason': self.remarks,
        })

        order.message_post(
            body=_(
                "Margin rejected by %s. Reason: %s"
                + (" [Level: %s]" % self.approval_line_id.level_id.name
                   if self.approval_line_id else "")
            ) % (self.env.user.name, self.remarks)
        )

        # Close pending To-Do activities for this order
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if todo_type:
            user_ids = (
                self.approval_line_id.user_ids.ids
                if self.approval_line_id
                else approvers.ids
            )
            activities = self.env['mail.activity'].search([
                ('res_model', '=', 'purchase.order'),
                ('res_id', '=', order.id),
                ('activity_type_id', '=', todo_type.id),
                ('user_id', 'in', user_ids),
            ])
            if activities:
                activities.action_feedback(
                    feedback=_("Rejected by %s. Reason: %s") % (self.env.user.name, self.remarks)
                )

        return order._get_refresh_action()