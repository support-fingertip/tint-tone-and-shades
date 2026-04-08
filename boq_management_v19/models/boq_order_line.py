# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqOrderLine(models.Model):
    """
    Individual BOQ line item within a work category.
    Captures product, quantity, type and pricing.
    """
    _name = 'boq.order.line'
    _description = 'BOQ Order Line'
    _order = 'sequence asc, id asc'

    # ── Relationships ────────────────────────────────────────────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ',
        required=True,
        ondelete='cascade',
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name='boq.category',
        string='Work Category',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        related='boq_id.company_id',
        store=True,
        index=True,
    )

    # ── Sequence / ordering ───────────────────────────────────────────────
    sequence = fields.Integer(string='#', default=10)

    # ── Product ───────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product / Material',
        required=True,
        change_default=True,
        index=True,
    )
    product_name = fields.Char(
        string='Description',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        precompute=True,
    )
    product_type = fields.Selection(
        selection=[
            ('material',    'Material'),
            ('labour',      'Labour'),
            ('equipment',   'Equipment'),
            ('subcontract', 'Subcontract'),
            ('other',       'Other'),
        ],
        string='Type',
        required=True,
        default='material',
    )

    # ── UoM ───────────────────────────────────────────────────────────────
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        precompute=True,
    )
    # ── Quantity & Price ──────────────────────────────────────────────────
    qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    unit_price = fields.Float(
        string='Unit Price',
        digits='Product Price',
        default=0.0,
    )
    discount = fields.Float(
        string='Disc. %',
        digits='Discount',
        default=0.0,
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        digits='Product Price',
        precompute=True,
    )
    currency_id = fields.Many2one(
        related='boq_id.currency_id',
        store=True,
    )

    # ── Preferred Vendors (Many2many → res.partner, filtered to vendors) ──
    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_order_line_vendor_rel',
        column1='line_id',
        column2='partner_id',
        string='Preferred Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Select one or more vendors for this line. '
             '"Create RFQ" will generate a purchase RFQ per vendor.',
    )

    # ── Taxes ─────────────────────────────────────────────────────────────
    # Relation table boq_order_line_tax_rel is pre-created by migration
    # 19.0.1.0.2 (CREATE TABLE IF NOT EXISTS), so fresh installs and
    # upgrades both work without UndefinedTable errors.
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        relation='boq_order_line_tax_rel',
        column1='line_id',
        column2='tax_id',
        string='Taxes',
        domain=[('type_tax_use', 'in', ('purchase', 'all'))],
        help='Taxes applied to this line. Affects Tax Amount and Total (incl. Tax).',
    )

    # ── Tax / Total / Margin ──────────────────────────────────────────────
    tax_amount = fields.Float(
        string='Tax Amount',
        compute='_compute_total_value',
        store=False,
        digits='Product Price',
    )
    total_value = fields.Float(
        string='Total (incl. Tax)',
        compute='_compute_total_value',
        store=False,
        digits='Product Price',
        help='Subtotal + computed taxes from tax_ids.',
    )

    # ── Cost & Margin ──────────────────────────────────────────────────────
    cost_price = fields.Float(
        string='Cost Price',
        compute='_compute_from_product',
        store=False,
        readonly=False,
        digits='Product Price',
        help='Unit cost from product standard price.',
    )
    margin_percent = fields.Float(
        string='Margin %',
        compute='_compute_margin',
        store=False,
        digits='Discount',
        help='Gross margin percentage: ((Unit Price - Cost) / Unit Price) × 100.',
    )

    # ── Notes ─────────────────────────────────────────────────────────────
    notes = fields.Char(string='Remarks')

    # ── _auto_init: idempotent schema bootstrap on every startup ──────────
    def _auto_init(self):
        """
        boq.order.line is owned by boq_management_v19, so this _auto_init()
        is guaranteed to run on EVERY server startup (not just -u upgrades).

        We use it to ensure all boq_management_v19 schema changes exist,
        including columns on tables owned by other modules (res_partner, etc.)
        that cannot be bootstrapped from those models' own _auto_init().

        All statements use IF NOT EXISTS / DO NOTHING so repeated calls are safe.
        """
        res = super()._auto_init()

        # ── 1. M2M relation table for BOQ line taxes ──────────────────────
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS boq_order_line_tax_rel (
                line_id INTEGER NOT NULL
                    REFERENCES boq_order_line(id) ON DELETE CASCADE,
                tax_id  INTEGER NOT NULL
                    REFERENCES account_tax(id)    ON DELETE CASCADE,
                PRIMARY KEY (line_id, tax_id)
            );
        """)

        # ── 2. res_partner columns for BOQ v2.0 (NEW TASK 1 + NEW TASK 4) ─
        # _auto_init() on _inherit='res.partner' is NOT called by Odoo because
        # res.partner is owned by 'base'. We add them here instead.
        self.env.cr.execute("""
            ALTER TABLE res_partner
                ADD COLUMN IF NOT EXISTS partner_type VARCHAR,
                ADD COLUMN IF NOT EXISTS avg_rating   NUMERIC(6, 2) DEFAULT 0.0,
                ADD COLUMN IF NOT EXISTS rating_count INTEGER       DEFAULT 0;
        """)

        # ── 3. boq_category.is_down_payment column (BUG 1) ───────────────
        self.env.cr.execute("""
            ALTER TABLE boq_category
                ADD COLUMN IF NOT EXISTS is_down_payment BOOLEAN DEFAULT FALSE;
        """)

        return res

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('product_id')
    def _compute_from_product(self):
        for line in self:
            if line.product_id:
                line.product_name = line.product_id.display_name
                line.uom_id = line.product_id.uom_id
                line.cost_price = line.product_id.standard_price or 0.0
            else:
                line.product_name = False
                line.uom_id = False
                line.cost_price = 0.0

    @api.depends('qty', 'unit_price', 'discount')
    def _compute_subtotal(self):
        for line in self:
            base = line.qty * line.unit_price
            line.subtotal = base * (1.0 - line.discount / 100.0)

    @api.depends('subtotal', 'tax_ids', 'qty', 'unit_price', 'discount')
    def _compute_total_value(self):
        for line in self:
            if line.tax_ids:
                # price_unit after discount — taxes compute per unit × qty
                price_after_disc = line.unit_price * (1.0 - line.discount / 100.0)
                taxes = line.tax_ids.compute_all(
                    price_after_disc,
                    currency=line.currency_id or None,
                    quantity=line.qty,
                    product=line.product_id or None,
                    partner=line.boq_id.partner_id or None,
                )
                line.tax_amount = taxes['total_included'] - taxes['total_excluded']
                line.total_value = taxes['total_included']
            else:
                line.tax_amount = 0.0
                line.total_value = line.subtotal

    @api.depends('unit_price', 'discount', 'cost_price', 'category_id', 'category_id.is_down_payment')
    def _compute_margin(self):
        """
        BUG 1 fix — Margin formula: ((sale_price - purchase_price) / sale_price) × 100
        • sale_price  = unit_price after discount
        • purchase_price = cost_price (product standard_price)
        • If sale_price == 0  → margin = 0  (avoid divide-by-zero)
        • If category is_down_payment → margin forced to 0 (down-payment convention)
        """
        for line in self:
            # Down-payment lines always carry 0% margin
            if line.category_id and line.category_id.is_down_payment:
                line.margin_percent = 0.0
                continue
            sale_price = line.unit_price * (1.0 - (line.discount or 0.0) / 100.0)
            if sale_price > 0:
                purchase_price = line.cost_price or 0.0
                line.margin_percent = ((sale_price - purchase_price) / sale_price) * 100.0
            else:
                line.margin_percent = 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.lst_price or self.product_id.standard_price
