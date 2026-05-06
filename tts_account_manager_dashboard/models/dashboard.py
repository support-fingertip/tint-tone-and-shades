# -*- coding: utf-8 -*-
from odoo import models, api, exceptions
from datetime import datetime
from dateutil.relativedelta import relativedelta


class TtsAccountDashboard(models.AbstractModel):
    """
    Abstract model that exposes all dashboard data as @api.model methods.
    The OWL component calls these via orm.call() — no HTTP controller needed.
    All methods guard against missing optional modules (purchase, hr.expense).
    """
    _name = "tts.account.dashboard"
    _description = "TTS Account Manager Dashboard"

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry-point called by the JS component
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def get_dashboard_data(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise exceptions.AccessDenied(
                "Only Accounts Managers may access this dashboard."
            )
        return {
            "revenue": self._monthly_revenue(),
            "overheads": self._monthly_overheads(),
            "office_expenses": self._office_expenses_by_category(),
            "pending_approvals": self._pending_approvals(),
            "vendor_payments": self._vendor_payment_requests(),
            "summary": self._summary_kpis(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Widget 1 — Monthly Revenue Collection (last 12 months)
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _monthly_revenue(self):
        today = datetime.today()
        months = []
        for i in range(11, -1, -1):
            start = (today - relativedelta(months=i)).replace(day=1)
            end = start + relativedelta(months=1) - relativedelta(days=1)

            moves = self.env["account.move"].search([
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start.strftime("%Y-%m-%d")),
                ("invoice_date", "<=", end.strftime("%Y-%m-%d")),
            ])
            total = sum(
                m.amount_total if m.move_type == "out_invoice" else -m.amount_total
                for m in moves
            )
            months.append({
                "month": start.strftime("%b %Y"),
                "month_short": start.strftime("%b"),
                "year": start.strftime("%Y"),
                "amount": total,
                "count": len(moves),
            })
        return months

    # ─────────────────────────────────────────────────────────────────────────
    # Widget 2 — Monthly Overheads (last 12 months)
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _monthly_overheads(self):
        today = datetime.today()
        months = []
        for i in range(11, -1, -1):
            start = (today - relativedelta(months=i)).replace(day=1)
            end = start + relativedelta(months=1) - relativedelta(days=1)

            moves = self.env["account.move"].search([
                ("move_type", "in", ["in_invoice", "in_refund"]),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start.strftime("%Y-%m-%d")),
                ("invoice_date", "<=", end.strftime("%Y-%m-%d")),
            ])
            total = sum(
                m.amount_total if m.move_type == "in_invoice" else -m.amount_total
                for m in moves
            )
            months.append({
                "month": start.strftime("%b %Y"),
                "month_short": start.strftime("%b"),
                "year": start.strftime("%Y"),
                "amount": total,
                "count": len(moves),
            })
        return months

    # ─────────────────────────────────────────────────────────────────────────
    # Widget 3 — Office Expenses & Maintenance — categorised YTD
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _office_expenses_by_category(self):
        today = datetime.today()
        year_start = today.replace(month=1, day=1)

        lines = self.env["account.move.line"].search([
            ("move_id.state", "=", "posted"),
            ("move_id.move_type", "in", ["in_invoice", "in_refund"]),
            ("move_id.invoice_date", ">=", year_start.strftime("%Y-%m-%d")),
            ("account_id.account_type", "in", [
                "expense",
                "expense_depreciation",
                "expense_direct_cost",
            ]),
        ])

        # Aggregate by account name
        by_account = {}
        for line in lines:
            key = line.account_id.name or "Unknown"
            net = line.debit - line.credit
            by_account[key] = by_account.get(key, 0.0) + net

        by_account = {k: v for k, v in by_account.items() if v > 0}
        total = sum(by_account.values()) or 1.0

        categories = sorted(
            [
                {
                    "category": name,
                    "amount": round(amount, 2),
                    "percentage": round(amount / total * 100, 1),
                }
                for name, amount in by_account.items()
            ],
            key=lambda x: x["amount"],
            reverse=True,
        )[:12]

        # Monthly trend (last 12 months, total expense per month)
        monthly = []
        for i in range(11, -1, -1):
            start = (today - relativedelta(months=i)).replace(day=1)
            end = start + relativedelta(months=1) - relativedelta(days=1)

            ml = self.env["account.move.line"].search([
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "in", ["in_invoice", "in_refund"]),
                ("move_id.invoice_date", ">=", start.strftime("%Y-%m-%d")),
                ("move_id.invoice_date", "<=", end.strftime("%Y-%m-%d")),
                ("account_id.account_type", "in", [
                    "expense",
                    "expense_depreciation",
                    "expense_direct_cost",
                ]),
            ])
            monthly.append({
                "month": start.strftime("%b %Y"),
                "month_short": start.strftime("%b"),
                "amount": round(sum(max(l.debit - l.credit, 0) for l in ml), 2),
            })

        return {"categories": categories, "monthly": monthly}

    # ─────────────────────────────────────────────────────────────────────────
    # Widget 4 — Pending Approvals
    # Integrates with infinys_account_move_approval + infinys_purchase_order_approval
    # Falls back gracefully when those modules are absent.
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _pending_approvals(self):
        items = []

        # Account Move approvals
        AccountMove = self.env["account.move"]
        if "approval_state" in AccountMove._fields:
            for move in AccountMove.search(
                [("approval_state", "=", "pending")],
                order="invoice_date desc",
                limit=50,
            ):
                items.append({
                    "source": "Account",
                    "type": (
                        "Customer Invoice" if move.move_type == "out_invoice"
                        else "Vendor Bill" if move.move_type == "in_invoice"
                        else move.move_type.replace("_", " ").title()
                    ),
                    "name": move.name or "Draft",
                    "partner": move.partner_id.name or "",
                    "amount": round(move.amount_total, 2),
                    "currency_symbol": move.currency_id.symbol or "",
                    "date": move.invoice_date.strftime("%Y-%m-%d") if move.invoice_date else "",
                    "id": move.id,
                    "model": "account.move",
                    "approval_status": move.approval_state,
                })
        else:
            # Fallback: draft invoices/bills sitting for > 3 days
            from_date = (datetime.today() - relativedelta(days=3)).strftime("%Y-%m-%d")
            for move in AccountMove.search(
                [
                    ("state", "=", "draft"),
                    ("move_type", "in", ["out_invoice", "in_invoice"]),
                    ("create_date", "<=", from_date),
                ],
                order="create_date asc",
                limit=30,
            ):
                items.append({
                    "source": "Account",
                    "type": "Draft " + (
                        "Invoice" if move.move_type == "out_invoice" else "Bill"
                    ),
                    "name": move.name or "Draft",
                    "partner": move.partner_id.name or "",
                    "amount": round(move.amount_total, 2),
                    "currency_symbol": move.currency_id.symbol or "",
                    "date": move.invoice_date.strftime("%Y-%m-%d") if move.invoice_date else "",
                    "id": move.id,
                    "model": "account.move",
                    "approval_status": "draft",
                })

        # Purchase Order approvals
        PO = self.env.get("purchase.order")
        if PO is not None:
            for po in PO.search(
                [("state", "=", "to approve")],
                order="date_order desc",
                limit=50,
            ):
                items.append({
                    "source": "Purchase",
                    "type": "Purchase Order",
                    "name": po.name,
                    "partner": po.partner_id.name or "",
                    "amount": round(po.amount_total, 2),
                    "currency_symbol": po.currency_id.symbol or "",
                    "date": po.date_order.strftime("%Y-%m-%d") if po.date_order else "",
                    "id": po.id,
                    "model": "purchase.order",
                    "approval_status": "to approve",
                })

        return {"count": len(items), "items": items[:40]}

    # ─────────────────────────────────────────────────────────────────────────
    # Widget 5 — Vendor Payment Requests
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _vendor_payment_requests(self):
        items = []
        today_date = datetime.today().date()

        for bill in self.env["account.move"].search(
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
            ],
            order="invoice_date_due asc",
            limit=60,
        ):
            due = bill.invoice_date_due
            items.append({
                "type": "Vendor Bill",
                "name": bill.name,
                "vendor": bill.partner_id.name or "",
                "amount_total": round(bill.amount_total, 2),
                "amount_residual": round(bill.amount_residual, 2),
                "currency_symbol": bill.currency_id.symbol or "",
                "invoice_date": bill.invoice_date.strftime("%Y-%m-%d") if bill.invoice_date else "",
                "due_date": due.strftime("%Y-%m-%d") if due else "",
                "overdue": bool(due and due < today_date),
                "payment_state": bill.payment_state,
                "id": bill.id,
                "model": "account.move",
            })

        # Confirmed POs not yet invoiced
        PO = self.env.get("purchase.order")
        if PO is not None:
            for po in PO.search(
                [("state", "=", "purchase"), ("invoice_status", "=", "to invoice")],
                order="date_approve desc",
                limit=30,
            ):
                items.append({
                    "type": "PO — Awaiting Invoice",
                    "name": po.name,
                    "vendor": po.partner_id.name or "",
                    "amount_total": round(po.amount_total, 2),
                    "amount_residual": round(po.amount_total, 2),
                    "currency_symbol": po.currency_id.symbol or "",
                    "invoice_date": po.date_approve.strftime("%Y-%m-%d") if po.date_approve else "",
                    "due_date": "",
                    "overdue": False,
                    "payment_state": "not_invoiced",
                    "id": po.id,
                    "model": "purchase.order",
                })

        return {"count": len(items), "items": items}

    # ─────────────────────────────────────────────────────────────────────────
    # Summary KPI strip
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _summary_kpis(self):
        today = datetime.today()
        ytd_start = today.replace(month=1, day=1).strftime("%Y-%m-%d")

        rev_moves = self.env["account.move"].search([
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("invoice_date", ">=", ytd_start),
        ])
        ytd_revenue = sum(
            m.amount_total if m.move_type == "out_invoice" else -m.amount_total
            for m in rev_moves
        )

        exp_moves = self.env["account.move"].search([
            ("move_type", "in", ["in_invoice", "in_refund"]),
            ("state", "=", "posted"),
            ("invoice_date", ">=", ytd_start),
        ])
        ytd_expenses = sum(
            m.amount_total if m.move_type == "in_invoice" else -m.amount_total
            for m in exp_moves
        )

        bills = self.env["account.move"].search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
        ])
        payables = sum(b.amount_residual for b in bills)

        inv = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
        ])
        receivables = sum(i.amount_residual for i in inv)

        currency = self.env.company.currency_id
        return {
            "ytd_revenue": round(ytd_revenue, 2),
            "ytd_expenses": round(ytd_expenses, 2),
            "net_profit": round(ytd_revenue - ytd_expenses, 2),
            "outstanding_payables": round(payables, 2),
            "outstanding_receivables": round(receivables, 2),
            "currency_symbol": currency.symbol or "",
        }
