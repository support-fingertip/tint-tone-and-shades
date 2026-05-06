# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions

class PurchaseOrderApprovalLine(models.Model):
    _name = 'purchase.order.approval.line'
    _description = 'Purchase Order Approval Line'
    _order = 'sequence'

    order_id = fields.Many2one('purchase.order', string='Purchase Order', required=True, ondelete='cascade')
    level_id = fields.Many2one('purchase.approval.level', string='Approval Level', required=True)
    sequence = fields.Integer(string='Sequence', related='level_id.sequence')
    user_ids = fields.Many2many(related='level_id.user_ids', string='Approvers')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('current', 'Current'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', readonly=True)
    
    approved_by_user_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    rejected_by_user_id = fields.Many2one('res.users', string='Rejected By', readonly=True)
    is_current_approver = fields.Boolean(
        string='Is Current Approver', compute='_compute_is_current_approver',
    )

    @api.depends_context('uid')
    @api.depends('user_ids', 'status')
    def _compute_is_current_approver(self):
        for line in self:
            line.is_current_approver = (
                line.status == 'current'
                and self.env.user in line.user_ids
            )

    def action_approve(self):
        self.ensure_one()
        
        if self.status != 'current':
            raise exceptions.UserError("You can only approve the current approval level.")
            
        if self.env.user not in self.user_ids:
            raise exceptions.UserError(f"You are not in the list of authorized approvers for the level '{self.level_id.name}'.")

        self.write({
            'status': 'approved',
            'approved_by_user_id': self.env.user.id,
        })
        self.order_id.message_post(body=f"Approval Level '{self.level_id.name}' has been approved by {self.env.user.name}.")

        todo_type = self.env.ref('mail.mail_activity_data_todo')
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', self.order_id.id),
            ('activity_type_id', '=', todo_type.id),
            ('user_id', 'in', self.user_ids.ids)
        ])
        if activities:
            activities.action_feedback(feedback=f"Approved by {self.env.user.name}")
            
        self.order_id._check_approval_status()
        return self.order_id._get_refresh_action()


    # def action_reject(self):
    #     self.ensure_one()
    #
    #     if self.status != 'current':
    #         raise exceptions.UserError("You can only reject the current approval level.")
    #
    #     if self.env.user not in self.user_ids:
    #         raise exceptions.UserError(f"You are not in the list of authorized approvers for the level '{self.level_id.name}'.")
    #
    #     self.write({
    #         'status': 'rejected',
    #         'rejected_by_user_id': self.env.user.id,
    #     })
    #     self.order_id.write({
    #         'state': 'cancel',
    #     })
    #     self.order_id.message_post(body=f"Approval Level '{self.level_id.name}' has been rejected by {self.env.user.name}.")
    #
    #     todo_type = self.env.ref('mail.mail_activity_data_todo')
    #     activities = self.env['mail.activity'].search([
    #         ('res_model', '=', 'purchase.order'),
    #         ('res_id', '=', self.order_id.id),
    #         ('activity_type_id', '=', todo_type.id),
    #         ('user_id', 'in', self.user_ids.ids)
    #     ])
    #     if activities:
    #         activities.action_feedback(feedback=f"Rejected by {self.env.user.name}")
    #
    #     return self.order_id._get_refresh_action()

    def action_reject(self):
        self.ensure_one()

        if self.status != 'current':
            raise exceptions.UserError("You can only reject the current approval level.")

        if self.env.user not in self.user_ids:
            raise exceptions.UserError(
                f"You are not in the list of authorized approvers for level '{self.level_id.name}'."
            )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Rejection Remarks',
            'res_model': 'margin.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_id': self.order_id.id,
                'default_approval_line_id': self.id,
            },
        }
