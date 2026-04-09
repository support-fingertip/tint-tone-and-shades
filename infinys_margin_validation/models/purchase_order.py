# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    margin_approval_status = fields.Selection([
        ('none', 'No Approval Needed'),
        ('to_approve', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Margin Approval Status", default='none', tracking=True, copy=False)

    has_margin_below_threshold = fields.Boolean(
        string="Has Low Margin Lines",
        compute='_compute_has_margin_below_threshold',
        store=True,
    )
    margin_warning_message = fields.Char(
        string="Margin Warning",
        compute='_compute_has_margin_below_threshold',
    )
    is_margin_approver = fields.Boolean(
        string="Is Margin Approver",
        compute='_compute_is_margin_approver',
    )

    @api.depends('order_line.product_id.categ_id')
    def _compute_is_margin_approver(self):
        ThresholdConfig = self.env['margin.threshold.config']
        for order in self:
            approvers = ThresholdConfig.search([
                ('company_id', '=', order.company_id.id),
            ]).mapped('approver_id')
            order.is_margin_approver = self.env.user in approvers

    @api.depends('order_line.is_margin_below_threshold')
    def _compute_has_margin_below_threshold(self):
        for order in self:
            low_lines = order.order_line.filtered(
                lambda l: l.is_margin_below_threshold and not l.display_type
            )
            order.has_margin_below_threshold = bool(low_lines)
            if low_lines:
                warnings = []
                for line in low_lines:
                    threshold = self.env['margin.threshold.config'].search([
                        ('category_id', '=', line.product_id.categ_id.id),
                        ('company_id', '=', order.company_id.id),
                    ], limit=1)
                    min_margin = threshold.minimum_margin if threshold else 0
                    warnings.append(
                        _("%(product)s: Margin %(margin).2f%% is below threshold %(threshold).2f%%.",
                          product=line.product_id.display_name,
                          margin=line.margin_percentage,
                          threshold=min_margin)
                    )
                order.margin_warning_message = ' | '.join(warnings)
            else:
                order.margin_warning_message = False

    def button_confirm(self):
        for order in self:
            if order.has_margin_below_threshold and order.margin_approval_status not in ('approved', 'none'):
                raise UserError(_(
                    "Cannot confirm this order. Some product margins are below the threshold. "
                    "Please request margin approval first."
                ))
            if order.has_margin_below_threshold and order.margin_approval_status == 'none':
                raise UserError(_(
                    "Cannot confirm this order. Some product margins are below the threshold. "
                    "Please request margin approval first."
                ))
        return super().button_confirm()

    def action_request_margin_approval(self):
        self.ensure_one()
        if not self.has_margin_below_threshold:
            raise UserError(_("All margins are within acceptable thresholds. No approval needed."))

        self.margin_approval_status = 'to_approve'

        # Find approvers from threshold config for the affected lines
        low_lines = self.order_line.filtered(lambda l: l.is_margin_below_threshold and not l.display_type)
        approvers = self.env['res.users']
        for line in low_lines:
            threshold = self.env['margin.threshold.config'].search([
                ('category_id', '=', line.product_id.categ_id.id),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if threshold and threshold.approver_id:
                approvers |= threshold.approver_id

        # Create activity for each approver
        for approver in approvers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=approver.id,
                summary=_("Margin Approval Required: %s", self.name),
                note=_(
                    "Purchase order <b>%(order)s</b> has lines with margin below the configured threshold.<br/>"
                    "%(warning)s<br/>"
                    "Please review and approve or reject.",
                    order=self.name,
                    warning=self.margin_warning_message,
                ),
            )

        # Post message in chatter
        self.message_post(
            body=_(
                "Margin approval requested. The following lines have margin below threshold:<br/>%(warning)s",
                warning=self.margin_warning_message,
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

    def action_approve_margin(self):
        self.ensure_one()
        if self.margin_approval_status != 'to_approve':
            raise UserError(_("This order is not waiting for margin approval."))

        # Check if current user is an authorized approver
        low_lines = self.order_line.filtered(lambda l: l.is_margin_below_threshold and not l.display_type)
        approvers = self.env['res.users']
        for line in low_lines:
            threshold = self.env['margin.threshold.config'].search([
                ('category_id', '=', line.product_id.categ_id.id),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if threshold and threshold.approver_id:
                approvers |= threshold.approver_id
        if self.env.user not in approvers:
            raise UserError(_("Only the authorized approver (%s) can approve this margin.", ', '.join(approvers.mapped('name'))))

        self.margin_approval_status = 'approved'

        # Mark related activities as done
        activities = self.activity_ids.filtered(
            lambda a: 'Margin Approval' in (a.summary or '')
        )
        activities.action_feedback(feedback=_("Margin approved by %s", self.env.user.name))

        self.message_post(
            body=_("Margin approved by <b>%s</b>. Order can now be confirmed.", self.env.user.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

    def action_reject_margin(self):
        self.ensure_one()
        if self.margin_approval_status != 'to_approve':
            raise UserError(_("This order is not waiting for margin approval."))

        # Check if current user is an authorized approver
        low_lines = self.order_line.filtered(lambda l: l.is_margin_below_threshold and not l.display_type)
        approvers = self.env['res.users']
        for line in low_lines:
            threshold = self.env['margin.threshold.config'].search([
                ('category_id', '=', line.product_id.categ_id.id),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if threshold and threshold.approver_id:
                approvers |= threshold.approver_id
        if self.env.user not in approvers:
            raise UserError(_("Only the authorized approver (%s) can reject this margin.", ', '.join(approvers.mapped('name'))))

        self.margin_approval_status = 'rejected'

        # Mark related activities as done
        activities = self.activity_ids.filtered(
            lambda a: 'Margin Approval' in (a.summary or '')
        )
        activities.action_feedback(feedback=_("Margin rejected by %s", self.env.user.name))

        self.message_post(
            body=_("Margin rejected by <b>%s</b>.", self.env.user.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
