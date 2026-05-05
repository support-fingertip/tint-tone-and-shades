/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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

class BoqManagerDashboardBase extends Component {
   
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
            loading:             true,
            error:               null,
            stats:               {},
            tree:                [],
            vendorSummary:       [],
            approvalPOs:         [],
            pendingVendors:      [],
            recentlySubmitted:   [],
            companySummary:      [],
            showRecentPanel:     false,
            expandedTrades:      {},
            expandedVendors:     {},
            expandedRfqs:        {},   
            rfqLineItems:        {},   
            rfqLinesLoading:     {},  
            filterText:          "",
        });

        onWillStart(async () => { await this._loadAll(); });

        this._refreshTimer = null;
        onMounted(() => {
            this._refreshTimer = setInterval(async () => {
                if (!this.state.loading) {
                    await this._loadAll();
                }
            }, 60000);
        });
        onWillUnmount(() => {
            if (this._refreshTimer) {
                clearInterval(this._refreshTimer);
                this._refreshTimer = null;
            }
        });
    }

    get dashboardType()     { return this.constructor.DASHBOARD_TYPE; }
    get isVendorDashboard() { return this.dashboardType === "vendor"; }
    get isHeadDashboard()   { return false; } 

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

    async _loadAll() {
        try {
            const dt = this.dashboardType;
            const [stats, tree, vendorSummary, approvalPOs, pendingVendors, recentlySubmitted] = await Promise.all([
                this.orm.call("boq.boq", "get_dashboard_stats",           [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_dashboard_tree_data",       [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_vendor_summary",            [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_approval_pending_pos",      [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_pending_rfq_vendors",       [], { dashboard_type: dt }),
                this.orm.call("boq.boq", "get_recently_submitted_rfqs",   [], { dashboard_type: dt }),
            ]);
            this.state.stats              = stats;
            this.state.tree               = tree;
            this.state.vendorSummary      = vendorSummary;
            this.state.approvalPOs        = approvalPOs;
            this.state.pendingVendors     = pendingVendors;
            this.state.recentlySubmitted  = recentlySubmitted;
        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading            = true;
        this.state.error              = null;
        this.state.vendorSummary      = [];
        this.state.pendingVendors     = [];
        this.state.recentlySubmitted  = [];
        this.state.expandedTrades     = {};
        this.state.expandedVendors    = {};
        this.state.expandedRfqs       = {};
        this.state.rfqLineItems       = {};
        this.state.rfqLinesLoading    = {};
        await this._loadAll();
    }

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
    isRfqExpanded(id)    { return !!this.state.expandedRfqs[id];    }

    async toggleRfqLines(ev, rfqId) {
        if (ev) ev.stopPropagation();
        if (this.state.expandedRfqs[rfqId]) {
            this.state.expandedRfqs = { ...this.state.expandedRfqs, [rfqId]: false };
            return;
        }
        if (!this.state.rfqLineItems[rfqId]) {
            this.state.rfqLinesLoading = { ...this.state.rfqLinesLoading, [rfqId]: true };
            try {
                const lines = await this.orm.call("boq.boq", "get_rfq_line_items", [rfqId], {});
                this.state.rfqLineItems = { ...this.state.rfqLineItems, [rfqId]: lines };
            } catch (e) {
                this.state.rfqLineItems = { ...this.state.rfqLineItems, [rfqId]: [] };
            } finally {
                this.state.rfqLinesLoading = { ...this.state.rfqLinesLoading, [rfqId]: false };
            }
        }
        this.state.expandedRfqs = { ...this.state.expandedRfqs, [rfqId]: true };
    }

    fmtPercent(val) {
        return (val || 0).toFixed(1) + "%";
    }

    marginClass(pct) {
        if (pct >= 30) return "boq_margin_good";
        if (pct >= 15) return "boq_margin_ok";
        return "boq_margin_low";
    }

    get overallMargin() {
        let custTotal = 0, vendTotal = 0;
        for (const trade of this.filteredTree) {
            custTotal += trade.customer_total    || 0;
            vendTotal += trade.vendor_cost_total || 0;
        }
        if (custTotal > 0 && vendTotal > 0) {
            return ((custTotal - vendTotal) / custTotal * 100).toFixed(1);
        }
        return null;
    }

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

    get pendingRfqTotals() {
        const pv = this.state.pendingVendors || [];
        return {
            vendors: pv.length,
            rfqs:    pv.reduce((s, v) => s + (v.rfq_count || 0), 0),
            oldest:  pv.length ? pv[0].oldest_days : 0,  
        };
    }

    get approvalTotals() {
        const pos = this.state.approvalPOs || [];
        return {
            count:   pos.length,
            value:   pos.reduce((s, p) => s + (p.amount_total || 0), 0),
            current: pos.filter(p => p.has_current_approver).length,
        };
    }

    get currencySymbol()   { return this.state.stats.currency_symbol   || "$"; }
    get currencyPosition() { return this.state.stats.currency_position || "before"; }
    fmtCurrency(val) { return formatCurrency(val, this.currencySymbol, this.currencyPosition); }

    paymentStatusClass(s)  { return paymentStatusClass(s);  }
    rfqStateClass(s)       { return rfqStateClass(s);       }
    approvalStatusClass(s) { return approvalStatusClass(s); }

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
        // Filter the list by partner_type so the count matches the dashboard stats.
        const ptype = this.isVendorDashboard ? "vendor" : "supplier";
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      this.isVendorDashboard ? "Vendor RFQs" : "Supplier RFQs",
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            domain:    [["partner_id.partner_type", "=", ptype]],
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
        // Filter by state AND partner_type so the count matches the dashboard card.
        const ptype = this.isVendorDashboard ? "vendor" : "supplier";
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      "POs Awaiting Approval",
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            domain:    [
                ["state", "=", "to approve"],
                ["partner_id.partner_type", "=", ptype],
            ],
            target:    "current",
        });
    }

    clearFilter() { this.state.filterText = ""; }

    toggleRecentPanel() {
        this.state.showRecentPanel = !this.state.showRecentPanel;
    }

    get iconBoqs()             { return "fa-calculator"; }
    get iconBOQValue()         { return "fa-money"; }
    get iconGrandTotal()       { return "fa-bar-chart"; }
    get iconRfqs()             { return "fa-shopping-cart"; }
    get iconRfqValue()         { return "fa-money"; }
    get iconApprovalCard()     { return "fa-clock-o"; }
    get iconPendingSection()   { return "fa-clock-o"; }
    get iconTradeAnalysis()    { return "fa-bar-chart"; }
    get iconPendingApprovals() { return "fa-clock-o"; }
    get statBoqBg() {
        return this.isVendorDashboard
            ? "bg-primary-subtle text-primary"
            : "bg-success-subtle text-success";
    }

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

async function _loadDashboardData(component) {
    const dt   = component.dashboardType;
    const cids = await component.orm.call(
        "boq.boq", "get_available_companies", [], {}
    ).then(cs => cs.map(c => c.id)).catch(() => null);
    const extra = cids && cids.length ? { company_ids: cids } : {};

    const [stats, tree, vendorSummary, approvalPOs, pendingVendors, recentlySubmitted] =
        await Promise.all([
            component.orm.call("boq.boq", "get_dashboard_stats",         [], { dashboard_type: dt, ...extra }),
            component.orm.call("boq.boq", "get_dashboard_tree_data",     [], { dashboard_type: dt, ...extra }),
            component.orm.call("boq.boq", "get_vendor_summary",          [], { dashboard_type: dt, ...extra }),
            component.orm.call("boq.boq", "get_approval_pending_pos",    [], { dashboard_type: dt, ...extra }),
            component.orm.call("boq.boq", "get_pending_rfq_vendors",     [], { dashboard_type: dt, ...extra }),
            component.orm.call("boq.boq", "get_recently_submitted_rfqs", [], { dashboard_type: dt, ...extra }),
        ]);

    component.state.stats             = stats;
    component.state.tree              = tree;
    component.state.vendorSummary     = vendorSummary;
    component.state.approvalPOs       = approvalPOs;
    component.state.pendingVendors    = pendingVendors;
    component.state.recentlySubmitted = recentlySubmitted;
}

export class VendorManagerDashboard extends BoqManagerDashboardBase {
    static DASHBOARD_TYPE = "vendor";
    static template       = "boq_management_v19.VendorManagerDashboard";

    async _loadAll() {
        try {
            await _loadDashboardData(this);
        } catch (err) {
            this.state.error = err.message || "Failed to load Vendor dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading           = true;
        this.state.error             = null;
        this.state.tree              = [];
        this.state.vendorSummary     = [];
        this.state.approvalPOs       = [];
        this.state.pendingVendors    = [];
        this.state.recentlySubmitted = [];
        this.state.expandedTrades    = {};
        this.state.expandedVendors   = {};
        this.state.expandedRfqs      = {};
        this.state.rfqLineItems      = {};
        this.state.rfqLinesLoading   = {};
        await this._loadAll();
    }
}

export class ProcurementManagerDashboard extends BoqManagerDashboardBase {
    static DASHBOARD_TYPE = "supplier";
    static template       = "boq_management_v19.ProcurementManagerDashboard";

    async _loadAll() {
        try {
            await _loadDashboardData(this);
        } catch (err) {
            this.state.error = err.message || "Failed to load Procurement dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading           = true;
        this.state.error             = null;
        this.state.tree              = [];
        this.state.vendorSummary     = [];
        this.state.approvalPOs       = [];
        this.state.pendingVendors    = [];
        this.state.recentlySubmitted = [];
        this.state.expandedTrades    = {};
        this.state.expandedVendors   = {};
        this.state.expandedRfqs      = {};
        this.state.rfqLineItems      = {};
        this.state.rfqLinesLoading   = {};
        await this._loadAll();
    }
}

export class HeadSupplierDashboard extends BoqManagerDashboardBase {
    static DASHBOARD_TYPE = "supplier";
    static template       = "boq_management_v19.HeadSupplierDashboard";

    get isHeadDashboard()   { return true; }
    get dashboardTitle()    { return "Head of Supplier Dashboard"; }
    get dashboardSubtitle() { return "Consolidated multi-company supplier & procurement view"; }
    get dashboardIcon()     { return "fa-globe"; }
    get partnerLabel()      { return "Supplier"; }
    get dashboardColor()    { return "text-success"; }

    get iconBoqs()             { return "fa-clipboard"; }
    get iconBOQValue()         { return "fa-tag"; }
    get iconGrandTotal()       { return "fa-pie-chart"; }
    get iconRfqs()             { return "fa-inbox"; }
    get iconRfqValue()         { return "fa-credit-card"; }
    get iconApprovalCard()     { return "fa-hourglass-half"; }
    get iconPendingSection()   { return "fa-hourglass-2"; }
    get iconTradeAnalysis()    { return "fa-area-chart"; }
    get iconPendingApprovals() { return "fa-tasks"; }
    get statBoqBg()            { return "bg-info-subtle text-info"; }

    setup() {
        super.setup();
        this.state.availableCompanies   = [];   
        this.state.selectedCompanyIds   = [];  
        this.state.showCompanyDropdown  = false;

        this._closeDropdown = () => { this.state.showCompanyDropdown = false; };
        onMounted(()       => document.addEventListener("click", this._closeDropdown));
        onWillUnmount(()   => document.removeEventListener("click", this._closeDropdown));
    }

    /** Returns the company_ids kwarg to pass to Python, or null for "all". */
    get _filterCompanyIds() {
        return this.state.selectedCompanyIds.length > 0
            ? this.state.selectedCompanyIds
            : null;
    }

    isCompanySelected(cid) {
        return this.state.selectedCompanyIds.length === 0
            || this.state.selectedCompanyIds.includes(cid);
    }

    isCompanyTag(cid) {
        return this.state.selectedCompanyIds.includes(cid);
    }

    toggleCompanyDropdown(ev) {
        if (ev) ev.stopPropagation();
        this.state.showCompanyDropdown = !this.state.showCompanyDropdown;
    }

    async removeCompany(ev, cid) {
        if (ev) ev.stopPropagation();
        const all = this.state.availableCompanies.map(c => c.id);
        const cur = this.state.selectedCompanyIds;
        if (cur.length === 0) {
            this.state.selectedCompanyIds = all.filter(id => id !== cid);
        } else {
            const next = cur.filter(id => id !== cid);
            this.state.selectedCompanyIds = next.length > 0 ? next : [];
        }
        await this._reloadFiltered();
    }

    async toggleCompany(cid) {
        const all   = this.state.availableCompanies.map(c => c.id);
        const cur   = this.state.selectedCompanyIds;

        if (cur.length === 0) {
            this.state.selectedCompanyIds = all.filter(id => id !== cid);
        } else if (cur.includes(cid)) {
            const next = cur.filter(id => id !== cid);
            this.state.selectedCompanyIds = next.length > 0 ? next : [];
        } else {
            const next = [...cur, cid];
            this.state.selectedCompanyIds = next.length === all.length ? [] : next;
        }
        await this._reloadFiltered();
    }

    async selectAllCompanies(ev) {
        if (ev) ev.stopPropagation();
        this.state.showCompanyDropdown = false;
        this.state.selectedCompanyIds  = [];
        await this._reloadFiltered();
    }

    async _reloadFiltered() {
        this.state.loading         = true;
        this.state.expandedTrades  = {};
        this.state.expandedVendors = {};
        await this._loadData();
    }

    get headTotalCompanies()  { return this.state.companySummary.length; }
    get headTotalSuppliers()  {
        return this.state.vendorSummary ? this.state.vendorSummary.length : 0;
    }
    get headPendingApprovals()   { return this.state.approvalPOs ? this.state.approvalPOs.length : 0; }
    get headRecentlySubmitted()  { return this.state.recentlySubmitted ? this.state.recentlySubmitted.length : 0; }
    get headPendingRfqs() {
        return (this.state.pendingVendors || []).reduce((s, v) => s + (v.rfq_count || 0), 0);
    }
    get headTotalValue() { return this.state.stats ? (this.state.stats.rfq_total_value || 0) : 0; }

    /** First load available companies (once), then data. */
    async _loadAll() {
        try {
            if (this.state.availableCompanies.length === 0) {
                const companies = await this.orm.call(
                    "boq.boq", "get_available_companies", [], {}
                ).catch(() => []);
                this.state.availableCompanies = companies;
            }
            await this._loadData();
        } catch (err) {
            this.state.error   = err.message || "Failed to load dashboard data.";
            this.state.loading = false;
        }
    }

    async _loadData() {
        try {
            const dt  = this.dashboardType;
            const cids = this._filterCompanyIds;  
            const allCids = this.state.availableCompanies.map(c => c.id);
            const companyCids = cids || (allCids.length > 0 ? allCids : null);
            const extra = companyCids ? { company_ids: companyCids } : {};

            const [r0, r1, r2, r3, r4, r5, r6] = await Promise.allSettled([
                this.orm.call("boq.boq", "get_dashboard_stats",          [], { dashboard_type: dt, ...extra }),
                this.orm.call("boq.boq", "get_dashboard_tree_data",      [], { dashboard_type: dt, ...extra }),
                this.orm.call("boq.boq", "get_vendor_summary",           [], { dashboard_type: dt, ...extra }),
                this.orm.call("boq.boq", "get_approval_pending_pos",     [], { dashboard_type: dt, ...extra }),
                this.orm.call("boq.boq", "get_pending_rfq_vendors",      [], { dashboard_type: dt, ...extra }),
                this.orm.call("boq.boq", "get_recently_submitted_rfqs",  [], { dashboard_type: dt, ...extra }),
                this.orm.call("boq.boq", "get_company_wise_summary",     [], { dashboard_type: dt, ...extra }),
            ]);

            if (r0.status === "rejected" && r1.status === "rejected") {
                this.state.error = r0.reason?.message || "Failed to load dashboard data.";
                return;
            }

            if (r0.status === "fulfilled") this.state.stats             = r0.value;
            if (r1.status === "fulfilled") this.state.tree              = r1.value;
            if (r2.status === "fulfilled") this.state.vendorSummary     = r2.value;
            if (r3.status === "fulfilled") this.state.approvalPOs       = r3.value;
            if (r4.status === "fulfilled") this.state.pendingVendors    = r4.value;
            if (r5.status === "fulfilled") this.state.recentlySubmitted = r5.value;
            if (r6.status === "fulfilled") this.state.companySummary    = r6.value;

        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading            = true;
        this.state.error              = null;
        this.state.vendorSummary      = [];
        this.state.pendingVendors     = [];
        this.state.recentlySubmitted  = [];
        this.state.companySummary     = [];
        this.state.availableCompanies = [];
        this.state.selectedCompanyIds = [];
        this.state.expandedTrades     = {};
        this.state.expandedVendors    = {};
        this.state.expandedRfqs       = {};
        this.state.rfqLineItems       = {};
        this.state.rfqLinesLoading    = {};
        await this._loadAll();
    }

    openCompanyRfqs(companyId, companyName) {
        // Filter by company AND supplier partner_type to match dashboard numbers.
        this.actionSvc.doAction({
            type:      "ir.actions.act_window",
            name:      `RFQs — ${companyName}`,
            res_model: "purchase.order",
            views:     [[false, "list"], [false, "form"]],
            domain:    [
                ["company_id", "=", companyId],
                ["partner_id.partner_type", "=", "supplier"],
            ],
            target:    "current",
        });
    }
}

registry.category("actions").add(
    "boq_management_v19.vendor_manager_dashboard_action",
    VendorManagerDashboard
);
registry.category("actions").add(
    "boq_management_v19.procurement_manager_dashboard_action",
    ProcurementManagerDashboard
);
registry.category("actions").add(
    "boq_management_v19.head_supplier_dashboard_action",
    HeadSupplierDashboard
);
