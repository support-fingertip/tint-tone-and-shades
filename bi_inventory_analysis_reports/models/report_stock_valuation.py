# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BiStockValuationReport(models.Model):
    """Stock Valuation Report — SQL view over stock.valuation.layer.
    Supports AVCO, FIFO, and Standard costing methods.
    """

    _name = 'bi.stock.valuation.report'
    _description = 'Stock Valuation Report'
    _auto = False
    _rec_name = 'product_id'
    _order = 'date desc, product_id'
    _log_access = False

    # ── Product ──────────────────────────────────────────────────────────────
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)

    # ── Move context ─────────────────────────────────────────────────────────
    stock_move_id = fields.Many2one('stock.move', string='Stock Move', readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', string='Operation Type', readonly=True)
    location_id = fields.Many2one('stock.location', string='From Location', readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='To Location', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)

    # ── Company / Currency ───────────────────────────────────────────────────
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # ── Layer data ───────────────────────────────────────────────────────────
    quantity = fields.Float(
        string='Quantity', readonly=True, digits='Product Unit of Measure')
    unit_cost = fields.Float(string='Unit Cost', readonly=True, digits='Product Price')
    total_value = fields.Monetary(
        string='Total Value', readonly=True, currency_field='currency_id')
    remaining_qty = fields.Float(
        string='Remaining Qty', readonly=True, digits='Product Unit of Measure')
    remaining_value = fields.Monetary(
        string='Remaining Value', readonly=True, currency_field='currency_id')
    description = fields.Char(string='Description', readonly=True)

    # ── Movement direction ───────────────────────────────────────────────────
    movement_type = fields.Selection([
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
    ], string='Direction', readonly=True)

    # ── Dates ────────────────────────────────────────────────────────────────
    date = fields.Datetime(string='Date', readonly=True)
    date_month = fields.Date(string='Month', readonly=True)

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _svl_exists(cr):
        cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'stock_valuation_layer')"
        )
        return cr.fetchone()[0]

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        if not self._svl_exists(self.env.cr):
            # stock_account not installed — create an empty view with correct column types
            self.env.cr.execute(f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    SELECT
                        NULL::integer           AS id,
                        NULL::integer           AS product_id,
                        NULL::integer           AS product_tmpl_id,
                        NULL::integer           AS categ_id,
                        NULL::integer           AS uom_id,
                        NULL::integer           AS stock_move_id,
                        NULL::integer           AS picking_type_id,
                        NULL::integer           AS location_id,
                        NULL::integer           AS location_dest_id,
                        NULL::integer           AS partner_id,
                        NULL::integer           AS company_id,
                        NULL::integer           AS currency_id,
                        NULL::double precision  AS quantity,
                        NULL::double precision  AS unit_cost,
                        NULL::double precision  AS total_value,
                        NULL::double precision  AS remaining_qty,
                        NULL::double precision  AS remaining_value,
                        NULL::varchar           AS description,
                        NULL::varchar           AS movement_type,
                        NULL::timestamp         AS date,
                        NULL::date              AS date_month
                    WHERE FALSE
                )
            """)
            return

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    svl.id,
                    svl.product_id,
                    pp.product_tmpl_id,
                    pt.categ_id,
                    svl.uom_id,
                    svl.stock_move_id,
                    sm.picking_type_id,
                    sm.location_id,
                    sm.location_dest_id,
                    sm.partner_id,
                    svl.company_id,
                    rc.currency_id,
                    svl.quantity,
                    svl.unit_cost,
                    svl.value                                       AS total_value,
                    svl.remaining_qty,
                    svl.remaining_value,
                    svl.description,
                    CASE
                        WHEN svl.quantity >= 0 THEN 'in'
                        ELSE 'out'
                    END                                             AS movement_type,
                    svl.create_date                                 AS date,
                    DATE_TRUNC('month', svl.create_date)::date      AS date_month
                FROM stock_valuation_layer svl
                JOIN product_product  pp ON pp.id = svl.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                JOIN res_company      rc ON rc.id = svl.company_id
                LEFT JOIN stock_move  sm ON sm.id = svl.stock_move_id
            )
        """)
