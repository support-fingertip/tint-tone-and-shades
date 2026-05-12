# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BiStockInventoryReport(models.Model):
    """Current Stock Inventory Analysis — SQL view over stock.quant."""

    _name = 'bi.stock.inventory.report'
    _description = 'Current Stock Inventory Analysis'
    _auto = False
    _rec_name = 'product_id'
    _order = 'product_id, location_id'
    _log_access = False

    # ── Product ──────────────────────────────────────────────────────────────
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)

    # ── Location ─────────────────────────────────────────────────────────────
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)

    # ── Lot / Owner ──────────────────────────────────────────────────────────
    lot_id = fields.Many2one('stock.lot', string='Lot / Serial No.', readonly=True)
    owner_id = fields.Many2one('res.partner', string='Owner', readonly=True)

    # ── Company / Currency ───────────────────────────────────────────────────
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # ── Quantities ───────────────────────────────────────────────────────────
    qty_on_hand = fields.Float(
        string='On Hand Qty', readonly=True, digits='Product Unit of Measure')
    qty_reserved = fields.Float(
        string='Reserved Qty', readonly=True, digits='Product Unit of Measure')
    qty_available = fields.Float(
        string='Available Qty', readonly=True, digits='Product Unit of Measure')

    # ── Dates ────────────────────────────────────────────────────────────────
    last_update = fields.Datetime(string='Last Updated', readonly=True)

    # ── Valuation ────────────────────────────────────────────────────────────
    cost_price = fields.Float(string='Cost Price', readonly=True, digits='Product Price')
    total_value = fields.Monetary(
        string='Stock Value', readonly=True, currency_field='currency_id')

    # ─────────────────────────────────────────────────────────────────────────

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sq.id,
                    sq.product_id,
                    pp.product_tmpl_id,
                    pt.categ_id,
                    pt.uom_id,
                    sq.location_id,
                    wh_lkp.warehouse_id,
                    sq.lot_id,
                    sq.owner_id,
                    sq.company_id,
                    rc.currency_id,
                    sq.quantity                                         AS qty_on_hand,
                    sq.reserved_quantity                                AS qty_reserved,
                    (sq.quantity - sq.reserved_quantity)                AS qty_available,
                    sq.in_date                                          AS last_update,
                    COALESCE(last_cost.unit_cost, 0.0)                  AS cost_price,
                    sq.quantity * COALESCE(last_cost.unit_cost, 0.0)    AS total_value
                FROM stock_quant sq
                JOIN product_product  pp  ON pp.id  = sq.product_id
                JOIN product_template pt  ON pt.id  = pp.product_tmpl_id
                JOIN stock_location   sl  ON sl.id  = sq.location_id
                JOIN res_company      rc  ON rc.id  = sq.company_id
                -- Resolve warehouse from location hierarchy
                LEFT JOIN LATERAL (
                    SELECT sw.id AS warehouse_id
                    FROM stock_warehouse  sw
                    JOIN stock_location   wv ON wv.id = sw.view_location_id
                    WHERE sl.complete_name LIKE wv.complete_name || '/%%'
                       OR sl.id = wv.id
                    ORDER BY LENGTH(wv.complete_name) DESC
                    LIMIT 1
                ) wh_lkp ON TRUE
                -- Latest unit cost from valuation layer
                LEFT JOIN LATERAL (
                    SELECT svl.unit_cost
                    FROM stock_valuation_layer svl
                    WHERE svl.product_id = sq.product_id
                      AND svl.company_id = sq.company_id
                    ORDER BY svl.id DESC
                    LIMIT 1
                ) last_cost ON TRUE
                WHERE sl.usage = 'internal'
                  AND sq.quantity > 0
            )
        """ % self._table)
