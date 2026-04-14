/** @odoo-module **/
/**
 * BOQ Manager Dashboards — Odoo 19 OWL Components
 * =================================================
 *
 * Architecture: ONE shared base class, TWO registered subclasses.
 * Each subclass gets its own ir.actions.client tag and its own menu
 * item → truly separate pages, not a toggle.
 *
 *  VendorManagerDashboard          → tag: boq_management_v19.vendor_manager_dashboard_action
 *  ProcurementManagerDashboard     → tag: boq_management_v19.procurement_manager_dashboard_action
 *
 * Task 1  — Two fully separate menu pages (different component + tag)
 * Task 1.6— Approval-pending PO section per dashboard
 * Task 2  — Expandable Trade → Vendor → RFQ tree (3 levels)
 * Task 4  — Renamed labels, no "lines", payment badge on vendor row,
 *            Draft → "Quote Requested"
 * Task 5  — Multi-company: orm service auto-includes allowed_company_ids
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Shared helpers ──────────────────────────────────────────────────────────

function formatCurrency(value, symbol, position) {
    const n = Number(value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    return position === "after" ? `${n} ${symbol}` : `${symbol}${n}`;
}

function paymentStatusClass(s) {
    return { paid: "bg-success", in_payment: "bg-info",
             partial: "bg-warning text-dark", not_paid: "bg-secondary" }[s]
        || "bg-secondary";
}

function rfqStateClass(s) {
    return { draft: "bg-secondary", sent: "bg-primary",
             submitted: "bg-warning text-dark", "to approve": "bg-info",
             purchase: "bg-success", done: "bg-success",
             cancel: "bg-danger" }[s]
        || "bg-secondary";
}

function approvalStatusClass(s) {
    return { pending: "bg-secondary", current: "bg-warning text-dark",
             approved: "bg-success", rejected: "bg-danger" }[s]
        || "bg-secondary";
}

// ═══════════════════════════════════════════════════════════════════════════════
//  BASE CLASS — all logic lives here
// ═══════════════════════════════════════════════════════════════════════════════
class BoqManagerDashboardBase extends Component {
    /**
     * Subclasses MUST define:
     *   static DASHBOARD_TYPE = "vendor" | "supplier";
     *   static template       = "boq_management_v19.VendorManagerDashboard"
     *                         | "boq_management_v19.ProcurementManagerDashboard";
     */
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

        this.state = useState({
            loading:          true,
            error:            null,
            stats:            {},
            tree:             [],   // Level 1: trades → Level 2: vendors → Level 3: rfqs
            vendorSummary:    [],   // Flat vendor cards: name, rfq_count, value, margin, payment
            approvalPOs:      [],   // Task 1.6 — POs awaiting approval
            pendingVendors:   [],   // Task 2.5 — Vendors with pending (draft/sent) RFQs
            expandedTrades:   {},   // { trade_id: bool }
            expandedVendors:  {},   // { vendor_id: bool }
            filterText:       "",
        });

        onWillStart(async () => { await this._loadAll(); });
    }

    // ── Dashboard identity ────────────────────────────────────────────────
    get dashboardType()     { return this.constructor.DASHBOARD_TYPE; }
    get isVendorDashboard() { return this.dashboardType === "vendor"; }

    get dashboardTitle() {
        return this.isVendorDashboard
            ? "Vendor Manager Dashboard"
            : "Procurement Manager Dashboard";
    }

    get dashboardSubtitle() {
        return this.isVendorDashboard
            ? "Trade-wise Vendor RFQ summary — Installation & Services"
            : "Trade-wise Supplier RFQ summary — Supply & Procurement";
    }

    get dashboardIcon()  { return this.isVendorDashboard ? "fa-industry" : "fa-truck"; }
    get partnerLabel()   { return this.isVendorDashboard ? "Vendor" : "Supplier"; }
    get dashboardColor() { return this.isVendorDashboard ? "text-primary" : "text-success"; }

    // ── Data loading ──────────────────────────────────────────────────────
    // Task 5: Odoo's orm service automatically includes allowed_company_ids
    // in every RPC context (populated by the company switcher), so
    // self.env.context.get('allowed_company_ids') in Python is always correct.
    async _loadAll() {
        try {
            const dt = this.dashboardType;
            const [stats, tree, vendorSummary, approvalPOs, pendingVendors] = await Promise.all([
                this.orm.call("boq.boq", "get_dashboard_stats",        [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_dashboard_tree_data",    [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_vendor_summary",         [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_approval_pending_pos",   [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_pending_rfq_vendors",    [], { dashboard_type: dt }),
            ]);
            this.state.stats           = stats;
            this.state.tree            = tree;
            this.state.vendorSummary   = vendorSummary;
            this.state.approvalPOs     = approvalPOs;
            this.state.pendingVendors  = pendingVendors;
        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading         = true;
        this.state.error           = null;
        this.state.vendorSummary   = [];
        this.state.pendingVendors  = [];
        this.state.expandedTrades  = {};
        this.state.expandedVendors = {};
        await this._loadAll();
    }

    // ── Tree expand / collapse ────────────────────────────────────────────
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

    isTradeExpanded(id)  { return !!this.state.expandedTrades[id];  }
    isVendorExpanded(id) { return !!this.state.expandedVendors[id]; }

    // ── Computed: filtered tree ───────────────────────────────────────────
    get filteredTree() {
        const q = (this.state.filterText || "").toLowerCase().trim();
        if (!q) return this.state.tree;
        return this.state.tree.filter(trade =>
            (trade.trade_name || "").toLowerCase().includes(q) ||
            (trade.vendors || []).some(v =>
                (v.vendor_name || "").toLowerCase().includes(q)
            )
        );
    }

    // ── Computed: summary totals ──────────────────────────────────────────
    get treeTotals() {
        const t = this.filteredTree;
        return {
            trades:    t.length,
            vendors:   t.reduce((s, r) => s + (r.vendor_count    || 0), 0),
            rfqs:      t.reduce((s, r) => s + (r.rfq_count       || 0), 0),
            pending:   t.reduce((s, r) => s + (r.pending_count   || 0), 0),
            submitted: t.reduce((s, r) => s + (r.submitted_count || 0), 0),
            value:     t.reduce((s, r) => s + (r.total_value     || 0), 0),
        };
    }

    // ── Computed: pending RFQ totals (Task 2.5) ──────────────────────────
    get pendingRfqTotals() {
        const pv = this.state.pendingVendors || [];
        return {
            vendors: pv.length,
            rfqs:    pv.reduce((s, v) => s + (v.rfq_count || 0), 0),
            oldest:  pv.length ? pv[0].oldest_days : 0,  // already sorted desc
        };
    }

    // ── Computed: approval totals ─────────────────────────────────────────
    get approvalTotals() {
        const pos = this.state.approvalPOs || [];
        return {
            count:   pos.length,
            value:   pos.reduce((s, p) => s + (p.amount_total || 0), 0),
            current: pos.filter(p => p.has_current_approver).length,
        };
    }

    // ── Currency helpers ──────────────────────────────────────────────────
    get currencySymbol()   { return this.state.stats.currency_symbol   || "$"; }
    get currencyPosition() { return this.state.stats.currency_position || "before"; }
    fmtCurrency(val) { return formatCurrency(val, this.currencySymbol, this.currencyPosition); }

    // ── CSS helpers ───────────────────────────────────────────────────────
    paymentStatusClass(s)  { return paymentStatusClass(s);  }
    rfqStateClass(s)       { return rfqStateClass(s);       }
    approvalStatusClass(s) { return approvalStatusClass(s); }

    // ── Navigation ────────────────────────────────────────────────────────
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
            name:      this.isVendorDashboard ? "Vendor RFQs" : "Supplier RFQs",
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

    openRfq(rfqId) {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      "Purchase Order",
            res_model: "purchase.order",
            res_id:    rfqId,
            views:     [[false, "form"]],
            target:    "current",
        });
    }

    openApprovalPos() {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      "POs Awaiting Approval",
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            domain:    [["state", "=", "to approve"]],
            target:    "current",
        });
    }

    clearFilter() { this.state.filterText = ""; }

    openVendorContact(vendorId) {
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      "Partner",
            res_model: "res.partner",
            res_id:    vendorId,
            views:     [[false, "form"]],
            target:    "current",
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  VENDOR MANAGER DASHBOARD — separate component, separate action tag
// ═══════════════════════════════════════════════════════════════════════════════
export class VendorManagerDashboard extends BoqManagerDashboardBase {
    static DASHBOARD_TYPE = "vendor";
    static template       = "boq_management_v19.VendorManagerDashboard";
}

// ═══════════════════════════════════════════════════════════════════════════════
//  PROCUREMENT MANAGER DASHBOARD — separate component, separate action tag
// ═══════════════════════════════════════════════════════════════════════════════
export class ProcurementManagerDashboard extends BoqManagerDashboardBase {
    static DASHBOARD_TYPE = "supplier";
    static template       = "boq_management_v19.ProcurementManagerDashboard";
}

// ── Register each under its OWN tag ─────────────────────────────────────────
registry.category("actions").add(
    "boq_management_v19.vendor_manager_dashboard_action",
    VendorManagerDashboard
);
registry.category("actions").add(
    "boq_management_v19.procurement_manager_dashboard_action",
    ProcurementManagerDashboard
);
