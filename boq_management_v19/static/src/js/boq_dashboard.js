/** @odoo-module **/
/**
 * BOQ Dashboard — Odoo 19 OWL Component
 * Trade-wise vendor summary, margin %, project stage, payment status.
 * Enhanced UI with trade overview, coloured bars and reactive vendor cards.
 */

import { Component, useState, onWillStart, onPatched, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Trade metadata ──────────────────────────────────────────────────────────
const TRADE_META = {
    electrical: { label: "Electrical", color: "#0d6efd", bg: "#e7f1ff", icon: "fa-bolt" },
    civil:      { label: "Civil",      color: "#6f42c1", bg: "#f0ebff", icon: "fa-building" },
    lighting:   { label: "Lighting",   color: "#f29000", bg: "#fff3cd", icon: "fa-lightbulb-o" },
    plumbing:   { label: "Plumbing",   color: "#0dcaf0", bg: "#d0f4fd", icon: "fa-tint" },
    hvac:       { label: "HVAC",       color: "#20c997", bg: "#d4f8ee", icon: "fa-snowflake-o" },
    finishing:  { label: "Finishing",  color: "#e05929", bg: "#fce8e2", icon: "fa-paint-brush" },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatCurrency(value, symbol, position) {
    const formatted = Number(value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    return position === "after" ? `${formatted} ${symbol}` : `${symbol}${formatted}`;
}

function marginClass(pct) {
    if (pct >= 30) return "boq_margin_high";
    if (pct >= 15) return "boq_margin_mid";
    if (pct >= 0)  return "boq_margin_low";
    return "boq_margin_neg";
}

function tradeColor(code) {
    return (TRADE_META[code] || {}).color || "#6c757d";
}

function tradeBg(code) {
    return (TRADE_META[code] || {}).bg || "#f8f9fa";
}

function tradeLabel(code) {
    return (TRADE_META[code] || {}).label || code;
}

function tradeIcon(code) {
    return (TRADE_META[code] || {}).icon || "fa-wrench";
}

// ═══════════════════════════════════════════════════════════════════════════════
// BoqDashboard Component
// ═══════════════════════════════════════════════════════════════════════════════
export class BoqDashboard extends Component {
    static template = "boq_management_v19.BoqDashboard";
    static props = {
        action:            { type: Object,   optional: true },
        actionId:          { optional: true },
        updateActionState: { type: Function, optional: true },
        className:         { type: String,   optional: true },
        globalState:       { optional: true }, // passed by Odoo 19 action client
        "*":               true,               // forward-compat: accept any extra props
    };

    setup() {
        this.orm          = useService("orm");
        this.action       = useService("action");
        this.notification = useService("notification");
        this.scrollContainerRef = useRef("scrollContainer");
        this.notebookRef        = useRef("notebook");
        this._scrollPending = false;

        this.state = useState({
            loading:              true,
            stats:                {},
            vendors:              [],
            tradeSummary:         [],
            alerts:               { done_no_rfq: [], pending_pos: [] },
            error:                null,
            filterVendor:         "",
            filterTrade:          "",
            selectedVendor:       null,
            activeTab:            "summary",
            vendorLines:          [],
            vendorLinesLoading:   false,
            vendorRatings:        [],
            vendorRatingsLoading: false,
        });

        onWillStart(() => this._loadAll());
        onPatched(() => {
            if (this._scrollPending && this.notebookRef.el) {
                this._scrollPending = false;
                const notebook  = this.notebookRef.el;
                const container = this.scrollContainerRef.el;
                if (!container) return;
                requestAnimationFrame(() => {
                    const cRect = container.getBoundingClientRect();
                    const nRect = notebook.getBoundingClientRect();
                    container.scrollBy({ top: nRect.top - cRect.top - 16, behavior: "smooth" });
                });
            }
        });
    }

    // ── Data loading ────────────────────────────────────────────────────────
    async _loadAll() {
        try {
            const [stats, vendors, tradeSummary, alerts] = await Promise.all([
                this.orm.call("boq.boq", "get_dashboard_stats", []),
                this.orm.call("boq.boq", "get_vendor_summary", []),
                this.orm.call("boq.boq", "get_trade_summary", []),
                this.orm.call("boq.boq", "get_dashboard_alerts", []),
            ]);
            this.state.stats        = stats;
            this.state.vendors      = vendors;
            this.state.tradeSummary = tradeSummary;
            this.state.alerts       = alerts;
        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading = true;
        this.state.error   = null;
        await this._loadAll();
    }

    // ── Navigation helpers ──────────────────────────────────────────────────
    openAllBoqs() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Bills of Quantities",
            res_model: "boq.boq",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            target: "current",
        });
    }

    openRfqs() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "RFQs from BOQ",
            res_model: "purchase.order",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openBoqForm(boqId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "boq.boq",
            res_id: boqId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPoForm(poId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "purchase.order",
            res_id: poId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async selectVendor(vendor) {
        this.state.selectedVendor       = vendor;
        this.state.activeTab            = "summary";
        this.state.vendorLines          = [];
        this.state.vendorLinesLoading   = true;
        this.state.vendorRatings        = [];
        this.state.vendorRatingsLoading = true;
        this._scrollPending = true;
        try {
            const [lines, ratings] = await Promise.all([
                this.orm.call("boq.boq", "get_vendor_boq_lines", [vendor.vendor_id]),
                this.orm.call("boq.boq", "get_vendor_ratings", [vendor.vendor_id]),
            ]);
            this.state.vendorLines   = lines;
            this.state.vendorRatings = ratings;
        } catch (_) {
            this.state.vendorLines   = [];
            this.state.vendorRatings = [];
        } finally {
            this.state.vendorLinesLoading   = false;
            this.state.vendorRatingsLoading = false;
        }
    }

    closeNotebook() { this.state.selectedVendor = null; }
    clearFilter()   { this.state.filterVendor = ""; }
    clearTradeFilter() { this.state.filterTrade = ""; }
    setActiveTab(tab) { this.state.activeTab = tab; }

    filterByTrade(code) {
        this.state.filterTrade = (this.state.filterTrade === code) ? "" : code;
    }

    openVendorRfqs(vendorId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "RFQs",
            res_model: "purchase.order",
            views: [[false, "list"], [false, "form"]],
            domain: [["partner_id", "=", vendorId]],
            target: "current",
        });
    }

    openVendorRatings(vendorId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Vendor Ratings",
            res_model: "vendor.po.rating",
            views: [[false, "list"], [false, "form"]],
            domain: [["vendor_id", "=", vendorId]],
            target: "current",
        });
    }

    openVendorDashboard() {
        this.action.doAction("boq_management_v19.action_vendor_dashboard");
    }

    // ── Computed getters ────────────────────────────────────────────────────
    get filteredVendors() {
        let list = this.state.vendors;
        const q = (this.state.filterVendor || "").toLowerCase();
        if (q) list = list.filter(v => (v.vendor_name || "").toLowerCase().includes(q));
        const t = this.state.filterTrade;
        if (t) list = list.filter(v => (v.trades || []).includes(t));
        return list;
    }

    get vendorTotals() {
        const vendors    = this.filteredVendors;
        const totalValue = vendors.reduce((s, v) => s + (v.total_value || 0), 0);
        const totalTax   = vendors.reduce((s, v) => s + (v.total_tax   || 0), 0);
        const totalRfqs  = vendors.reduce((s, v) => s + (v.rfq_count   || 0), 0);
        return { totalValue, totalTax, totalRfqs, count: vendors.length };
    }

    get currencySymbol()   { return this.state.stats.currency_symbol   || "$"; }
    get currencyPosition() { return this.state.stats.currency_position || "before"; }

    fmtCurrency(val) {
        return formatCurrency(val, this.currencySymbol, this.currencyPosition);
    }

    // ── Trade helpers (exposed to template) ─────────────────────────────────
    tradeColor(code)  { return tradeColor(code); }
    tradeBg(code)     { return tradeBg(code); }
    tradeLabel(code)  { return tradeLabel(code); }
    tradeIcon(code)   { return tradeIcon(code); }

    // ── Grouped BOQ summary for the Summary tab ─────────────────────────────
    get vendorBoqSummary() {
        const groups = {};
        for (const ln of this.state.vendorLines) {
            const key = ln.boq_name || "—";
            if (!groups[key]) {
                groups[key] = { boq_name: key, items: 0, subtotal: 0, tax: 0 };
            }
            groups[key].items++;
            groups[key].subtotal += ln.subtotal   || 0;
            groups[key].tax      += ln.tax_amount || 0;
        }
        return Object.values(groups).sort((a, b) => a.boq_name.localeCompare(b.boq_name));
    }

    get vendorBoqSummaryTotals() {
        return this.vendorBoqSummary.reduce(
            (acc, g) => ({ subtotal: acc.subtotal + g.subtotal, tax: acc.tax + g.tax }),
            { subtotal: 0, tax: 0 }
        );
    }

    marginClass(pct) { return marginClass(pct); }

    get stateLabels() {
        return { draft: "Draft", submitted: "Submitted", done: "Done" };
    }

    get stateSummary() {
        const sc = this.state.stats.state_counts || {};
        return [
            { key: "draft",     label: "Draft",     cls: "bg-secondary",        val: sc.draft     || 0 },
            { key: "submitted", label: "Submitted",  cls: "bg-warning text-dark", val: sc.submitted || 0 },
            { key: "done",      label: "Done",       cls: "bg-success",          val: sc.done      || 0 },
        ].filter(s => s.val > 0);
    }

    // ── Trades for selected vendor notebook ─────────────────────────────────
    get selectedVendorTrades() {
        const v = this.state.selectedVendor;
        if (!v || !v.trades || !v.trades.length) return [];
        return v.trades.map(code => ({
            code,
            label: tradeLabel(code),
            color: tradeColor(code),
            bg:    tradeBg(code),
            icon:  tradeIcon(code),
        }));
    }
}

// Register as client action
registry.category("actions").add("boq_management_v19.boq_dashboard_action", BoqDashboard);
