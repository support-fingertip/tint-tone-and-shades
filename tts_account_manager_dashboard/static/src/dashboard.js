/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─────────────────────────────────────────────────────────────────────────────
// Root dashboard component — owns all state, fetches data once on mount
// ─────────────────────────────────────────────────────────────────────────────
export class AccountManagerDashboard extends Component {
    static template = "tts_account_manager_dashboard.Dashboard";
    static props = {};

    setup() {
        this.rpc = useService("rpc");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            error: null,
            revenue: [],
            overheads: [],
            officeExpenses: { categories: [], monthly: [] },
            pendingApprovals: { count: 0, items: [] },
            vendorPayments: { count: 0, items: [] },
            summary: {},
        });

        onMounted(async () => {
            await this._loadData();
        });
    }

    async _loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.rpc("/tts/account/dashboard/data", {});
            if (data.error) {
                this.state.error = data.error;
            } else {
                this.state.revenue = data.revenue || [];
                this.state.overheads = data.overheads || [];
                this.state.officeExpenses = data.office_expenses || { categories: [], monthly: [] };
                this.state.pendingApprovals = data.pending_approvals || { count: 0, items: [] };
                this.state.vendorPayments = data.vendor_payments || { count: 0, items: [] };
                this.state.summary = data.summary || {};
            }
        } catch (e) {
            this.state.error = "Failed to load dashboard data. Please refresh.";
        } finally {
            this.state.loading = false;
        }
    }

    // ── Chart helpers ────────────────────────────────────────────────────────

    _maxOf(arr, key = "amount") {
        const vals = arr.map((d) => Math.abs(d[key] || 0));
        return Math.max(...vals, 1);
    }

    barHeightPct(amount, max) {
        const h = (Math.abs(amount) / max) * 100;
        return Math.max(h, 1).toFixed(1);
    }

    // ── Number formatting ────────────────────────────────────────────────────

    fmt(value, decimals = 0) {
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value || 0);
    }

    fmtMoney(value) {
        return this.fmt(value, 2);
    }

    fmtK(value) {
        if (Math.abs(value) >= 1_000_000)
            return (value / 1_000_000).toFixed(1) + "M";
        if (Math.abs(value) >= 1_000)
            return (value / 1_000).toFixed(1) + "K";
        return this.fmt(value, 0);
    }

    // ── Navigation ───────────────────────────────────────────────────────────

    openRecord(model, id) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPendingApprovalsList() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Pending Approvals",
            res_model: "account.move",
            view_mode: "list,form",
            domain: [["approval_state", "=", "pending"]],
            target: "current",
        });
    }

    openVendorBillsList() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Vendor Payment Requests",
            res_model: "account.move",
            view_mode: "list,form",
            domain: [
                ["move_type", "=", "in_invoice"],
                ["state", "=", "posted"],
                ["payment_state", "in", ["not_paid", "partial"]],
            ],
            target: "current",
        });
    }

    async refresh() {
        await this._loadData();
    }

    // ── Computed getters used by template ────────────────────────────────────

    get maxRevenue() { return this._maxOf(this.state.revenue); }
    get maxOverheads() { return this._maxOf(this.state.overheads); }
    get maxOfficeMonthly() { return this._maxOf(this.state.officeExpenses.monthly || []); }

    get netProfitClass() {
        const n = this.state.summary.net_profit || 0;
        return n >= 0 ? "tts-kpi-positive" : "tts-kpi-negative";
    }

    get overdueCount() {
        return (this.state.vendorPayments.items || []).filter((i) => i.overdue).length;
    }
}

registry
    .category("actions")
    .add("tts_account_manager_dashboard.Dashboard", AccountManagerDashboard);
