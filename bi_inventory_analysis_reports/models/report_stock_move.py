# -*- coding: utf-8 -*-
from odoo import fields, models


class BiStockMoveReport(models.Model):
    """Stock Movement Analysis — SQL view over done stock.move records."""

    _name = 'bi.stock.move.report'
    _description = 'Stock Movement Analysis'
    _auto = False
    _rec_name = 'product_id'
    _order = 'date desc, product_id'
    _log_access = False

    # ── Move reference ───────────────────────────────────────────────────────
    origin = fields.Char(string='Source Document', readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', string='Operation Type', readonly=True)
    move_type = fields.Selection([
        ('in', 'Incoming'),
        ('out', 'Outgoing'),
        ('internal', 'Internal'),
        ('other', 'Other'),
    ], string='Move Type', readonly=True)

    # ── Product ──────────────────────────────────────────────────────────────
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)

    # ── Locations ────────────────────────────────────────────────────────────
    location_id = fields.Many2one('stock.location', string='From Location', readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='To Location', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)

    # ── Partner / Company ────────────────────────────────────────────────────
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # ── Quantities ───────────────────────────────────────────────────────────
    product_qty = fields.Float(
        string='Demand Qty', readonly=True, digits='Product Unit of Measure')
    qty_done = fields.Float(
        string='Done Qty', readonly=True, digits='Product Unit of Measure')

    # ── Valuation ────────────────────────────────────────────────────────────
    price_unit = fields.Float(string='Unit Price', readonly=True, digits='Product Price')
    total_value = fields.Monetary(
        string='Total Value', readonly=True, currency_field='currency_id')

    # ── Dates ────────────────────────────────────────────────────────────────
    date = fields.Datetime(string='Date', readonly=True)
    date_month = fields.Date(string='Month', readonly=True)

    # ─────────────────────────────────────────────────────────────────────────

    @property
    def _table_query(self):
        return """
            SELECT
                sm.id,
                sm.origin,
                sm.picking_id,
                sm.picking_type_id,
                CASE
                    WHEN spt.code = 'incoming' THEN 'in'
                    WHEN spt.code = 'outgoing' THEN 'out'
                    WHEN spt.code = 'internal' THEN 'internal'
                    ELSE 'other'
                END                                                 AS move_type,
                sm.product_id,
                pp.product_tmpl_id,
                pt.categ_id,
                sm.product_uom                                      AS uom_id,
                sm.location_id,
                sm.location_dest_id,
                wh_lkp.warehouse_id,
                sm.partner_id,
                sm.company_id,
                rc.currency_id,
                sm.product_uom_qty                                  AS product_qty,
                COALESCE(
                    (SELECT SUM(sml.quantity)
                     FROM stock_move_line sml
                     WHERE sml.move_id = sm.id
                       AND sml.state = 'done'),
                    0.0
                )                                                   AS qty_done,
                sm.price_unit,
                COALESCE(
                    (SELECT SUM(sml.quantity)
                     FROM stock_move_line sml
                     WHERE sml.move_id = sm.id
                       AND sml.state = 'done'),
                    0.0
                ) * sm.price_unit                                   AS total_value,
                sm.date,
                DATE_TRUNC('month', sm.date)::date                  AS date_month
            FROM stock_move sm
            JOIN product_product    pp  ON pp.id  = sm.product_id
            JOIN product_template   pt  ON pt.id  = pp.product_tmpl_id
            JOIN res_company        rc  ON rc.id  = sm.company_id
            LEFT JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
            LEFT JOIN stock_location     sl  ON sl.id  = sm.location_dest_id
            LEFT JOIN LATERAL (
                SELECT sw.id AS warehouse_id
                FROM stock_warehouse  sw
                JOIN stock_location   wv ON wv.id = sw.view_location_id
                WHERE sl.complete_name LIKE wv.complete_name || '/%'
                   OR sl.id = wv.id
                ORDER BY LENGTH(wv.complete_name) DESC
                LIMIT 1
            ) wh_lkp ON TRUE
            WHERE sm.state = 'done'
        """
