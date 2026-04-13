/** @odoo-module **/
/**
 * BOQ Manager Dashboard — Odoo 19 OWL Component
 *
 * Task 1  — Two separate dashboards: Vendor Manager & Procurement Manager
 * Task 2  — Expandable Trade → Vendor → RFQ tree structure
 * Task 4  — Renamed labels, removed "lines", payment status visibility,
 *            Draft → "Quote Requested" label
 * Task 5  — Multi-company: passes allowed_company_ids in RPC context
 *
 * One component class (BoqManagerDashboard) is registered under TWO action
 * tags.  The dashboard_type ('vendor' | 'supplier') is read from the
 * ir.actions.client context so each menu page gets its own data scope.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatCurrency(value, symbol, position) {
    const formatted = Number(value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    return position === "after" ? `${formatted} ${symbol}` : `${symbol}${formatted}`;
}

function paymentStatusClass(status) {
    const map = {
        paid:       "bg-success",
        in_payment: "bg-info",
        partial:    "bg-warning text-dark",
        not_paid:   "bg-secondary",
    };
    return map[status] || "bg-secondary";
}

function rfqStateClass(state) {
    const map = {
        draft:        "bg-secondary",
        sent:         "bg-primary",
        submitted:    "bg-warning text-dark",
        "to approve": "bg-info",
        purchase:     "bg-success",
        done:         "bg-success",
        cancel:       "bg-danger",
    };
    return map[state] || "bg-secondary";
}

// ═══════════════════════════════════════════════════════════════════════════════
// BoqManagerDashboard — single class, two registrations
// ═══════════════════════════════════════════════════════════════════════════════
export class BoqManagerDashboard extends Component {
    static template = "boq_management_v19.BoqManagerDashboard";
    static props = {
        action:            { type: Object,   optional: true },
        actionId:          { optional: true },
        updateActionState: { type: Function, optional: true },
        className:         { type: String,   optional: true },
        "*":               true,
    };

    setup() {
        this.orm          = useService("orm");
        this.actionSvc    = useService("action");
        this.notification = useService("notification");

        // Determine dashboard type from action context (set in ir.actions.client)
        const ctx = this.props.action?.context || {};
        this.dashboardType = ctx.dashboard_type || "vendor";

        this.state = useState({
            loading:       true,
            error:         null,
            stats:         {},
            tree:          [],          // hierarchical trade→vendor→rfq data
            expandedTrades: {},          // {trade_id: bool}
            expandedVendors: {},         // {vendor_id: bool}
            filterText:    "",
        });

        onWillStart(() => this._loadAll());
    }

    // ── Labels based on dashboard type ──────────────────────────────────
    get dashboardTitle() {
        return this.dashboardType === "vendor"
            ? "Vendor Manager Dashboard"
            : "Procurement Manager Dashboard";
    }

    get dashboardSubtitle() {
        return this.dashboardType === "vendor"
            ? "Trade-wise Vendor RFQ summary — Installation & Services"
            : "Trade-wise Supplier RFQ summary — Supply & Procurement";
    }

    get partnerLabel() {
        return this.dashboardType === "vendor" ? "Vendor" : "Supplier";
    }

    get dashboardIcon() {
        return this.dashboardType === "vendor" ? "fa-industry" : "fa-truck";
    }

    // ── Data loading ─────────────────────────────────────────────────────
    // Task 5 — Multi-company: Odoo's orm service automatically includes
    // allowed_company_ids in the RPC context from the company switcher, so
    // self.env.context.get('allowed_company_ids') on the Python side is
    // populated correctly without any extra work here.
    async _loadAll() {
        try {
            const [stats, tree] = await Promise.all([
                this.orm.call(
                    "boq.boq", "get_dashboard_stats",
                    [], { dashboard_type: this.dashboardType }
                ),
                this.orm.call(
                    "boq.boq", "get_dashboard_tree_data",
                    [], { dashboard_type: this.dashboardType }
                ),
            ]);
            this.state.stats = stats;
            this.state.tree  = tree;
        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading = true;
        this.state.error   = null;
        this.state.expandedTrades  = {};
        this.state.expandedVendors = {};
        await this._loadAll();
    }

    // ── Tree expand/collapse ─────────────────────────────────────────────
    toggleTrade(tradeId) {
        this.state.expandedTrades = {
            ...this.state.expandedTrades,
            [tradeId]: !this.state.expandedTrades[tradeId],
        };
    }

    toggleVendor(vendorId) {
        this.state.expandedVendors = {
            ...this.state.expandedVendors,
            [vendorId]: !this.state.expandedVendors[vendorId],
        };
    }

    isTradeExpanded(tradeId)   { return !!this.state.expandedTrades[tradeId]; }
    isVendorExpanded(vendorId) { return !!this.state.expandedVendors[vendorId]; }

    // ── Filtered tree ────────────────────────────────────────────────────
    get filteredTree() {
        const q = (this.state.filterText || "").toLowerCase().trim();
        if (!q) return this.state.tree;
        return this.state.tree.filter(trade => {
            if ((trade.trade_name || "").toLowerCase().includes(q)) return true;
            return (trade.vendors || []).some(v =>
                (v.vendor_name || "").toLowerCase().includes(q)
            );
        });
    }

    // ── Summary totals ───────────────────────────────────────────────────
    get treeTotals() {
        const tree = this.filteredTree;
        return {
            trades:    tree.length,
            rfqs:      tree.reduce((s, t) => s + (t.rfq_count     || 0), 0),
            pending:   tree.reduce((s, t) => s + (t.pending_count  || 0), 0),
            submitted: tree.reduce((s, t) => s + (t.submitted_count|| 0), 0),
            value:     tree.reduce((s, t) => s + (t.total_value    || 0), 0),
            vendors:   tree.reduce((s, t) => s + (t.vendor_count   || 0), 0),
        };
    }

    // ── Currency helpers ─────────────────────────────────────────────────
    get currencySymbol()   { return this.state.stats.currency_symbol   || "$"; }
    get currencyPosition() { return this.state.stats.currency_position || "before"; }
    fmtCurrency(val) {
        return formatCurrency(val, this.currencySymbol, this.currencyPosition);
    }

    // ── CSS class helpers ────────────────────────────────────────────────
    paymentStatusClass(s)  { return paymentStatusClass(s); }
    rfqStateClass(s)        { return rfqStateClass(s); }

    // ── Navigation ───────────────────────────────────────────────────────
    openAllBoqs() {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      "Bills of Quantities",
            res_model: "boq.boq",
            views:     [[false, "list"], [false, "kanban"], [false, "form"]],
            domain:    [["boq_type", "=", this.dashboardType]],
            target:    "current",
        });
    }

    openRfqs() {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      this.dashboardType === "vendor" ? "Vendor RFQs" : "Supplier RFQs",
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            target:    "current",
        });
    }

    openVendorRfqs(vendorId, vendorName) {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      `RFQs — ${vendorName}`,
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            domain:    [["partner_id", "=", vendorId]],
            target:    "current",
        });
    }

    openTradeRfqs(tradeCode, tradeName) {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      `RFQs — ${tradeName}`,
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            target:    "current",
        });
    }

    openRfq(rfqId) {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      "RFQ",
            res_model: "purchase.order",
            res_id:    rfqId,
            views:     [[false, "form"]],
            target:    "current",
        });
    }

    clearFilter() { this.state.filterText = ""; }
}

// Register under TWO action tags — each menu item points to its own tag
registry.category("actions").add(
    "boq_management_v19.manager_dashboard_action",
    BoqManagerDashboard
);
