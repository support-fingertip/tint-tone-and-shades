# -*- coding: utf-8 -*-
from odoo import models, api


def _base_ctx(wizard):
    return {
        "company":   wizard.company_id,
        "warehouse": wizard.warehouse_id,
        "date_from": wizard.date_from,
        "date_to":   wizard.date_to,
        "wizard":    wizard,
    }


class ReportInventoryAging(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_aging"
    _description = "Inventory Aging Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        return {**_base_ctx(wizard), "rows": wizard._compute_aging_data()}


class ReportAgeBreakdown(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_age_breakdown"
    _description = "Age Breakdown Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        return {**_base_ctx(wizard), "data": wizard._compute_age_breakdown_data()}


class ReportFSN(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_fsn"
    _description = "FSN Analysis Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        rows = wizard._compute_fsn_data()
        summary = {"F": 0, "S": 0, "N": 0}
        for r in rows:
            summary[r["classification"]] = summary.get(r["classification"], 0) + 1
        return {**_base_ctx(wizard), "rows": rows, "summary": summary}


class ReportXYZ(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_xyz"
    _description = "XYZ Analysis Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        rows = wizard._compute_xyz_data()
        summary = {"X": {"count": 0, "value": 0.0}, "Y": {"count": 0, "value": 0.0}, "Z": {"count": 0, "value": 0.0}}
        for r in rows:
            c = r["classification"]
            summary[c]["count"] += 1
            summary[c]["value"] = round(summary[c]["value"] + r["consumption_value"], 2)
        return {**_base_ctx(wizard), "rows": rows, "summary": summary}


class ReportFSNXYZ(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_fsn_xyz"
    _description = "FSN & XYZ Combined Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        return {**_base_ctx(wizard), "rows": wizard._compute_fsn_xyz_data()}


class ReportOverstock(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_overstock"
    _description = "Overstock Analysis Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        rows = wizard._compute_overstock_data()
        total_excess_value = round(sum(r["excess_value"] for r in rows), 2)
        return {**_base_ctx(wizard), "rows": rows, "total_excess_value": total_excess_value}


class ReportOutOfStock(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_out_of_stock"
    _description = "Out of Stock Analysis Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        rows = wizard._compute_out_of_stock_data()
        summary = {"out_of_stock": 0, "below_reorder": 0, "low_stock": 0}
        for r in rows:
            summary[r["status"]] += 1
        return {**_base_ctx(wizard), "rows": rows, "summary": summary}


class ReportMovement(models.AbstractModel):
    _name = "report.tts_inventory_advanced_reports.report_movement"
    _description = "Stock Movement Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["inventory.report.wizard"].browse(docids)
        rows = wizard._compute_movement_data()
        types = {}
        for r in rows:
            t = r["move_type"]
            types[t] = types.get(t, 0) + 1
        return {**_base_ctx(wizard), "rows": rows, "move_types": types}
