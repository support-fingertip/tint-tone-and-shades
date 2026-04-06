# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions


class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_line_ids = fields.One2many(
        'account.move.approval.line', 'move_id',
        string='Approval Lines', readonly=True,
    )
    approval_state = fields.Selection([
        ('none', 'No Approval'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval Status', default='none', tracking=True, copy=False)

    is_admin = fields.Boolean(
        string='Is Admin', compute='_compute_is_admin',
    )
    hide_post_button = fields.Boolean(
        compute='_compute_hide_post_button_approval', readonly=True,
    )

    @api.depends_context('uid')
    def _compute_is_admin(self):
        is_admin = self.env.user.has_group('base.group_system')
        for move in self:
            move.is_admin = is_admin

    @api.depends('state', 'approval_state', 'auto_post', 'date')
    def _compute_hide_post_button_approval(self):
        is_admin = self.env.user.has_group('base.group_system')
        for record in self:
            # Default logic from account.move
            hide = (
                record.state != 'draft'
                or record.auto_post != 'no'
                and record.date
                and record.date > fields.Date.context_today(record)
            )
            # Hide for non-admin when approval is pending or rejected
            if not hide and not is_admin and record.approval_state in ('pending', 'rejected'):
                hide = True
            record.hide_post_button = hide

    def action_post(self):
        for move in self:
            # Admin users can always post directly
            if move.env.user.has_group('base.group_system'):
                continue

            # If already approved, allow posting
            if move.approval_state == 'approved':
                continue

            # If pending approval, block posting
            if move.approval_state == 'pending':
                raise exceptions.UserError(
                    "This entry is waiting for approval. Please complete all approvals "
                    "in the 'Approval Details' tab before posting."
                )

            # If rejected, block posting
            if move.approval_state == 'rejected':
                raise exceptions.UserError(
                    "This entry has been rejected. Please reset to draft and re-submit."
                )

            # Check if approval is required (only for invoices/bills, not journal entries)
            if move.state == 'draft' and move.move_type != 'entry' and move.approval_state == 'none':
                required_levels = move.env['account.approval.level'].search([
                    ('minimum_amount', '<=', move.amount_total),
                    '|',
                    ('maximum_amount', '>=', move.amount_total),
                    ('maximum_amount', '=', 0),
                ], order='sequence asc')

                if required_levels:
                    move._create_approval_lines(required_levels)
                    move.write({'approval_state': 'pending'})
                    move._check_approval_status()
                    move.message_post(
                        body="This entry requires approval. The approval process has been initiated."
                    )
                    return move._get_refresh_action()

        return super().action_post()

    def _create_approval_lines(self, levels):
        self.approval_line_ids.unlink()
        line_vals = []
        for level in levels:
            line_vals.append((0, 0, {
                'level_id': level.id,
                'move_id': self.id,
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
                    summary=f"Approval required for {self.name or 'Draft Entry'}",
                    user_id=user.id,
                    date_deadline=fields.Date.today(),
                    note=f"Please approve {self.name or 'Draft Entry'} "
                         f"for {self.amount_total} {self.currency_id.symbol}.",
                )
        else:
            self.write({'approval_state': 'approved'})
            self.action_post()

    def button_draft(self):
        res = super().button_draft()
        for move in self:
            if move.approval_line_ids:
                move.approval_line_ids.unlink()
            move.approval_state = 'none'
        return res

    def _get_refresh_action(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
