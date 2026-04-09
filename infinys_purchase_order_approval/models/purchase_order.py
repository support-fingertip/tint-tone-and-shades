# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_line_ids = fields.One2many(
        'purchase.order.approval.line', 'order_id',
        string='Approval Lines', readonly=True,
    )

    is_admin = fields.Boolean(
        string='Is Admin', compute='_compute_is_admin',
    )

    @api.depends_context('uid')
    def _compute_is_admin(self):
        is_admin = self.env.user.has_group('base.group_system')
        for order in self:
            order.is_admin = is_admin

    def button_confirm(self):
        self.ensure_one()

        # Admin users can always confirm directly
        if self.env.user.has_group('base.group_system'):
            self._cleanup_approval_activities()
            return super(PurchaseOrder, self).button_confirm()

        # If approval lines exist and all approved, final confirm
        if self.approval_line_ids and all(
            line.status == 'approved' for line in self.approval_line_ids
        ):
            return super(PurchaseOrder, self).button_confirm()

        # If approval is already in progress, block
        if self.approval_line_ids and any(
            line.status in ('pending', 'current') for line in self.approval_line_ids
        ):
            self.message_post(
                body="This order is already waiting for approval. "
                     "Please use the approval buttons in the 'Approval Details' tab."
            )
            return self._get_refresh_action()

        # First, confirm the order to PO state (RFQ → Purchase Order)
        res = super(PurchaseOrder, self).button_confirm()

        # Now check if approval is required based on amount
        required_levels = self.env['purchase.approval.level'].search([
            ('minimum_amount', '<=', self.amount_total),
            '|',
            ('maximum_amount', '>=', self.amount_total),
            ('maximum_amount', '=', 0),
        ], order='sequence asc')

        if required_levels:
            # PO is created, now put it on hold for approval
            self.write({'state': 'to approve'})
            self._create_approval_lines(required_levels)
            self._check_approval_status()
            self.message_post(
                body="Purchase Order created. This order requires approval before it can proceed."
            )
            return self._get_refresh_action()

        return res

    def _create_approval_lines(self, levels):
        self.approval_line_ids.unlink()
        line_vals = []
        for level in levels:
            line_vals.append((0, 0, {
                'level_id': level.id,
                'order_id': self.id,
            }))
        self.write({'approval_line_ids': line_vals})

    def _check_approval_status(self):
        self.ensure_one()
        current_line = self.approval_line_ids.filtered(
            lambda l: l.status == 'current'
        )
        if current_line:
            return

        pending_lines = self.approval_line_ids.filtered(
            lambda l: l.status == 'pending'
        )
        if pending_lines:
            pending_lines[0].status = 'current'

            activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
            for user in pending_lines[0].user_ids:
                self.activity_schedule(
                    activity_type_id=activity_type_id,
                    summary=f"Approval required for Purchase Order {self.name}",
                    user_id=user.id,
                    date_deadline=fields.Date.today(),
                    note=f"Please approve Purchase Order {self.name} "
                         f"for {self.amount_total} {self.currency_id.symbol}.",
                )
        else:
            super(PurchaseOrder, self).button_confirm()

    def _cleanup_approval_activities(self):
        """Remove pending approval activities when order is confirmed/approved by admin."""
        todo_type = self.env.ref('mail.mail_activity_data_todo')
        activities = self.activity_ids.filtered(
            lambda a: a.activity_type_id == todo_type
            and 'Approval required for Purchase Order' in (a.summary or '')
        )
        if activities:
            activities.action_feedback(feedback=f"Order confirmed by {self.env.user.name} (admin bypass)")
        # Mark any pending/current approval lines as approved
        for line in self.approval_line_ids.filtered(lambda l: l.status in ('pending', 'current')):
            line.write({
                'status': 'approved',
                'approved_by_user_id': self.env.user.id,
            })

    def _get_refresh_action(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def button_approve(self, force=False):
        self.ensure_one()
        if self.state == 'to approve' and self.approval_line_ids:
            # Admin can bypass
            if self.env.user.has_group('base.group_system'):
                self._cleanup_approval_activities()
                self.write({
                    'state': 'purchase',
                    'date_approve': fields.Datetime.now(),
                })
                self.filtered(
                    lambda p: p.lock_confirmed_po == 'lock'
                ).write({'locked': True})
                return {}

            all_approved = all(
                line.status == 'approved' for line in self.approval_line_ids
            )
            if not all_approved:
                raise exceptions.UserError(
                    "Please complete all approvals in the 'Approval Details' tab "
                    "first before approving the order."
                )
            self.write({
                'state': 'purchase',
                'date_approve': fields.Datetime.now(),
            })
            self.filtered(
                lambda p: p.lock_confirmed_po == 'lock'
            ).write({'locked': True})
            return {}

        return super(PurchaseOrder, self).button_approve(force=force)
