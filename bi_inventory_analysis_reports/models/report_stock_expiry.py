# -*- coding: utf-8 -*-
from odoo import fields, models


class BiStockExpiryReport(models.Model):
    """Stock Expiry Report — lot-tracked products near or past expiration.
    Requires the product_expiry module (expiration_date on stock.lot).
    """

    _name = 'bi.stock.expiry.report'
    _description = 'Stock Expiry Report'
    _auto = False
    _rec_name = 'product_id'
    _order = 'expiration_date asc, product_id'
    _log_access = False

    # ── Product ──────────────────────────────────────────────────────────────
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)

    # ── Location ─────────────────────────────────────────────────────────────
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)

    # ── Lot ──────────────────────────────────────────────────────────────────
    lot_id = fields.Many2one('stock.lot', string='Lot / Serial No.', readonly=True)

    # ── Company / Currency ───────────────────────────────────────────────────
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # ── Quantities ───────────────────────────────────────────────────────────
    qty_on_hand = fields.Float(
        string='On Hand Qty', readonly=True, digits='Product Unit of Measure')

    # ── Expiry data ──────────────────────────────────────────────────────────
    expiration_date = fields.Datetime(string='Expiration Date', readonly=True)
    best_before_date = fields.Datetime(string='Best Before Date', readonly=True)
    removal_date = fields.Datetime(string='Removal Date', readonly=True)
    days_to_expiry = fields.Integer(string='Days to Expiry', readonly=True)
    expiry_status = fields.Selection([
        ('expired', 'Expired'),
        ('near_expiry', 'Near Expiry (≤ 30 days)'),
        ('expiring_soon', 'Expiring Soon (≤ 90 days)'),
        ('ok', 'OK'),
        ('no_expiry', 'No Expiry Date'),
    ], string='Expiry Status', readonly=True)

    # ── Valuation ────────────────────────────────────────────────────────────
    cost_price = fields.Float(string='Cost Price', readonly=True, digits='Product Price')
    total_value = fields.Monetary(
        string='Stock Value', readonly=True, currency_field='currency_id')

    # ─────────────────────────────────────────────────────────────────────────

    def _auto_init(self):
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)" % (self._table, self._table_query)
        )
        return super()._auto_init()

    @property
    def _table_query(self):
        self.env.cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'stock_valuation_layer')"
        )
        svl_exists = self.env.cr.fetchone()[0]

        if svl_exists:
            cost_join = """
                LEFT JOIN LATERAL (
                    SELECT svl.unit_cost
                    FROM stock_valuation_layer svl
                    WHERE svl.product_id = sq.product_id
                      AND svl.company_id = sq.company_id
                    ORDER BY svl.id DESC
                    LIMIT 1
                ) last_cost ON TRUE"""
            cost_expr = "COALESCE(last_cost.unit_cost, 0.0)"
        else:
            cost_join = ""
            cost_expr = "0.0"

        return f"""
            SELECT
                sq.id,
                sq.product_id,
                pp.product_tmpl_id,
                pt.categ_id,
                pt.uom_id,
                sq.location_id,
                wh_lkp.warehouse_id,
                sq.lot_id,
                sq.company_id,
                rc.currency_id,
                sq.quantity                                           AS qty_on_hand,
                sl2.expiration_date,
                sl2.use_date                                          AS best_before_date,
                sl2.removal_date,
                CASE
                    WHEN sl2.expiration_date IS NULL THEN NULL
                    ELSE EXTRACT(
                        DAY FROM (sl2.expiration_date - NOW() AT TIME ZONE 'UTC')
                    )::integer
                END                                                   AS days_to_expiry,
                CASE
                    WHEN sl2.expiration_date IS NULL
                        THEN 'no_expiry'
                    WHEN sl2.expiration_date < NOW() AT TIME ZONE 'UTC'
                        THEN 'expired'
                    WHEN sl2.expiration_date < NOW() AT TIME ZONE 'UTC'
                         + INTERVAL '30 days'
                        THEN 'near_expiry'
                    WHEN sl2.expiration_date < NOW() AT TIME ZONE 'UTC'
                         + INTERVAL '90 days'
                        THEN 'expiring_soon'
                    ELSE 'ok'
                END                                                   AS expiry_status,
                {cost_expr}                                           AS cost_price,
                sq.quantity * {cost_expr}                             AS total_value
            FROM stock_quant sq
            JOIN product_product  pp   ON pp.id = sq.product_id
            JOIN product_template pt   ON pt.id = pp.product_tmpl_id
            JOIN stock_location   sl   ON sl.id = sq.location_id
            JOIN res_company      rc   ON rc.id = sq.company_id
            LEFT JOIN stock_lot   sl2  ON sl2.id = sq.lot_id
            LEFT JOIN LATERAL (
                SELECT sw.id AS warehouse_id
                FROM stock_warehouse  sw
                JOIN stock_location   wv ON wv.id = sw.view_location_id
                WHERE sl.complete_name LIKE wv.complete_name || '/%'
                   OR sl.id = wv.id
                ORDER BY LENGTH(wv.complete_name) DESC
                LIMIT 1
            ) wh_lkp ON TRUE
            {cost_join}
            WHERE sl.usage = 'internal'
              AND sq.quantity > 0
              AND sq.lot_id IS NOT NULL
        """
