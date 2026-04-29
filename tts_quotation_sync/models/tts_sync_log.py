# -*- coding: utf-8 -*-
from odoo import fields, models


class TtsSyncLog(models.Model):
    _name = 'tts.sync.log'
    _description = 'TTS Quotation Sync Log'
    _order = 'sync_date desc'

    sync_date = fields.Datetime(
        string='Sync Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    quotations_fetched = fields.Integer(string='Fetched', readonly=True)
    quotations_success = fields.Integer(string='Success', readonly=True)
    quotations_failed = fields.Integer(string='Failed', readonly=True)
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('partial', 'Partial'),
            ('error',   'Error'),
        ],
        string='Status',
        readonly=True,
    )
    error_message = fields.Text(string='Error Detail', readonly=True)
    log_line_ids = fields.One2many(
        'tts.sync.log.line', 'log_id', string='Per-Quotation Details'
    )


class TtsSyncLogLine(models.Model):
    _name = 'tts.sync.log.line'
    _description = 'TTS Sync Log — Per-Quotation Detail'
    _order = 'id'

    log_id = fields.Many2one(
        'tts.sync.log',
        string='Sync Log',
        ondelete='cascade',
        required=True,
        index=True,
    )
    quotation_ext_id = fields.Integer(string='Quotation ID (ext)')
    tts_quotation_id = fields.Many2one(
        'tts.quotation', string='Quotation Record', ondelete='set null'
    )
    state = fields.Selection(
        selection=[('success', 'Success'), ('failure', 'Failure')],
        string='Result',
    )
    error_message = fields.Text(string='Error Detail')
