/** @odoo-module **/
/**
 * BOQ Dashboard — Odoo 19 OWL Component
 * Task 4: Vendor-wise RFQ summary, margin %, project stage, payment status.
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

// ─── Helper: margin color class ─────────────────────────────────────────────
function marginClass(pct) {
    if (pct >= 30) return "boq_margin_high";
    if (pct >= 15) return "boq_margin_mid";
    if (pct >= 0)  return "boq_margin_low";
    return "boq_margin_neg";
}

// ─── Helper: BOQ state badge ─────────────────────────────────────────────────
function stateBadgeClass(state) {
    const map = {
        draft: "bg-secondary",
        submitted: "bg-warning text-dark",
        approved: "bg-info",
        rejected: "bg-danger",
        done: "bg-success",
    };
    return map[state] || "bg-secondary";
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
            error: null,
            filterVendor: "",
            selectedVendor: null,
            activeTab: "summary",
            vendorLines: [],
            vendorLinesLoading: false,
        });

        onWillStart(() => this._loadAll());
        onPatched(() => {
            if (this._scrollPending && this.notebookRef.el) {
                this._scrollPending = false;
                const notebook  = this.notebookRef.el;
                const container = this.scrollContainerRef.el;
                if (!container) return;
                requestAnimationFrame(() => {
                    // getBoundingClientRect gives viewport-relative coords.
                    // The delta brings the notebook 16 px below the container top.
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
            const [stats, vendors] = await Promise.all([
                this.orm.call("boq.boq", "get_dashboard_stats", []),
                this.orm.call("boq.boq", "get_vendor_summary", []),
            ]);
            this.state.stats   = stats;
            this.state.vendors = vendors;
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

    // ── Navigation helpers ──────────────────────────────────────────────────
    // NOTE: Passing full action objects (with explicit `views`) avoids the
    //       Odoo 19 _preprocessAction bug where string XML-ID resolution can
    //       return an action dict that lacks the `views` property, causing:
    //       TypeError: can't access property "map", action.views is undefined
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

    // ── Computed getters ────────────────────────────────────────────────────
    get filteredVendors() {
        const q = (this.state.filterVendor || "").toLowerCase();
        if (!q) return this.state.vendors;
        return this.state.vendors.filter(v =>
            (v.vendor_name || "").toLowerCase().includes(q)
        );
    }

    get vendorTotals() {
        const vendors = this.filteredVendors;
        const totalValue = vendors.reduce((s, v) => s + (v.total_value || 0), 0);
        const totalTax   = vendors.reduce((s, v) => s + (v.total_tax   || 0), 0);
        const totalRfqs  = vendors.reduce((s, v) => s + (v.rfq_count   || 0), 0);
        return { totalValue, totalTax, totalRfqs, count: vendors.length };
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
                groups[key] = { boq_name: key, items: 0, subtotal: 0, tax: 0 };
            }
            groups[key].items++;
            groups[key].subtotal += ln.subtotal || 0;
            groups[key].tax      += ln.tax_amount || 0;
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

    marginClass(pct) { return marginClass(pct); }
    stateBadgeClass(state) { return stateBadgeClass(state); }

    get stateLabels() {
        return {
            draft: "Draft",
            submitted: "Submitted",
            approved: "Approved",
            rejected: "Rejected",
            done: "Done",
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
