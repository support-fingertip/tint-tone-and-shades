# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TtsQuotationLine(models.Model):
    _name = 'tts.quotation.line'
    _description = 'TTS Quotation Line'
    _order = 'tts_quotation_id, sequence, id'

    tts_quotation_id = fields.Many2one(
        'tts.quotation',
        string='Quotation',
        ondelete='cascade',
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    # Char: API ids are 13-digit longs that overflow PostgreSQL integer (max ~2.1B)
    external_line_id = fields.Char(string='External Line ID')

    item_type = fields.Selection(
        selection=[('header', 'Header'), ('row', 'Row')],
        string='Item Type',
        default='row',
        required=True,
    )
    category_type = fields.Selection(
        selection=[
            ('wood',    'Wood / Furniture'),
            ('civil',   'Civil / Services'),
            ('handles', 'Handles / Hardware'),
        ],
        string='Category Type',
    )

    # ── Header-only ────────────────────────────────────────────────────────
    title = fields.Char(string='Section Title')
    category_id_ext = fields.Char(string='Category ID (ext)')

    # ── Wood fields ────────────────────────────────────────────────────────
    product_name = fields.Char(string='Product Name')
    product_code = fields.Char(string='Product Code')
    subcategory = fields.Char(string='Subcategory / Finish')

    height = fields.Float(string='Height (ft)', digits=(16, 3))
    width = fields.Float(string='Width (ft)', digits=(16, 3))
    sqft = fields.Float(string='Area (sqft)', digits=(16, 3))

    # ── Civil fields ───────────────────────────────────────────────────────
    service_item = fields.Char(string='Service Description')
    unit = fields.Char(string='Unit of Measure')

    # ── Handles fields ─────────────────────────────────────────────────────
    brand = fields.Char(string='Brand')
    article_category = fields.Char(string='Article Category')
    article_description = fields.Char(string='Article Description')
    dimension = fields.Char(string='Dimension')

    # ── Shared category field (wood + civil) ───────────────────────────────
    category = fields.Char(string='Category / Grade')

    # ── Pricing (all row types) ────────────────────────────────────────────
    price = fields.Float(string='Unit Price', digits=(16, 4))
    qty = fields.Integer(string='Qty')
    amount = fields.Float(string='Amount', digits=(16, 2))
    discount = fields.Float(string='Discount Value', digits=(16, 4))
    discount_type = fields.Char(string='Discount Type')   # "percentage" | "fixed"
    final_amount = fields.Float(string='Final Amount', digits=(16, 2))

    # ── Computed label used in SO line description ─────────────────────────
    line_description = fields.Char(
        string='Description',
        compute='_compute_line_description',
        store=True,
    )

    @api.depends(
        'item_type', 'category_type', 'title',
        'product_name', 'product_code', 'category', 'subcategory',
        'height', 'width', 'sqft',
        'service_item', 'unit',
        'article_description', 'brand', 'dimension',
    )
    def _compute_line_description(self):
        for line in self:
            if line.item_type == 'header':
                line.line_description = line.title or ''
                continue

            if line.category_type == 'wood':
                parts = [line.product_name]
                if line.category:
                    parts.append(line.category)
                if line.subcategory:
                    parts.append(line.subcategory)
                if line.product_code:
                    parts.append(f'[{line.product_code}]')
                if line.sqft:
                    h = f'{line.height:.2f}' if line.height else '?'
                    w = f'{line.width:.2f}' if line.width else '?'
                    parts.append(f'H:{h}ft × W:{w}ft ({line.sqft:.2f} sqft)')
                line.line_description = ' | '.join(p for p in parts if p)

            elif line.category_type == 'civil':
                parts = [line.service_item or line.subcategory or line.category]
                if line.unit:
                    parts.append(f'Unit: {line.unit}')
                line.line_description = ' | '.join(p for p in parts if p)

            elif line.category_type == 'handles':
                parts = [line.article_description or line.article_category]
                if line.brand:
                    parts.append(f'Brand: {line.brand}')
                if line.dimension:
                    parts.append(f'Dim: {line.dimension}')
                line.line_description = ' | '.join(p for p in parts if p)

            else:
                line.line_description = ''
