# -*- coding: utf-8 -*-
import base64
import io
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False


class InventoryReportWizard(models.TransientModel):
    _name = "inventory.report.wizard"
    _description = "Inventory Advanced Reports"

    # ── Report selector ───────────────────────────────────────────────────────
    report_type = fields.Selection(
        selection=[
            ("aging",         "Inventory Aging Report"),
            ("age_breakdown", "Age Breakdown Report"),
            ("fsn",           "FSN Analysis (Fast / Slow / Non-Moving)"),
            ("xyz",           "XYZ Analysis (Value Classification)"),
            ("fsn_xyz",       "FSN & XYZ Combined"),
            ("overstock",     "Overstock Analysis"),
            ("out_of_stock",  "Out of Stock Analysis"),
            ("movement",      "Stock Movement Report"),
        ],
        string="Report Type",
        required=True,
        default="aging",
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    date_from = fields.Date(
        string="Date From",
        default=lambda self: date.today().replace(month=1, day=1),
    )
    date_to = fields.Date(
        string="Date To",
        default=fields.Date.today,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse")
    product_ids = fields.Many2many("product.product", string="Products")
    category_ids = fields.Many2many("product.category", string="Product Categories")

    # ── Aging thresholds ──────────────────────────────────────────────────────
    aging_threshold_1 = fields.Integer("Threshold 1 (days)", default=30)
    aging_threshold_2 = fields.Integer("Threshold 2 (days)", default=60)
    aging_threshold_3 = fields.Integer("Threshold 3 (days)", default=90)

    # ── FSN parameters ────────────────────────────────────────────────────────
    fsn_fast_pct = fields.Float(
        "Fast Threshold (%)", default=30.0,
        help="Products whose daily rate is ≥ this % of the maximum rate are Fast",
    )

    # ── XYZ parameters ────────────────────────────────────────────────────────
    xyz_x_pct = fields.Float(
        "X Class Cumulative %", default=70.0,
        help="Items covering the top X% of total consumption value",
    )
    xyz_y_pct = fields.Float(
        "Y Class Cumulative %", default=90.0,
        help="Items covering the next band up to Y% of total consumption value",
    )

    # ── Overstock / Out-of-Stock ──────────────────────────────────────────────
    coverage_days = fields.Integer("Target Coverage (days)", default=30)

    # =========================================================================
    # Helper: internal locations
    # =========================================================================
    def _get_locations(self):
        domain = [("usage", "=", "internal"), ("company_id", "=", self.company_id.id)]
        if self.warehouse_id:
            wh = self.warehouse_id
            domain.append(("complete_name", "like", wh.name + "%"))
        return self.env["stock.location"].search(domain)

    def _quant_extra_domain(self):
        extra = []
        if self.product_ids:
            extra.append(("product_id", "in", self.product_ids.ids))
        if self.category_ids:
            extra.append(("product_id.categ_id", "in", self.category_ids.ids))
        return extra

    def _move_extra_domain(self):
        extra = []
        if self.product_ids:
            extra.append(("product_id", "in", self.product_ids.ids))
        if self.category_ids:
            extra.append(("product_id.categ_id", "in", self.category_ids.ids))
        return extra

    def _aging_band(self, days):
        t1, t2, t3 = self.aging_threshold_1, self.aging_threshold_2, self.aging_threshold_3
        if days <= t1:
            return f"0 – {t1} days"
        if days <= t2:
            return f"{t1 + 1} – {t2} days"
        if days <= t3:
            return f"{t2 + 1} – {t3} days"
        return f"> {t3} days"

    # =========================================================================
    # Report 1 — Inventory Aging
    # =========================================================================
    def _compute_aging_data(self):
        today = date.today()
        locations = self._get_locations()

        quants = self.env["stock.quant"].search(
            [("location_id", "in", locations.ids), ("quantity", ">", 0)]
            + self._quant_extra_domain()
        )

        rows = []
        for q in quants:
            in_date = q.in_date.date() if q.in_date else today
            days = (today - in_date).days
            cost = q.product_id.standard_price
            rows.append({
                "product":     q.product_id.display_name,
                "category":    q.product_id.categ_id.name,
                "location":    q.location_id.complete_name,
                "lot":         q.lot_id.name if q.lot_id else "",
                "quantity":    round(q.quantity, 2),
                "uom":         q.product_uom_id.name,
                "unit_cost":   round(cost, 2),
                "stock_value": round(q.quantity * cost, 2),
                "in_date":     in_date.strftime("%Y-%m-%d"),
                "days":        days,
                "aging_band":  self._aging_band(days),
            })

        rows.sort(key=lambda r: r["days"], reverse=True)
        return rows

    # =========================================================================
    # Report 2 — Age Breakdown
    # =========================================================================
    def _compute_age_breakdown_data(self):
        rows = self._compute_aging_data()

        bands_order = [
            self._aging_band(0),
            self._aging_band(self.aging_threshold_1 + 1),
            self._aging_band(self.aging_threshold_2 + 1),
            self._aging_band(self.aging_threshold_3 + 1),
        ]

        bands = {}
        for row in rows:
            b = row["aging_band"]
            if b not in bands:
                bands[b] = {"band": b, "count": 0, "total_qty": 0.0, "total_value": 0.0}
            bands[b]["count"] += 1
            bands[b]["total_qty"] = round(bands[b]["total_qty"] + row["quantity"], 2)
            bands[b]["total_value"] = round(bands[b]["total_value"] + row["stock_value"], 2)

        summary = [bands[b] for b in bands_order if b in bands]
        return {"summary": summary, "rows": rows}

    # =========================================================================
    # Report 3 — FSN Analysis
    # =========================================================================
    def _compute_fsn_data(self):
        date_from = self.date_from or (date.today() - timedelta(days=365))
        date_to   = self.date_to   or date.today()
        period_days = max((date_to - date_from).days, 1)

        locations = self._get_locations()

        # Outgoing moves
        moves = self.env["stock.move.line"].search(
            [
                ("state", "=", "done"),
                ("date", ">=", f"{date_from} 00:00:00"),
                ("date", "<=", f"{date_to} 23:59:59"),
                ("location_id", "in", locations.ids),
                ("location_dest_id.usage", "!=", "internal"),
                ("company_id", "=", self.company_id.id),
            ]
            + self._move_extra_domain()
        )

        product_out = {}
        for ml in moves:
            pid = ml.product_id.id
            if pid not in product_out:
                product_out[pid] = {"product": ml.product_id, "qty": 0.0, "count": 0}
            product_out[pid]["qty"] += ml.qty_done
            product_out[pid]["count"] += 1

        # Current stock
        quants = self.env["stock.quant"].search(
            [("location_id", "in", locations.ids)]
            + self._quant_extra_domain()
        )
        stock_map = {}
        for q in quants:
            pid = q.product_id.id
            stock_map[pid] = stock_map.get(pid, 0.0) + q.quantity

        all_pids = set(stock_map.keys()) | set(product_out.keys())

        # Resolve product records
        product_map = {q.product_id.id: q.product_id for q in quants}
        for pid, d in product_out.items():
            if pid not in product_map:
                product_map[pid] = d["product"]

        max_rate = max(
            (product_out[pid]["qty"] / period_days for pid in product_out), default=1.0
        ) or 1.0

        rows = []
        for pid in all_pids:
            prod = product_map.get(pid)
            if not prod:
                continue
            qty_out = product_out.get(pid, {}).get("qty", 0.0)
            count   = product_out.get(pid, {}).get("count", 0)
            rate    = qty_out / period_days
            rate_pct = (rate / max_rate) * 100

            if qty_out == 0:
                cls = "N"
            elif rate_pct >= self.fsn_fast_pct:
                cls = "F"
            else:
                cls = "S"

            rows.append({
                "product":             prod.display_name,
                "category":            prod.categ_id.name,
                "uom":                 prod.uom_id.name,
                "stock_qty":           round(stock_map.get(pid, 0.0), 2),
                "qty_out":             round(qty_out, 2),
                "move_count":          count,
                "daily_rate":          round(rate, 4),
                "classification":      cls,
                "classification_label": {"F": "Fast", "S": "Slow", "N": "Non-Moving"}[cls],
            })

        order = {"F": 0, "S": 1, "N": 2}
        rows.sort(key=lambda r: (order[r["classification"]], -r["qty_out"]))
        return rows

    # =========================================================================
    # Report 4 — XYZ Analysis
    # =========================================================================
    def _compute_xyz_data(self):
        date_from = self.date_from or date.today().replace(month=1, day=1)
        date_to   = self.date_to   or date.today()

        moves = self.env["stock.move.line"].search(
            [
                ("state", "=", "done"),
                ("date", ">=", f"{date_from} 00:00:00"),
                ("date", "<=", f"{date_to} 23:59:59"),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "!=", "internal"),
                ("company_id", "=", self.company_id.id),
            ]
            + self._move_extra_domain()
        )

        product_val = {}
        for ml in moves:
            pid = ml.product_id.id
            if pid not in product_val:
                product_val[pid] = {
                    "product":           ml.product_id.display_name,
                    "category":          ml.product_id.categ_id.name,
                    "uom":               ml.product_id.uom_id.name,
                    "qty_consumed":      0.0,
                    "consumption_value": 0.0,
                }
            cost = ml.product_id.standard_price
            product_val[pid]["qty_consumed"]      += ml.qty_done
            product_val[pid]["consumption_value"] += ml.qty_done * cost

        if not product_val:
            return []

        rows = list(product_val.values())
        total = sum(r["consumption_value"] for r in rows) or 1.0
        rows.sort(key=lambda r: r["consumption_value"], reverse=True)

        cumulative = 0.0
        for row in rows:
            cumulative += row["consumption_value"]
            cum_pct = (cumulative / total) * 100
            val_pct = (row["consumption_value"] / total) * 100

            if cum_pct <= self.xyz_x_pct:
                cls = "X"
            elif cum_pct <= self.xyz_y_pct:
                cls = "Y"
            else:
                cls = "Z"

            row["qty_consumed"]      = round(row["qty_consumed"], 2)
            row["consumption_value"] = round(row["consumption_value"], 2)
            row["value_pct"]         = round(val_pct, 2)
            row["cumulative_pct"]    = round(cum_pct, 2)
            row["classification"]    = cls
            row["classification_label"] = {
                "X": "X – High Value",
                "Y": "Y – Medium Value",
                "Z": "Z – Low Value",
            }[cls]

        return rows

    # =========================================================================
    # Report 5 — FSN & XYZ Combined
    # =========================================================================
    def _compute_fsn_xyz_data(self):
        fsn_rows = self._compute_fsn_data()
        xyz_rows = self._compute_xyz_data()
        xyz_map  = {r["product"]: r["classification"] for r in xyz_rows}

        rows = []
        for fsn in fsn_rows:
            xyz_cls = xyz_map.get(fsn["product"], "Z")
            rows.append({
                **fsn,
                "xyz_classification": xyz_cls,
                "combined":           f"{fsn['classification']}{xyz_cls}",
            })
        return rows

    # =========================================================================
    # Report 6 — Overstock Analysis
    # =========================================================================
    def _compute_overstock_data(self):
        date_from = self.date_from or (date.today() - timedelta(days=365))
        date_to   = self.date_to   or date.today()
        period_days = max((date_to - date_from).days, 1)

        locations = self._get_locations()

        quants = self.env["stock.quant"].search(
            [("location_id", "in", locations.ids), ("quantity", ">", 0)]
            + self._quant_extra_domain()
        )

        stock_map = {}
        for q in quants:
            pid = q.product_id.id
            if pid not in stock_map:
                stock_map[pid] = {"product": q.product_id, "qty": 0.0, "value": 0.0}
            stock_map[pid]["qty"]   += q.quantity
            stock_map[pid]["value"] += q.quantity * q.product_id.standard_price

        if not stock_map:
            return []

        moves = self.env["stock.move.line"].search([
            ("state", "=", "done"),
            ("date", ">=", f"{date_from} 00:00:00"),
            ("date", "<=", f"{date_to} 23:59:59"),
            ("location_id", "in", locations.ids),
            ("location_dest_id.usage", "!=", "internal"),
            ("product_id", "in", list(stock_map.keys())),
            ("company_id", "=", self.company_id.id),
        ])

        consumption = {}
        for ml in moves:
            pid = ml.product_id.id
            consumption[pid] = consumption.get(pid, 0.0) + ml.qty_done

        rows = []
        for pid, data in stock_map.items():
            prod       = data["product"]
            stock_qty  = data["qty"]
            daily      = consumption.get(pid, 0.0) / period_days
            target_qty = daily * self.coverage_days
            excess_qty = max(stock_qty - target_qty, 0.0)

            if excess_qty < 0.01:
                continue

            coverage = round(stock_qty / daily, 1) if daily > 0 else 9999
            rows.append({
                "product":          prod.display_name,
                "category":         prod.categ_id.name,
                "uom":              prod.uom_id.name,
                "stock_qty":        round(stock_qty, 2),
                "stock_value":      round(data["value"], 2),
                "daily_consumption":round(daily, 4),
                "target_qty":       round(target_qty, 2),
                "excess_qty":       round(excess_qty, 2),
                "excess_value":     round(excess_qty * prod.standard_price, 2),
                "coverage_days":    coverage,
            })

        rows.sort(key=lambda r: r["excess_value"], reverse=True)
        return rows

    # =========================================================================
    # Report 7 — Out of Stock Analysis
    # =========================================================================
    def _compute_out_of_stock_data(self):
        date_from = self.date_from or (date.today() - timedelta(days=90))
        date_to   = self.date_to   or date.today()
        period_days = max((date_to - date_from).days, 1)

        domain = [("type", "in", ["product", "consu"])]
        if self.product_ids:
            domain.append(("id", "in", self.product_ids.ids))
        if self.category_ids:
            domain.append(("categ_id", "in", self.category_ids.ids))
        products = self.env["product.product"].search(domain)

        locations = self._get_locations()

        quants = self.env["stock.quant"].search([
            ("location_id", "in", locations.ids),
            ("product_id", "in", products.ids),
        ])
        stock_map = {}
        for q in quants:
            pid = q.product_id.id
            stock_map[pid] = stock_map.get(pid, 0.0) + q.quantity

        moves = self.env["stock.move.line"].search([
            ("state", "=", "done"),
            ("date", ">=", f"{date_from} 00:00:00"),
            ("date", "<=", f"{date_to} 23:59:59"),
            ("location_id", "in", locations.ids),
            ("location_dest_id.usage", "!=", "internal"),
            ("product_id", "in", products.ids),
            ("company_id", "=", self.company_id.id),
        ])
        consumption = {}
        for ml in moves:
            pid = ml.product_id.id
            consumption[pid] = consumption.get(pid, 0.0) + ml.qty_done

        orderpoints = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "in", products.ids),
            ("company_id", "=", self.company_id.id),
        ])
        reorder_map = {op.product_id.id: op.product_min_qty for op in orderpoints}

        rows = []
        for prod in products:
            pid = prod.id
            stock_qty  = stock_map.get(pid, 0.0)
            daily      = consumption.get(pid, 0.0) / period_days
            reorder_pt = reorder_map.get(pid, 0.0)
            days_rem   = round(stock_qty / daily, 1) if daily > 0 else None

            if stock_qty <= 0:
                status = "out_of_stock"
            elif stock_qty <= reorder_pt:
                status = "below_reorder"
            elif days_rem is not None and days_rem < self.coverage_days:
                status = "low_stock"
            else:
                continue

            rows.append({
                "product":          prod.display_name,
                "category":         prod.categ_id.name,
                "uom":              prod.uom_id.name,
                "stock_qty":        round(stock_qty, 2),
                "reorder_point":    round(reorder_pt, 2),
                "daily_consumption":round(daily, 4),
                "days_remaining":   days_rem if days_rem is not None else "–",
                "status":           status,
                "status_label":     {
                    "out_of_stock":   "Out of Stock",
                    "below_reorder":  "Below Reorder Point",
                    "low_stock":      "Low Stock",
                }[status],
            })

        order = {"out_of_stock": 0, "below_reorder": 1, "low_stock": 2}
        rows.sort(key=lambda r: order[r["status"]])
        return rows

    # =========================================================================
    # Report 8 — Stock Movement
    # =========================================================================
    def _compute_movement_data(self):
        date_from = self.date_from or date.today().replace(day=1)
        date_to   = self.date_to   or date.today()

        domain = [
            ("state", "=", "done"),
            ("date", ">=", f"{date_from} 00:00:00"),
            ("date", "<=", f"{date_to} 23:59:59"),
            ("company_id", "=", self.company_id.id),
        ] + self._move_extra_domain()

        if self.warehouse_id:
            locations = self._get_locations()
            domain += [
                "|",
                ("location_id", "in", locations.ids),
                ("location_dest_id", "in", locations.ids),
            ]

        moves = self.env["stock.move.line"].search(domain, order="date asc", limit=2000)

        rows = []
        for ml in moves:
            src_use = ml.location_id.usage
            dst_use = ml.location_dest_id.usage
            if src_use == "supplier" or (src_use not in ("internal",) and dst_use == "internal"):
                mtype = "Receipt"
            elif dst_use == "customer" or (src_use == "internal" and dst_use not in ("internal",)):
                mtype = "Delivery"
            elif src_use == "internal" and dst_use == "internal":
                mtype = "Internal Transfer"
            else:
                mtype = "Other"

            rows.append({
                "date":          ml.date.strftime("%Y-%m-%d %H:%M") if ml.date else "",
                "product":       ml.product_id.display_name,
                "category":      ml.product_id.categ_id.name,
                "lot":           ml.lot_id.name if ml.lot_id else "",
                "from_location": ml.location_id.complete_name,
                "to_location":   ml.location_dest_id.complete_name,
                "move_type":     mtype,
                "qty_done":      round(ml.qty_done, 2),
                "uom":           ml.product_uom_id.name,
                "reference":     ml.reference or "",
            })
        return rows

    # =========================================================================
    # Action: Print PDF
    # =========================================================================
    def action_print_pdf(self):
        ref_map = {
            "aging":         "tts_inventory_advanced_reports.action_report_inventory_aging",
            "age_breakdown": "tts_inventory_advanced_reports.action_report_age_breakdown",
            "fsn":           "tts_inventory_advanced_reports.action_report_fsn",
            "xyz":           "tts_inventory_advanced_reports.action_report_xyz",
            "fsn_xyz":       "tts_inventory_advanced_reports.action_report_fsn_xyz",
            "overstock":     "tts_inventory_advanced_reports.action_report_overstock",
            "out_of_stock":  "tts_inventory_advanced_reports.action_report_out_of_stock",
            "movement":      "tts_inventory_advanced_reports.action_report_movement",
        }
        return self.env.ref(ref_map[self.report_type]).report_action(self)

    # =========================================================================
    # Action: Export Excel
    # =========================================================================
    def action_export_excel(self):
        if not HAS_XLSXWRITER:
            raise UserError(
                _("The 'xlsxwriter' Python library is not installed.\n"
                  "Please install it: pip install xlsxwriter")
            )

        output   = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        {
            "aging":         self._xl_aging,
            "age_breakdown": self._xl_age_breakdown,
            "fsn":           self._xl_fsn,
            "xyz":           self._xl_xyz,
            "fsn_xyz":       self._xl_fsn_xyz,
            "overstock":     self._xl_overstock,
            "out_of_stock":  self._xl_out_of_stock,
            "movement":      self._xl_movement,
        }[self.report_type](workbook)

        workbook.close()

        names = dict(self._fields["report_type"].selection)
        filename = names.get(self.report_type, "report").split("(")[0].strip().replace(" ", "_") + ".xlsx"

        attachment = self.env["ir.attachment"].create({
            "name":      filename,
            "type":      "binary",
            "datas":     base64.b64encode(output.getvalue()),
            "res_model": self._name,
            "res_id":    self.id,
        })
        return {
            "type":   "ir.actions.act_url",
            "url":    f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }

    # ── Excel format helpers ──────────────────────────────────────────────────
    def _xl_fmt(self, wb):
        H = {"bold": True, "bg_color": "#1e3a8a", "font_color": "white",
             "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True}
        return {
            "header": wb.add_format(H),
            "title":  wb.add_format({"bold": True, "font_size": 13, "font_color": "#1e3a8a"}),
            "meta":   wb.add_format({"italic": True, "font_color": "#555555"}),
            "money":  wb.add_format({"num_format": "#,##0.00"}),
            "num":    wb.add_format({"num_format": "#,##0"}),
            "pct":    wb.add_format({"num_format": "0.00"}),
            "alt":    wb.add_format({"bg_color": "#f0f4ff"}),
            "bold":   wb.add_format({"bold": True}),
            "green":  wb.add_format({"bold": True, "font_color": "#166534"}),
            "orange": wb.add_format({"bold": True, "font_color": "#92400e"}),
            "red":    wb.add_format({"bold": True, "font_color": "#991b1b"}),
            "blue":   wb.add_format({"bold": True, "font_color": "#1e40af"}),
        }

    def _xl_meta(self, ws, fmt, title):
        ws.set_row(0, 22)
        ws.write(0, 0, title, fmt["title"])
        ws.write(1, 0, f"Company: {self.company_id.name}", fmt["meta"])
        ws.write(2, 0, f"Period: {self.date_from or '–'} to {self.date_to or '–'}", fmt["meta"])
        if self.warehouse_id:
            ws.write(3, 0, f"Warehouse: {self.warehouse_id.name}", fmt["meta"])
        return 5

    def _xl_headers(self, ws, row, headers, fmt):
        ws.set_row(row, 18)
        for col, h in enumerate(headers):
            ws.write(row, col, h, fmt["header"])
        return row + 1

    # ── Excel writers (one per report type) ──────────────────────────────────
    def _xl_aging(self, wb):
        ws  = wb.add_worksheet("Inventory Aging")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "Inventory Aging Report")

        headers = ["Product", "Category", "Location", "Lot/Serial",
                   "Qty", "UoM", "Unit Cost", "Stock Value", "Date In",
                   "Days in Stock", "Aging Band"]
        row = self._xl_headers(ws, row, headers, fmt)

        for i, r in enumerate(self._compute_aging_data()):
            f = fmt["alt"] if i % 2 else None
            ws.write(row, 0,  r["product"],     f)
            ws.write(row, 1,  r["category"],    f)
            ws.write(row, 2,  r["location"],    f)
            ws.write(row, 3,  r["lot"],         f)
            ws.write(row, 4,  r["quantity"],    f)
            ws.write(row, 5,  r["uom"],         f)
            ws.write(row, 6,  r["unit_cost"],   fmt["money"])
            ws.write(row, 7,  r["stock_value"], fmt["money"])
            ws.write(row, 8,  r["in_date"],     f)
            ws.write(row, 9,  r["days"],        fmt["num"])
            ws.write(row, 10, r["aging_band"],  f)
            row += 1

        ws.set_column(0, 0, 32)
        ws.set_column(1, 1, 20)
        ws.set_column(2, 2, 28)
        ws.set_column(6, 7, 14)
        ws.set_column(8, 8, 12)
        ws.set_column(10, 10, 16)

    def _xl_age_breakdown(self, wb):
        ws  = wb.add_worksheet("Age Breakdown")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "Age Breakdown Report")
        data = self._compute_age_breakdown_data()

        ws.write(row, 0, "Summary", fmt["bold"])
        row += 1
        row = self._xl_headers(ws, row, ["Aging Band", "Products", "Total Qty", "Total Value"], fmt)
        for s in data["summary"]:
            ws.write_row(row, 0, [s["band"], s["count"], s["total_qty"], s["total_value"]])
            row += 1

        row += 2
        ws.write(row, 0, "Detail", fmt["bold"])
        row += 1
        row = self._xl_headers(ws, row,
            ["Product", "Category", "Qty", "Stock Value", "Days in Stock", "Aging Band"], fmt)
        for i, r in enumerate(data["rows"]):
            ws.write_row(row, 0, [r["product"], r["category"], r["quantity"],
                                   r["stock_value"], r["days"], r["aging_band"]])
            row += 1
        ws.set_column(0, 0, 32)
        ws.set_column(1, 1, 20)

    def _xl_fsn(self, wb):
        ws  = wb.add_worksheet("FSN Analysis")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "FSN Analysis Report")

        row = self._xl_headers(ws, row,
            ["Product", "Category", "UoM", "Stock Qty", "Qty Out",
             "Move Count", "Daily Rate", "Classification"], fmt)

        cls_fmt = {"F": fmt["green"], "S": fmt["orange"], "N": fmt["red"]}
        for r in self._compute_fsn_data():
            ws.write(row, 0, r["product"])
            ws.write(row, 1, r["category"])
            ws.write(row, 2, r["uom"])
            ws.write(row, 3, r["stock_qty"])
            ws.write(row, 4, r["qty_out"])
            ws.write(row, 5, r["move_count"])
            ws.write(row, 6, r["daily_rate"])
            ws.write(row, 7, r["classification_label"], cls_fmt.get(r["classification"]))
            row += 1
        ws.set_column(0, 0, 32)
        ws.set_column(1, 1, 20)

    def _xl_xyz(self, wb):
        ws  = wb.add_worksheet("XYZ Analysis")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "XYZ Analysis Report")

        row = self._xl_headers(ws, row,
            ["Product", "Category", "UoM", "Qty Consumed",
             "Consumption Value", "Value %", "Cumulative %", "Classification"], fmt)

        cls_fmt = {"X": fmt["green"], "Y": fmt["orange"], "Z": fmt["red"]}
        for r in self._compute_xyz_data():
            ws.write(row, 0, r["product"])
            ws.write(row, 1, r["category"])
            ws.write(row, 2, r["uom"])
            ws.write(row, 3, r["qty_consumed"])
            ws.write(row, 4, r["consumption_value"], fmt["money"])
            ws.write(row, 5, r["value_pct"])
            ws.write(row, 6, r["cumulative_pct"])
            ws.write(row, 7, r["classification_label"],
                     cls_fmt.get(r["classification"]))
            row += 1
        ws.set_column(0, 0, 32)
        ws.set_column(4, 4, 18)

    def _xl_fsn_xyz(self, wb):
        ws  = wb.add_worksheet("FSN-XYZ Combined")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "FSN & XYZ Combined Report")

        row = self._xl_headers(ws, row,
            ["Product", "Category", "UoM", "Stock Qty", "Qty Out",
             "FSN Class", "XYZ Class", "Combined"], fmt)

        for r in self._compute_fsn_xyz_data():
            ws.write_row(row, 0, [
                r["product"], r["category"], r["uom"], r["stock_qty"], r["qty_out"],
                r["classification_label"], r["xyz_classification"], r["combined"],
            ])
            row += 1
        ws.set_column(0, 0, 32)

    def _xl_overstock(self, wb):
        ws  = wb.add_worksheet("Overstock Analysis")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "Overstock Analysis Report")

        row = self._xl_headers(ws, row,
            ["Product", "Category", "UoM", "Stock Qty", "Stock Value",
             "Daily Consumption", "Target Qty", "Excess Qty",
             "Excess Value", "Coverage (days)"], fmt)

        for r in self._compute_overstock_data():
            ws.write(row, 0, r["product"])
            ws.write(row, 1, r["category"])
            ws.write(row, 2, r["uom"])
            ws.write(row, 3, r["stock_qty"])
            ws.write(row, 4, r["stock_value"],       fmt["money"])
            ws.write(row, 5, r["daily_consumption"])
            ws.write(row, 6, r["target_qty"])
            ws.write(row, 7, r["excess_qty"])
            ws.write(row, 8, r["excess_value"],      fmt["money"])
            ws.write(row, 9, r["coverage_days"])
            row += 1
        ws.set_column(0, 0, 32)
        ws.set_column(4, 4, 14)
        ws.set_column(8, 8, 14)

    def _xl_out_of_stock(self, wb):
        ws  = wb.add_worksheet("Out of Stock")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "Out of Stock Analysis Report")

        row = self._xl_headers(ws, row,
            ["Product", "Category", "UoM", "Stock Qty", "Reorder Point",
             "Daily Consumption", "Days Remaining", "Status"], fmt)

        status_fmt = {
            "out_of_stock":  fmt["red"],
            "below_reorder": fmt["orange"],
            "low_stock":     fmt["blue"],
        }
        for r in self._compute_out_of_stock_data():
            ws.write(row, 0, r["product"])
            ws.write(row, 1, r["category"])
            ws.write(row, 2, r["uom"])
            ws.write(row, 3, r["stock_qty"])
            ws.write(row, 4, r["reorder_point"])
            ws.write(row, 5, r["daily_consumption"])
            ws.write(row, 6, str(r["days_remaining"]))
            ws.write(row, 7, r["status_label"], status_fmt.get(r["status"]))
            row += 1
        ws.set_column(0, 0, 32)

    def _xl_movement(self, wb):
        ws  = wb.add_worksheet("Stock Movement")
        fmt = self._xl_fmt(wb)
        row = self._xl_meta(ws, fmt, "Stock Movement Report")

        row = self._xl_headers(ws, row,
            ["Date", "Product", "Category", "Lot/Serial",
             "From Location", "To Location", "Type",
             "Qty Done", "UoM", "Reference"], fmt)

        for r in self._compute_movement_data():
            ws.write_row(row, 0, [
                r["date"], r["product"], r["category"], r["lot"],
                r["from_location"], r["to_location"], r["move_type"],
                r["qty_done"], r["uom"], r["reference"],
            ])
            row += 1
        ws.set_column(0, 0, 18)
        ws.set_column(1, 1, 30)
        ws.set_column(4, 5, 25)
