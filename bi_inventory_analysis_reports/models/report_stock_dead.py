# -*- coding: utf-8 -*-
from odoo import fields, models


class BiStockDeadReport(models.Model):
    """Dead / Slow-Moving Stock Report.
    Identifies products with no movement activity for an extended period.
    Severity is computed from the last done move date per product+location.
    """

    _name = 'bi.stock.dead.report'
    _description = 'Dead / Slow-Moving Stock Report'
    _auto = False
    _rec_name = 'product_id'
    _order = 'days_no_movement desc, product_id'
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

    # ── Movement analysis ────────────────────────────────────────────────────
    last_move_date = fields.Datetime(string='Last Move Date', readonly=True)
    days_no_movement = fields.Integer(string='Days Without Movement', readonly=True)
    stock_status = fields.Selection([
        ('active', 'Active (< 90 days)'),
        ('slow_moving', 'Slow Moving (90–180 days)'),
        ('dead', 'Dead Stock (> 180 days)'),
        ('no_movement', 'No Movement Ever'),
    ], string='Stock Status', readonly=True)

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
                sq.quantity                                          AS qty_on_hand,
                last_mv.last_date                                    AS last_move_date,
                CASE
                    WHEN last_mv.last_date IS NULL THEN NULL
                    ELSE EXTRACT(
                        DAY FROM (NOW() AT TIME ZONE 'UTC' - last_mv.last_date)
                    )::integer
                END                                                  AS days_no_movement,
                CASE
                    WHEN last_mv.last_date IS NULL
                        THEN 'no_movement'
                    WHEN EXTRACT(
                        DAY FROM (NOW() AT TIME ZONE 'UTC' - last_mv.last_date)
                    ) > 180
                        THEN 'dead'
                    WHEN EXTRACT(
                        DAY FROM (NOW() AT TIME ZONE 'UTC' - last_mv.last_date)
                    ) > 90
                        THEN 'slow_moving'
                    ELSE 'active'
                END                                                  AS stock_status,
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
            LEFT JOIN LATERAL (
                SELECT MAX(sm.date) AS last_date
                FROM stock_move sm
                WHERE sm.product_id = sq.product_id
                  AND sm.state = 'done'
                  AND (sm.location_id = sq.location_id
                       OR sm.location_dest_id = sq.location_id)
            ) last_mv ON TRUE
            {cost_join}
            WHERE sl.usage = 'internal'
              AND sq.quantity > 0
        """
