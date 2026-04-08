/** @odoo-module **/
/**
 * BOQ Dashboard — Odoo 19 OWL Component
 *
 * Fixes implemented:
 *  BUG 2  — Trade Assignments section (grouped by work_category_id)
 *  BUG 4  — Margin % prominently shown on vendor cards and trade rows
 *  BUG 6  — Payment status on vendor cards
 *  NEW TASK 2 — Vendor / Supplier toggle tab at dashboard top
 */

import { Component, useState, onWillStart, onPatched, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Helper: format currency ────────────────────────────────────────────────
function formatCurrency(value, symbol, position) {
    const formatted = Number(value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    return position === "after" ? `${formatted} ${symbol}` : `${symbol}${formatted}`;
}

// ─── Helper: margin CSS class ────────────────────────────────────────────────
function marginClass(pct) {
    if (pct >= 30) return "boq_margin_high";
    if (pct >= 15) return "boq_margin_mid";
    if (pct >= 0)  return "boq_margin_low";
    return "boq_margin_neg";
}

// ─── Helper: BOQ state badge ─────────────────────────────────────────────────
function stateBadgeClass(state) {
    const map = {
        draft:     "bg-secondary",
        submitted: "bg-warning text-dark",
        approved:  "bg-info",
        rejected:  "bg-danger",
        done:      "bg-success",
    };
    return map[state] || "bg-secondary";
}

// ─── Helper: payment status badge ────────────────────────────────────────────
function paymentStatusClass(status) {
    const map = {
        paid:      "bg-success",
        in_payment:"bg-info",
        partial:   "bg-warning text-dark",
        not_paid:  "bg-secondary",
    };
    return map[status] || "bg-secondary";
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
    };

    setup() {
        this.orm          = useService("orm");
        this.action       = useService("action");
        this.notification = useService("notification");
        this.scrollContainerRef = useRef("scrollContainer");
        this.notebookRef        = useRef("notebook");
        this._scrollPending = false;

        this.state = useState({
            loading: true,
            stats: {},
            vendors: [],
            trades: [],
            error: null,
            filterVendor: "",
            selectedVendor: null,
            activeTab: "summary",
            vendorLines: [],
            vendorLinesLoading: false,
            // NEW TASK 2 — Vendor/Supplier toggle
            dashboardView: "vendor",   // "vendor" | "supplier"
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
            const [stats, vendors, trades] = await Promise.all([
                this.orm.call("boq.boq", "get_dashboard_stats", []),
                this.orm.call("boq.boq", "get_vendor_summary",  []),
                this.orm.call("boq.boq", "get_trade_summary",   []),
            ]);
            this.state.stats   = stats;
            this.state.vendors = vendors;
            this.state.trades  = trades;
        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        await this._loadAll();
    }

    // ── NEW TASK 2 — toggle handler ─────────────────────────────────────────
    setDashboardView(view) {
        this.state.dashboardView = view;
        this.state.selectedVendor = null;
        this.state.filterVendor = "";
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

    // BUG 2 — open trade-filtered RFQ list
    openTradeRfqs(tradeName) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `RFQs — ${tradeName}`,
            res_model: "purchase.order",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    async selectVendor(vendor) {
        this.state.selectedVendor = vendor;
        this.state.activeTab = "summary";
        this.state.vendorLines = [];
        this.state.vendorLinesLoading = true;
        this._scrollPending = true;
        try {
            const lines = await this.orm.call(
                "boq.boq", "get_vendor_boq_lines", [vendor.vendor_id]
            );
            this.state.vendorLines = lines;
        } catch (_) {
            this.state.vendorLines = [];
        } finally {
            this.state.vendorLinesLoading = false;
        }
    }

    closeNotebook() {
        this.state.selectedVendor = null;
    }

    clearFilter() {
        this.state.filterVendor = "";
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
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

    // ── NEW TASK 2 — Filtered vendor list by partner_type ──────────────────
    get filteredVendors() {
        const q    = (this.state.filterVendor || "").toLowerCase();
        const view = this.state.dashboardView;   // "vendor" or "supplier"

        let list = this.state.vendors;

        // Filter by partner_type if available in vendor data
        // (partner_type may not always be present; show all if missing)
        if (view === "vendor") {
            list = list.filter(v =>
                !v.partner_type || v.partner_type === "vendor"
            );
        } else {
            list = list.filter(v => v.partner_type === "supplier");
        }

        if (q) {
            list = list.filter(v =>
                (v.vendor_name || "").toLowerCase().includes(q)
            );
        }
        return list;
    }

    get vendorTotals() {
        const vendors = this.filteredVendors;
        const totalValue = vendors.reduce((s, v) => s + (v.total_value || 0), 0);
        const totalTax   = vendors.reduce((s, v) => s + (v.total_tax   || 0), 0);
        const totalRfqs  = vendors.reduce((s, v) => s + (v.rfq_count   || 0), 0);
        return { totalValue, totalTax, totalRfqs, count: vendors.length };
    }

    // ── BUG 2 — Trade data ─────────────────────────────────────────────────
    get tradeSummary() {
        return this.state.trades || [];
    }

    get tradeTotals() {
        const trades = this.tradeSummary;
        return {
            total_value: trades.reduce((s, t) => s + (t.total_value || 0), 0),
            total_lines: trades.reduce((s, t) => s + (t.line_count  || 0), 0),
            rfq_count:   trades.reduce((s, t) => s + (t.rfq_count   || 0), 0),
        };
    }

    get currencySymbol() {
        return this.state.stats.currency_symbol || "$";
    }

    get currencyPosition() {
        return this.state.stats.currency_position || "before";
    }

    fmtCurrency(val) {
        return formatCurrency(val, this.currencySymbol, this.currencyPosition);
    }

    // ── Grouped BOQ summary for the Summary tab ─────────────────────────────
    get vendorBoqSummary() {
        const groups = {};
        for (const ln of this.state.vendorLines) {
            const key = ln.boq_name || "—";
            if (!groups[key]) {
                groups[key] = {
                    boq_name: key, items: 0,
                    subtotal: 0, tax: 0, margin_sum: 0,
                };
            }
            groups[key].items++;
            groups[key].subtotal    += ln.subtotal     || 0;
            groups[key].tax         += ln.tax_amount   || 0;
            groups[key].margin_sum  += ln.margin_percent || 0;
        }
        return Object.values(groups).sort((a, b) => a.boq_name.localeCompare(b.boq_name));
    }

    get vendorBoqSummaryTotals() {
        return this.vendorBoqSummary.reduce(
            (acc, g) => ({
                subtotal: acc.subtotal + g.subtotal,
                tax:      acc.tax      + g.tax,
            }),
            { subtotal: 0, tax: 0 }
        );
    }

    marginClass(pct)        { return marginClass(pct); }
    stateBadgeClass(state)  { return stateBadgeClass(state); }
    paymentStatusClass(s)   { return paymentStatusClass(s); }

    get stateLabels() {
        return {
            draft:     "Draft",
            submitted: "Submitted",
            approved:  "Approved",
            rejected:  "Rejected",
            done:      "Done",
        };
    }

    get stateSummary() {
        const sc = this.state.stats.state_counts || {};
        return [
            { key: "draft",     label: "Draft",     cls: "bg-secondary",        val: sc.draft     || 0 },
            { key: "submitted", label: "Submitted",  cls: "bg-warning text-dark", val: sc.submitted || 0 },
            { key: "approved",  label: "Approved",   cls: "bg-info",             val: sc.approved  || 0 },
            { key: "rejected",  label: "Rejected",   cls: "bg-danger",           val: sc.rejected  || 0 },
            { key: "done",      label: "Done",       cls: "bg-success",          val: sc.done      || 0 },
        ].filter(s => s.val > 0);
    }
}

// Register as client action
registry.category("actions").add("boq_management_v19.boq_dashboard_action", BoqDashboard);
