# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

_INVOICE_TYPES = ('out_invoice', 'in_invoice')
_RECEIPT_TYPES = ('out_receipt', 'in_receipt')
_APPROVAL_MOVE_TYPES = _INVOICE_TYPES + _RECEIPT_TYPES


class AccountMove(models.Model):
    _inherit = 'account.move'

    inv_receipt_approval_state = fields.Selection([
        ('none', 'Not Submitted'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval Status', default='none', copy=False, tracking=True)

    inv_receipt_rejection_reason = fields.Text(
        string='Rejection Reason', copy=False, readonly=True,
    )

    inv_is_associate = fields.Boolean(compute='_compute_inv_approval_groups')
    inv_is_account_manager = fields.Boolean(compute='_compute_inv_approval_groups')

    inv_approval_required = fields.Boolean(
        compute='_compute_inv_approval_required',
        help='True when this document requires approval before posting.',
    )

    @api.depends_context('uid')
    def _compute_inv_approval_groups(self):
        is_manager = self.env.user.has_group('account.group_account_manager')
        is_associate = (
            self.env.user.has_group('account.group_account_invoice')
            and not is_manager
        )
        for move in self:
            move.inv_is_associate = is_associate
            move.inv_is_account_manager = is_manager

    @api.depends('move_type', 'amount_total',
                 'company_id.invoice_approval_active', 'company_id.invoice_approval_amount',
                 'company_id.receipt_approval_active', 'company_id.receipt_approval_amount')
    def _compute_inv_approval_required(self):
        for move in self:
            move.inv_approval_required = move._is_approval_required()

    def _is_approval_required(self):
        self.ensure_one()
        company = self.company_id
        if self.move_type in _INVOICE_TYPES:
            return bool(
                company.invoice_approval_active
                and self.amount_total > company.invoice_approval_amount
            )
        if self.move_type in _RECEIPT_TYPES:
            return bool(
                company.receipt_approval_active
                and self.amount_total > company.receipt_approval_amount
            )
        # Journal entries (payments, expenses, overheads) — Associates always require approval
        if self.move_type == 'entry':
            return True
        return False

    def action_post(self):
        for move in self:
            is_associate = (
                move.env.user.has_group('account.group_account_invoice')
                and not move.env.user.has_group('account.group_account_manager')
            )
            if not is_associate:
                continue
            if move.inv_receipt_approval_state == 'approved':
                continue
            if move.move_type in _APPROVAL_MOVE_TYPES:
                # Invoices / receipts: only block when above the configured threshold
                if not move._is_approval_required():
                    continue
            # Falls here for: above-threshold invoices/receipts, and ALL journal entries
            raise UserError(
                "This document requires approval before posting. "
                "Please use 'Submit for Approval' and wait for an administrator to approve it."
            )
        return super().action_post()

    def action_submit_for_approval(self):
        if self.env.user.has_group('account.group_account_manager'):
            raise UserError("Accounting managers should approve this document directly.")
        for move in self:
            if not move._is_approval_required():
                raise UserError(
                    "Approval is not required for this document "
                    "(amount is within the configured threshold or approval is not enabled)."
                )
            move.write({
                'inv_receipt_approval_state': 'submitted',
                'inv_receipt_rejection_reason': False,
            })
            move.message_post(body=f"Submitted for approval by {self.env.user.name}.")

    def action_approve_invoice(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError("Only accounting managers can approve this document.")
        self.write({'inv_receipt_approval_state': 'approved'})
        self.message_post(body=f"Approved by {self.env.user.name}.")
        return self.action_post()

    def action_reject_invoice(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError("Only accounting managers can reject this document.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rejection Reason',
            'res_model': 'invoice.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    def button_draft(self):
        res = super().button_draft()
        for move in self:
            if move.inv_receipt_approval_state in ('approved', 'submitted'):
                move.inv_receipt_approval_state = 'none'
        return res
