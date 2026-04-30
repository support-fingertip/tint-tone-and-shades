# -*- coding: utf-8 -*-
import logging

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_INTERVAL_MAP = {
    '5':    (5,  'minutes'),
    '15':   (15, 'minutes'),
    '30':   (30, 'minutes'),
    '60':   (1,  'hours'),
    '360':  (6,  'hours'),
    '1440': (1,  'days'),
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Connection settings ────────────────────────────────────────────────
    tts_api_base_url = fields.Char(
        string='API Base URL',
        config_parameter='tts_quotation_sync.api_base_url',
        help='Quotation Builder backend endpoint',
    )
    tts_api_key = fields.Char(
        string='API Key (x-api-key)',
        config_parameter='tts_quotation_sync.api_key',
        help='DEV environment key',
    )
    tts_environment = fields.Selection(
        selection=[
            ('development', 'Development'),
            ('production', 'Production'),
        ],
        string='Environment',
        config_parameter='tts_quotation_sync.environment',
        default='development',
        help='Switch before going live',
    )

    # ── Cron / auto-sync settings ──────────────────────────────────────────
    tts_sync_interval = fields.Selection(
        selection=[
            ('5',    'Every 5 minutes'),
            ('15',   'Every 15 minutes'),
            ('30',   'Every 30 minutes'),
            ('60',   'Every hour'),
            ('360',  'Every 6 hours'),
            ('1440', 'Every day'),
        ],
        string='Sync Interval',
        config_parameter='tts_quotation_sync.sync_interval',
        default='15',
        help='How often Odoo polls the API',
    )
    tts_auto_create_so = fields.Selection(
        selection=[
            ('yes', 'Yes — auto create'),
            ('no',  'No — manual review'),
        ],
        string='Auto-create Sale Order',
        config_parameter='tts_quotation_sync.auto_create_so',
        default='yes',
        help='Automatically create SO on success',
    )
    tts_failure_notification_email = fields.Char(
        string='Failure notification email',
        config_parameter='tts_quotation_sync.failure_notification_email',
        help='Notify when PUT returns Failure',
    )

    # Many2one for Default Customer — must use get_values/set_values in Odoo 19
    # (compute/inverse on TransientModel causes InFailedSqlTransaction on flush)
    tts_default_customer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Default Customer',
        help='Customer placed on auto-created Sale Orders',
    )

    # ── get_values: load Many2one from ir.config_parameter ────────────────
    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo().get_param(
            'tts_quotation_sync.default_customer_id'
        )
        try:
            res['tts_default_customer_id'] = int(param) if param else False
        except (ValueError, TypeError):
            res['tts_default_customer_id'] = False
        return res

    # ── set_values: persist Many2one + update cron interval ───────────────
    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'tts_quotation_sync.default_customer_id',
            self.tts_default_customer_id.id if self.tts_default_customer_id else False,
        )
        self._update_cron_interval()

    def _update_cron_interval(self):
        cron = self.env.ref(
            'tts_quotation_sync.cron_sync_quotations', raise_if_not_found=False
        )
        if not cron:
            return
        interval_key = self.tts_sync_interval or '15'
        number, unit = _INTERVAL_MAP.get(interval_key, (15, 'minutes'))
        cron.write({'interval_number': number, 'interval_type': unit})

    # ── Test Connection button ─────────────────────────────────────────────
    def action_test_connection(self):
        base_url = (self.tts_api_base_url or '').rstrip('/')
        api_key = self.tts_api_key or ''

        if not base_url or not api_key:
            return self._notif('warning', 'Missing Config',
                               'Please fill in API Base URL and API Key first.')

        url = f'{base_url}/public/quotations/approved'
        try:
            resp = requests.get(
                url,
                headers={'x-api-key': api_key},
                timeout=15,
            )
        except requests.exceptions.ConnectionError:
            return self._notif('danger', 'Connection Failed',
                               'Cannot reach the API. Check the Base URL.')
        except requests.exceptions.Timeout:
            return self._notif('danger', 'Timeout',
                               'The API did not respond within 15 seconds.')
        except Exception as exc:
            return self._notif('danger', 'Error', str(exc))

        if resp.status_code == 200:
            count = len(resp.json().get('quotations', []))
            return self._notif('success', 'Connection Successful',
                               f'Connected! {count} pending quotation(s) available.')
        if resp.status_code == 401:
            return self._notif('danger', 'Authentication Failed',
                               'Invalid or missing API key (HTTP 401).')
        return self._notif('warning', 'Unexpected Response',
                           f'HTTP {resp.status_code}: {resp.text[:200]}')

    # ── Trigger a manual sync from settings ───────────────────────────────
    def action_sync_now(self):
        self.env['tts.quotation']._cron_sync_quotations()
        return self._notif('success', 'Sync Triggered',
                           'Sync completed. Check Sync Logs for details.')

    @staticmethod
    def _notif(kind, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': kind,
                'sticky': False,
            },
        }
