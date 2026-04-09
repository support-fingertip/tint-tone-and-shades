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
        compute='_compute_product_info',
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
        compute='_compute_product_info',
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
        compute='_compute_cost_price',
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

    # ── _auto_init: M2M table only (runs on install/upgrade) ─────────────
    def _auto_init(self):
        """
        Create boq_order_line_tax_rel if it does not exist.
        _auto_init() runs during 'odoo -i' or 'odoo -u', NOT on plain restart.
        Column additions for other tables are handled in _register_hook() below.
        """
        res = super()._auto_init()
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS boq_order_line_tax_rel (
                line_id INTEGER NOT NULL
                    REFERENCES boq_order_line(id) ON DELETE CASCADE,
                tax_id  INTEGER NOT NULL
                    REFERENCES account_tax(id)    ON DELETE CASCADE,
                PRIMARY KEY (line_id, tax_id)
            );
        """)
        return res

    # ── _register_hook: runs on EVERY server startup ───────────────────────
    def _register_hook(self):
        """
        Odoo calls _register_hook() for every model on every registry build
        (i.e. every server start, with or without -u).  This is the correct
        place to add DB columns that must exist before the first HTTP request
        is served — unlike _auto_init() which only runs during install/upgrade.

        All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS so repeated
        calls on restart are fully idempotent.
        """
        res = super()._register_hook()

        # ── boq_trade_vendor: add partner_type column + fix unique constraint ─
        # partner_type column added in v2.1 — safe to add if already exists.
        # Old unique constraint (boq_id, category_id) renamed to include partner_type.
        self.env.cr.execute("""
            ALTER TABLE boq_trade_vendor
                ADD COLUMN IF NOT EXISTS partner_type VARCHAR DEFAULT 'vendor';
            ALTER TABLE boq_trade_vendor
                DROP CONSTRAINT IF EXISTS boq_trade_vendor_boq_id_category_id_key;
        """)

        # ── res_partner columns (BOQ v2.0 — NEW TASK 1 + NEW TASK 4) ─────
        # Cannot use res.partner._auto_init() because res.partner is owned
        # by 'base' and Odoo won't call _auto_init() on it for our module.
        self.env.cr.execute("""
            ALTER TABLE res_partner
                ADD COLUMN IF NOT EXISTS partner_type VARCHAR,
                ADD COLUMN IF NOT EXISTS avg_rating   NUMERIC(6, 2) DEFAULT 0.0,
                ADD COLUMN IF NOT EXISTS rating_count INTEGER       DEFAULT 0;
        """)

        # ── Clean up stale ir.rule for boq.vendor.rating ──────────────────
        # A legacy ir.rule has domain_force [('res_model','=','res.partner')]
        # which crashes every res.partner read because boq.vendor.rating has
        # no `res_model` field.
        #
        # Raw SQL DELETE is used instead of ORM unlink because _register_hook
        # runs during registry build before the ir.rule ORM cache is populated,
        # making a direct DELETE safe and more reliable than ORM operations.
        # The query is scoped to only the affected models to avoid removing
        # unrelated security rules from other modules.
        try:
            self.env.cr.execute("""
                DELETE FROM ir_rule
                 WHERE domain_force ILIKE '%%res_model%%'
                   AND model_id IN (
                       SELECT id FROM ir_model
                        WHERE model IN ('boq.vendor.rating', 'vendor.po.rating')
                   )
            """)
        except Exception:
            pass  # ir_rule table may not exist yet on very first install

        return res

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('product_id')
    def _compute_product_info(self):
        """Stored fields derived from product_id: product_name and uom_id."""
        for line in self:
            if line.product_id:
                line.product_name = line.product_id.display_name
                line.uom_id = line.product_id.uom_id
            else:
                line.product_name = False
                line.uom_id = False

    @api.depends('product_id')
    def _compute_cost_price(self):
        """Non-stored: unit cost from product standard_price."""
        for line in self:
            line.cost_price = line.product_id.standard_price or 0.0 if line.product_id else 0.0

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

    @api.depends('unit_price', 'discount', 'cost_price')
    def _compute_margin(self):
        """
        Margin formula: ((sale_price - cost_price) / sale_price) × 100
        • sale_price = unit_price after discount
        • If sale_price == 0 → margin = 0 (avoid divide-by-zero)
        """
        for line in self:
            sale_price = line.unit_price * (1.0 - (line.discount or 0.0) / 100.0)
            if sale_price > 0:
                line.margin_percent = ((sale_price - (line.cost_price or 0.0)) / sale_price) * 100.0
            else:
                line.margin_percent = 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.lst_price or self.product_id.standard_price
