# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BiStockAgingReport(models.Model):
    """Inventory Aging Analysis — based on stock.quant.in_date.
    Shows how long each stock unit has been sitting in its current location.
    """

    _name = 'bi.stock.aging.report'
    _description = 'Inventory Aging Analysis'
    _auto = False
    _rec_name = 'product_id'
    _order = 'days_in_stock desc, product_id'
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

    # ── Aging ────────────────────────────────────────────────────────────────
    in_date = fields.Datetime(string='Date Received', readonly=True)
    days_in_stock = fields.Integer(string='Days in Stock', readonly=True)
    aging_bucket = fields.Selection([
        ('0_30', '0 – 30 Days'),
        ('31_60', '31 – 60 Days'),
        ('61_90', '61 – 90 Days'),
        ('91_180', '91 – 180 Days'),
        ('over_180', 'Over 180 Days'),
        ('unknown', 'Unknown'),
    ], string='Aging Bucket', readonly=True)

    # ── Valuation ────────────────────────────────────────────────────────────
    cost_price = fields.Float(string='Cost Price', readonly=True, digits='Product Price')
    total_value = fields.Monetary(
        string='Stock Value', readonly=True, currency_field='currency_id')

    # ─────────────────────────────────────────────────────────────────────────

    def _auto_init(self):
        self.init()
        return super()._auto_init()

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE VIEW %s AS (%s)""" % (self._table, self._get_query()))

    def _get_query(self):
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
                sq.quantity                                          AS qty_on_hand,
                sq.in_date,
                CASE
                    WHEN sq.in_date IS NULL THEN NULL
                    ELSE EXTRACT(
                        DAY FROM (NOW() AT TIME ZONE 'UTC' - sq.in_date)
                    )::integer
                END                                                  AS days_in_stock,
                CASE
                    WHEN sq.in_date IS NULL THEN 'unknown'
                    WHEN EXTRACT(DAY FROM (NOW() AT TIME ZONE 'UTC' - sq.in_date)) <= 30
                        THEN '0_30'
                    WHEN EXTRACT(DAY FROM (NOW() AT TIME ZONE 'UTC' - sq.in_date)) <= 60
                        THEN '31_60'
                    WHEN EXTRACT(DAY FROM (NOW() AT TIME ZONE 'UTC' - sq.in_date)) <= 90
                        THEN '61_90'
                    WHEN EXTRACT(DAY FROM (NOW() AT TIME ZONE 'UTC' - sq.in_date)) <= 180
                        THEN '91_180'
                    ELSE 'over_180'
                END                                                  AS aging_bucket,
                {cost_expr}                                          AS cost_price,
                sq.quantity * {cost_expr}                            AS total_value
            FROM stock_quant sq
            JOIN product_product  pp  ON pp.id = sq.product_id
            JOIN product_template pt  ON pt.id = pp.product_tmpl_id
            JOIN stock_location   sl  ON sl.id = sq.location_id
            JOIN res_company      rc  ON rc.id = sq.company_id
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
        """
