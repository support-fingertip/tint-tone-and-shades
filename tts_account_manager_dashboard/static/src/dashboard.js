/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─────────────────────────────────────────────────────────────────────────────
// Root dashboard component
//
// Navigation methods are defined as arrow-function class fields so that `this`
// is always the component instance, regardless of how OWL's template compiler
// calls them (e.g. `() => openRecord(model, id)` in a t-on-click loses the
// regular method's `this` in strict mode — arrow fields prevent that).
// ─────────────────────────────────────────────────────────────────────────────
export class AccountManagerDashboard extends Component {
    static template = "tts_account_manager_dashboard.Dashboard";
    static props = {
        action:            { type: Object,   optional: true },
        actionId:          { optional: true },
        updateActionState: { type: Function, optional: true },
        className:         { type: String,   optional: true },
        "*":               true,
    };

    setup() {
        this.orm           = useService("orm");
        this.actionService = useService("action");
        this.notification  = useService("notification");

        this.state = useState({
            loading: true,
            error:   null,
            revenue:          [],
            overheads:        [],
            officeExpenses:   { categories: [], monthly: [] },
            pendingApprovals: { count: 0, items: [] },
            vendorPayments:   { count: 0, items: [] },
            summary:          {},
        });

        onWillStart(async () => {
            await this._loadData();
        });
    }

    // ── Data loading ──────────────────────────────────────────────────────────
    async _loadData() {
        this.state.loading = true;
        this.state.error   = null;
        try {
            const data = await this.orm.call(
                "tts.account.dashboard",
                "get_dashboard_data",
                [],
                {},
            );
            this.state.revenue          = data.revenue           || [];
            this.state.overheads        = data.overheads         || [];
            this.state.officeExpenses   = data.office_expenses   || { categories: [], monthly: [] };
            this.state.pendingApprovals = data.pending_approvals || { count: 0, items: [] };
            this.state.vendorPayments   = data.vendor_payments   || { count: 0, items: [] };
            this.state.summary          = data.summary           || {};
        } catch (e) {
            this.state.error = e.message || "Failed to load dashboard data. Please refresh.";
        } finally {
            this.state.loading = false;
        }
    }

    // ── Chart helpers ─────────────────────────────────────────────────────────
    _maxOf(arr, key = "amount") {
        const vals = arr.map((d) => Math.abs(d[key] || 0));
        return Math.max(...vals, 1);
    }

    barHeightPct(amount, max) {
        return Math.max((Math.abs(amount) / max) * 100, 1).toFixed(1);
    }

    // ── Number formatting ─────────────────────────────────────────────────────
    fmt(value, decimals = 0) {
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value || 0);
    }
    fmtMoney(value) { return this.fmt(value, 2); }
    fmtK(value) {
        const v = value || 0;
        if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
        if (Math.abs(v) >= 1_000)     return (v / 1_000).toFixed(1) + "K";
        return this.fmt(v, 0);
    }

    // ── Navigation — arrow function class fields (this always bound) ──────────
    // All doAction calls are wrapped in try/catch so a view-loading issue
    // (e.g. a missing field in account.move views) shows a clear notification
    // instead of an unhandled promise rejection.

    openRecord = async (model, id) => {
        try {
            await this.actionService.doAction({
                type:      "ir.actions.act_window",
                res_model: model,
                res_id:    id,
                view_mode: "form",
                views:     [[false, "form"]],
                target:    "current",
            });
        } catch (e) {
            this.notification.add(
                "Could not open record — " + (e.message || "view loading error"),
                { type: "danger", sticky: false },
            );
        }
    };

    openPendingApprovalsList = async () => {
        try {
            await this.actionService.doAction({
                type:      "ir.actions.act_window",
                name:      "Pending Approvals",
                res_model: "account.move",
                view_mode: "list,form",
                views:     [[false, "list"], [false, "form"]],
                domain:    [["approval_state", "=", "pending"]],
                target:    "current",
            });
        } catch (e) {
            this.notification.add(
                "Could not open Pending Approvals — " + (e.message || "view loading error"),
                { type: "danger", sticky: false },
            );
        }
    };

    openVendorBillsList = async () => {
        try {
            await this.actionService.doAction({
                type:      "ir.actions.act_window",
                name:      "Vendor Payment Requests",
                res_model: "account.move",
                view_mode: "list,form",
                views:     [[false, "list"], [false, "form"]],
                domain:    [
                    ["move_type",     "=",  "in_invoice"],
                    ["state",         "=",  "posted"],
                    ["payment_state", "in", ["not_paid", "partial"]],
                ],
                target: "current",
            });
        } catch (e) {
            this.notification.add(
                "Could not open Vendor Payments — " + (e.message || "view loading error"),
                { type: "danger", sticky: false },
            );
        }
    };

    refresh = async () => {
        await this._loadData();
    };

    // ── Computed getters used by the template ─────────────────────────────────
    get maxRevenue()       { return this._maxOf(this.state.revenue); }
    get maxOverheads()     { return this._maxOf(this.state.overheads); }
    get maxOfficeMonthly() { return this._maxOf(this.state.officeExpenses.monthly || []); }

    get netProfitClass() {
        return (this.state.summary.net_profit || 0) >= 0
            ? "tts-kpi-positive"
            : "tts-kpi-negative";
    }

    // Dynamic label: "Net Profit" when ≥ 0, "Net Loss" when < 0
    get netProfitLabel() {
        return (this.state.summary.net_profit || 0) >= 0 ? "Net Profit" : "Net Loss";
    }

    get netProfitIcon() {
        return (this.state.summary.net_profit || 0) >= 0
            ? "fa-trending-up fa-thumbs-up"
            : "fa-exclamation-triangle";
    }

    get overdueCount() {
        return (this.state.vendorPayments.items || []).filter((i) => i.overdue).length;
    }
}

registry
    .category("actions")
    .add("tts_account_manager_dashboard.Dashboard", AccountManagerDashboard);
