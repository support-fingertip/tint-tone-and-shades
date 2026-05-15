# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True,
    )

    invoice_approval_active = fields.Boolean(
        related='company_id.invoice_approval_active',
        string='Invoice Approval',
        readonly=False,
    )
    invoice_approval_amount = fields.Monetary(
        related='company_id.invoice_approval_amount',
        string='Minimum Invoice Amount',
        readonly=False,
        currency_field='company_currency_id',
    )
    receipt_approval_active = fields.Boolean(
        related='company_id.receipt_approval_active',
        string='Receipt Approval',
        readonly=False,
    )
    receipt_approval_amount = fields.Monetary(
        related='company_id.receipt_approval_amount',
        string='Minimum Receipt Amount',
        readonly=False,
        currency_field='company_currency_id',
    )
