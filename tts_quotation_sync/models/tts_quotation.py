# -*- coding: utf-8 -*-
import json
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_RETRIES = 3


_TTS_TO_BOQ_CATEGORY = {
    'wood':    'finishing',
    'civil':   'civil',
    'handles': 'finishing',
}


class TtsQuotation(models.Model):
    _name = 'tts.quotation'
    _description = 'TTS Quotation (from Quotation Builder)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'approved_at desc, id desc'
    _rec_name = 'name'

   
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    external_id = fields.Integer(
        string='Quotation ID',
        readonly=True,
        index=True,
        help='quotation_id returned by the API',
    )

    # ── API fields ─────────────────────────────────────────────────────────
    status = fields.Char(string='API Status', readonly=True, tracking=True)
    total_amount = fields.Float(
        string='Total Amount', readonly=True, digits=(16, 2)
    )
    client_notes = fields.Text(string='Client Notes', readonly=True)
    approved_at = fields.Datetime(string='Approved At', readonly=True)

    # ── Review state (mirrored from API) ──────────────────────────────────
    is_reviewed = fields.Boolean(string='Reviewed', readonly=True)
    is_review_status = fields.Char(
        string='Review Status', readonly=True, tracking=True
    )
    is_review_message = fields.Text(string='Review Message', readonly=True)

    # ── Odoo processing state ─────────────────────────────────────────────
    sync_state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('failure', 'Failure'),
        ],
        string='Sync State',
        default='pending',
        readonly=True,
        tracking=True,
    )
    sync_message = fields.Text(string='Sync Message', readonly=True)

    api_response_body = fields.Text(
        string='API Response Body',
        readonly=True,
        help='Full JSON payload received from the GET /quotations/approved API for this record',
    )
    mark_reviewed_response = fields.Text(
        string='Mark-Reviewed Response',
        readonly=True,
        help='Full JSON response from the PUT /mark-reviewed API call',
    )

    error_reason = fields.Text(
        string='Error Reason',
        readonly=True,
        tracking=True,
        help='Exact error captured when the last processing attempt failed',
    )

    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        readonly=True,
        help='Number of retry attempts made (0 = succeeded on first try; 3 = all retries exhausted)',
    )

    line_ids = fields.One2many(
        'tts.quotation.line', 'tts_quotation_id', string='Line Items'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        readonly=True,
        tracking=True,
    )
    sale_order_count = fields.Integer(
        string='Sale Orders',
        compute='_compute_sale_order_count',
    )
    boq_id = fields.Many2one(
        'boq.boq',
        string='BOQ',
        readonly=True,
        tracking=True,
        help='Bill of Quantities created from this quotation',
    )
    boq_count = fields.Integer(
        string='BOQs',
        compute='_compute_boq_count',
    )

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends('external_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f'TTS-{rec.external_id}' if rec.external_id else 'TTS-New'

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    def _compute_boq_count(self):
        for rec in self:
            rec.boq_count = 1 if rec.boq_id else 0

    # ── Smart button actions ───────────────────────────────────────────────
    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No Sale Order is linked to this quotation.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'target': 'current',
        }

    def _create_boq_from_api(self, quotation):
        """
        Build a boq.boq record from a tts.quotation.
        Called both during the automatic API sync and from the manual button.
        Returns the created boq.boq record.
        """
        if quotation.boq_id:
            return quotation.boq_id

        # BOQ partner_id requires is_company=True
        partner = False
        if quotation.sale_order_id and quotation.sale_order_id.partner_id.is_company:
            partner = quotation.sale_order_id.partner_id
        if not partner:
            partner = self.env.company.partner_id

        # Collect which BOQ category codes are needed from the TTS line items
        tts_cat_types = {
            line.category_type
            for line in quotation.line_ids
            if line.item_type == 'row' and line.category_type
        }
        boq_codes_needed = {
            _TTS_TO_BOQ_CATEGORY[ct]
            for ct in tts_cat_types
            if ct in _TTS_TO_BOQ_CATEGORY
        }
        boq_categories = self.env['boq.category'].search(
            [('code', 'in', list(boq_codes_needed))]
        )
        cat_by_code = {c.code: c for c in boq_categories}

        boq = self.env['boq.boq'].with_context(tts_create_boq=True).create({
            'partner_id': partner.id,
            'project_name': f'TTS-{quotation.external_id}',
            'notes': quotation.client_notes or '',
            'category_ids': [(6, 0, boq_categories.ids)],
            'tts_quotation_id': quotation.id,
        })

        boq_line_vals = []
        for line in quotation.line_ids.sorted('sequence'):
            if line.item_type != 'row' or not line.category_type:
                continue

            cat_code = _TTS_TO_BOQ_CATEGORY.get(line.category_type, 'finishing')
            boq_cat = cat_by_code.get(cat_code)
            if not boq_cat:
                continue

            product = self._get_or_create_product(line)
            discount_pct = self._compute_discount_pct(line)

            if line.category_type == 'wood':
                qty = (line.sqft or 1.0) * (line.qty or 1)
                product_type = 'material'
            elif line.category_type == 'civil':
                qty = float(line.qty or 1)
                product_type = 'subcontract'
            else:
                qty = float(line.qty or 1)
                product_type = 'material'

            boq_line_vals.append({
                'boq_id': boq.id,
                'category_id': boq_cat.id,
                'product_id': product.id,
                'product_name': line.line_description or product.name,
                'product_type': product_type,
                'qty': qty,
                'unit_price': line.price or 0.0,
                'discount': discount_pct,
                'sequence': line.sequence,
                'notes': line.line_description or '',
            })

        if boq_line_vals:
            self.env['boq.order.line'].create(boq_line_vals)

        quotation.boq_id = boq.id
        return boq

    def action_create_boq(self):
        """Manual button on the quotation form — creates or opens the BOQ."""
        self.ensure_one()
        boq = self._create_boq_from_api(self)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'boq.boq',
            'view_mode': 'form',
            'res_id': boq.id,
            'target': 'current',
        }

    # ── Manual sync button ────────────────────────────────────────────────
    def action_manual_sync(self):
        self._cron_sync_quotations()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _('Quotation sync finished. See Sync Logs for details.'),
                'type': 'success',
                'sticky': False,
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # CRON ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_sync_quotations(self):
        config = self._get_sync_config()
        if not config['api_base_url'] or not config['api_key']:
            _logger.warning('tts_quotation_sync: API not configured — skipping run.')
            return

        log = self.env['tts.sync.log'].create({
            'sync_date': fields.Datetime.now(),
            'quotations_fetched': 0,
            'quotations_success': 0,
            'quotations_failed': 0,
            'state': 'error',
        })

        try:
            quotations_data = self._fetch_approved_quotations(config)
            log.quotations_fetched = len(quotations_data)

            for q_data in quotations_data:
                self._process_single_quotation(config, log, q_data,
                                               q_data.get('quotation_id'))

            # Count results from log lines (each quotation writes its own entry)
            success_count = self.env['tts.sync.log.line'].search_count(
                [('log_id', '=', log.id), ('state', '=', 'success')]
            )
            failure_count = self.env['tts.sync.log.line'].search_count(
                [('log_id', '=', log.id), ('state', '=', 'failure')]
            )
            final_state = (
                'success' if failure_count == 0
                else ('error' if success_count == 0 else 'partial')
            )
            log.write({
                'quotations_success': success_count,
                'quotations_failed': failure_count,
                'state': final_state,
            })

        except Exception as exc:
            _logger.exception('tts_quotation_sync: fatal error during sync run')
            log.write({'state': 'error', 'error_message': str(exc)})

    def _process_single_quotation(self, config, log, q_data, qid):

        last_error = None
        raw_body = json.dumps(q_data, default=str)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with self.env.cr.savepoint():

                    # ── STEP 1 (First API data): upsert + create SO + BOQ ──
                    quotation = self._upsert_quotation(q_data)

                    if config['auto_create_so'] == 'yes' and not quotation.sale_order_id:
                        self._create_sale_order(quotation, config)

                    if config['auto_create_boq'] == 'yes' and not quotation.boq_id:
                        self._create_boq_from_api(quotation)

                    # ── STEP 2 (Second API): mark-reviewed PUT ─────────────
                    # Only reached when Step 1 completes without error.
                    mark_resp = self._mark_reviewed(
                        config, qid,
                        is_reviewed=True,
                        status='Success',
                        message=None,
                    )

                    quotation.write({
                        'is_reviewed': True,
                        'is_review_status': 'Success',
                        'is_review_message': False,
                        'sync_state': 'success',
                        'sync_message': False,
                        'retry_count': attempt - 1,
                        'error_reason': False,
                        'api_response_body': raw_body,
                        'mark_reviewed_response': json.dumps(mark_resp, default=str),
                    })
                    self.env['tts.sync.log.line'].create({
                        'log_id': log.id,
                        'quotation_ext_id': qid,
                        'tts_quotation_id': quotation.id,
                        'state': 'success',
                    })
                # ── savepoint committed ────────────────────────────────────
                return  # done — exit retry loop

            except Exception as exc:
                last_error = str(exc)
                _logger.warning(
                    'tts_quotation_sync: attempt %d/%d failed for quotation %s: %s',
                    attempt, MAX_RETRIES, qid, last_error,
                )
                # Savepoint rolled back — outer transaction still healthy.

                if attempt < MAX_RETRIES:
                    # Store intermediate retry state so it's visible in the UI
                    try:
                        existing = self.search([('external_id', '=', qid)], limit=1)
                        if existing:
                            existing.write({
                                'retry_count': attempt,
                                'error_reason': last_error,
                                'sync_state': 'pending',
                            })
                    except Exception:
                        pass
                    continue 

        _logger.error(
            'tts_quotation_sync: all %d attempts failed for quotation %s: %s',
            MAX_RETRIES, qid, last_error,
        )

        failure_quotation = None
        try:
            existing = self.search([('external_id', '=', qid)], limit=1)
            failure_vals = {
                'external_id': qid,
                'status': q_data.get('status', ''),
                'total_amount': float(q_data.get('total_amount') or 0),
                'client_notes': q_data.get('client_notes') or '',
                'approved_at': q_data.get('approved_at'),
                'is_reviewed': False,
                'is_review_status': 'Failure',
                'is_review_message': last_error,
                'sync_state': 'failure',
                'sync_message': last_error,
                'error_reason': last_error,
                'retry_count': MAX_RETRIES,
                'api_response_body': raw_body,
            }
            if existing:
                existing.write(failure_vals)
                failure_quotation = existing
            else:
                failure_quotation = self.create(failure_vals)
        except Exception:
            _logger.exception(
                'tts_quotation_sync: could not write failure record for quotation %s', qid
            )

        # Second API: mark Failure on external system (no DB interaction here)
        try:
            self._mark_reviewed(
                config, qid,
                is_reviewed=False,
                status='Failure',
                message=(last_error or 'Unknown error')[:500],
            )
        except Exception:
            _logger.exception(
                'tts_quotation_sync: could not call mark-reviewed (Failure) '
                'for quotation %s', qid,
            )

        self.env['tts.sync.log.line'].create({
            'log_id': log.id,
            'quotation_ext_id': qid or 0,
            'tts_quotation_id': failure_quotation.id if failure_quotation else False,
            'state': 'failure',
            'error_message': last_error,
        })

        notif_email = config.get('failure_notification_email')
        if notif_email:
            self._send_failure_notification(notif_email, q_data, last_error)

    # ─────────────────────────────────────────────────────────────────────
    # CONFIG HELPER
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def _get_sync_config(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        raw_customer = get_param('tts_quotation_sync.default_customer_id', '0')
        return {
            'api_base_url': (
                get_param('tts_quotation_sync.api_base_url', '') or ''
            ).rstrip('/'),
            'api_key': get_param('tts_quotation_sync.api_key', '') or '',
            'environment': get_param('tts_quotation_sync.environment', 'development'),
            'auto_create_so': get_param('tts_quotation_sync.auto_create_so', 'yes'),
            'auto_create_boq': get_param('tts_quotation_sync.auto_create_boq', 'yes'),
            'failure_notification_email': get_param(
                'tts_quotation_sync.failure_notification_email', ''
            ),
            'default_customer_id': int(raw_customer) if raw_customer else 0,
        }

    # ─────────────────────────────────────────────────────────────────────
    # API CALLS
    # ─────────────────────────────────────────────────────────────────────

    def _fetch_approved_quotations(self, config):
        url = f"{config['api_base_url']}/public/quotations/approved"
        resp = requests.get(
            url,
            headers={'x-api-key': config['api_key']},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get('quotations', [])

    def _mark_reviewed(self, config, quotation_id, is_reviewed, status, message):
        url = (
            f"{config['api_base_url']}/public/quotations"
            f"/{quotation_id}/mark-reviewed"
        )
        body = {
            'is_reviewed': is_reviewed,
            'is_review_status': status,
            'is_review_message': message,
        }
        resp = requests.put(
            url,
            json=body,
            headers={
                'x-api-key': config['api_key'],
                'Content-Type': 'application/json',
            },
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise Exception(
                f'mark-reviewed returned HTTP {resp.status_code}: {resp.text[:300]}'
            )
        return resp.json()

    # ─────────────────────────────────────────────────────────────────────
    # QUOTATION UPSERT
    # ─────────────────────────────────────────────────────────────────────

    def _upsert_quotation(self, q_data):
        existing = self.search(
            [('external_id', '=', q_data['quotation_id'])], limit=1
        )
        vals = {
            'external_id': q_data['quotation_id'],
            'status': q_data.get('status', ''),
            'total_amount': float(q_data.get('total_amount') or 0),
            'client_notes': q_data.get('client_notes') or '',
            'approved_at': q_data.get('approved_at'),
            'is_reviewed': q_data.get('is_reviewed', False),
            'is_review_status': q_data.get('is_review_status'),
            'is_review_message': q_data.get('is_review_message'),
            'sync_state': 'pending',
        }

        if existing:
            existing.write(vals)
            existing.line_ids.unlink()
            quotation = existing
        else:
            quotation = self.create(vals)

        line_vals_list = [
            self._parse_grid_row(row, quotation.id, (idx + 1) * 10)
            for idx, row in enumerate(q_data.get('grid_rows', []))
        ]
        if line_vals_list:
            self.env['tts.quotation.line'].create(line_vals_list)

        return quotation

    def _parse_grid_row(self, row, quotation_id, sequence=10):
        item_type = row.get('item_type', 'row')
        category_type = row.get('categoryType', '')

        vals = {
            'tts_quotation_id': quotation_id,
            # Store as Char — API ids are 13-digit longs, beyond PostgreSQL integer range
            'external_line_id': str(row.get('id', '')),
            'sequence': sequence,  # safe incrementing counter (10, 20, 30 …)
            'item_type': item_type,
            'category_type': category_type if item_type == 'row' else False,
        }

        if item_type == 'header':
            vals.update({
                'title': row.get('title', ''),
                'category_id_ext': str(row.get('categoryId', '')),
            })
            return vals

        # All row types — pricing
        vals.update({
            'price': float(row.get('price') or 0),
            'qty': int(row.get('qty') or 0),
            'amount': float(row.get('amount') or 0),
            'discount': float(row.get('discount') or 0),
            'discount_type': row.get('discountType', ''),
            'final_amount': float(row.get('finalAmount') or 0),
        })

        if category_type == 'wood':
            vals.update({
                'product_name': row.get('productName', ''),
                'category': row.get('category', ''),
                'subcategory': row.get('subcategory', ''),
                'product_code': row.get('productCode', ''),
                'height': float(row.get('height') or 0),
                'width': float(row.get('width') or 0),
                'sqft': float(row.get('sqft') or 0),
            })
        elif category_type == 'civil':
            vals.update({
                'category': row.get('category', ''),
                'subcategory': row.get('subcategory', ''),
                'service_item': row.get('serviceItem', ''),
                'unit': row.get('unit', ''),
            })
        elif category_type == 'handles':
            vals.update({
                'brand': row.get('brand', ''),
                'article_category': row.get('articleCategory', ''),
                'article_description': row.get('articleDescription', ''),
                'dimension': row.get('dimension', ''),
            })

        return vals

    # ─────────────────────────────────────────────────────────────────────
    # SALE ORDER CREATION
    # ─────────────────────────────────────────────────────────────────────

    def _create_sale_order(self, quotation, config):
        partner_id = config.get('default_customer_id') or self.env.company.partner_id.id

        so = self.env['sale.order'].create({
            'partner_id': partner_id,
            'client_order_ref': f'TTS-{quotation.external_id}',
            'origin': f'TTS Quotation Builder #{quotation.external_id}',
            'note': quotation.client_notes or '',
        })

        so_line_vals = []
        for line in quotation.line_ids.sorted('sequence'):
            if line.item_type == 'header':
                so_line_vals.append({
                    'order_id': so.id,
                    'display_type': 'line_section',
                    'name': line.title or 'Section',
                    'sequence': line.sequence,
                })
            elif line.item_type == 'row':
                product = self._get_or_create_product(line)
                discount_pct = self._compute_discount_pct(line)

                if line.category_type == 'wood':
                    effective_qty = (line.sqft or 1) * (line.qty or 1)
                    price_unit = line.price
                else:
                    effective_qty = line.qty or 1
                    price_unit = line.price

                so_line_vals.append({
                    'order_id': so.id,
                    'product_id': product.id,
                    'name': line.line_description or product.name,
                    'product_uom_qty': effective_qty,
                    'price_unit': price_unit,
                    'discount': discount_pct,
                    'sequence': line.sequence,
                })

        if so_line_vals:
            self.env['sale.order.line'].create(so_line_vals)

        quotation.sale_order_id = so.id
        return so

    @staticmethod
    def _compute_discount_pct(line):
        """Return a discount percentage for sale.order.line / BOQ line (0–100)."""
        if line.discount_type == 'percentage':
            return min(max(line.discount, 0), 100)
        if line.discount_type == 'fixed' and line.price and line.amount:
            base = (
                line.price * (line.sqft or 1) * (line.qty or 1)
                if line.category_type == 'wood'
                else line.price * (line.qty or 1)
            )
            if base > 0:
                return min((line.discount / base) * 100, 100)
        return 0.0

    def _get_or_create_product(self, line):
        Product = self.env['product.product']

        if line.category_type == 'wood':
            if line.product_code:
                product = Product.search(
                    [('default_code', '=', line.product_code)], limit=1
                )
            else:
                product = Product.search(
                    [('name', '=', line.product_name)], limit=1
                ) if line.product_name else Product.browse()

            if not product:
                product = Product.create({
                    'name': line.product_name or 'Furniture Item',
                    'default_code': line.product_code or '',
                    'type': 'consu',
                    'sale_ok': True,
                    'purchase_ok': True,
                })
            return product

        if line.category_type == 'civil':
            name = line.service_item or line.subcategory or line.category or 'Civil Service'
            product = Product.search(
                [('name', '=', name), ('detailed_type', '=', 'service')], limit=1
            )
            if not product:
                product = Product.create({
                    'name': name,
                    'detailed_type': 'service',
                    'sale_ok': True,
                })
            return product

        if line.category_type == 'handles':
            name = (
                line.article_description
                or line.article_category
                or 'Hardware Item'
            )
            product = Product.search([('name', '=', name)], limit=1)
            if not product:
                product = Product.create({
                    'name': name,
                    'type': 'consu',
                    'sale_ok': True,
                    'purchase_ok': True,
                })
            return product

        product = Product.search([], limit=1)
        if not product:
            product = Product.create({'name': 'General Item', 'type': 'consu'})
        return product

    # ─────────────────────────────────────────────────────────────────────
    # NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────────────

    def _send_failure_notification(self, email, q_data, error_msg):
        try:
            self.env['mail.mail'].sudo().create({
                'subject': (
                    f"TTS Quotation Sync Failure — "
                    f"QTN-{q_data.get('quotation_id', '?')}"
                ),
                'email_to': email,
                'body_html': (
                    f"<p>Quotation <b>TTS-{q_data.get('quotation_id')}</b> "
                    f"failed to sync into Odoo after {MAX_RETRIES} attempts.</p>"
                    f"<p><b>Error:</b> {error_msg}</p>"
                    f"<p>Please review the Sync Logs in Odoo for details.</p>"
                ),
                'auto_delete': True,
            }).send()
        except Exception:
            _logger.warning(
                'tts_quotation_sync: could not send failure notification email'
            )
