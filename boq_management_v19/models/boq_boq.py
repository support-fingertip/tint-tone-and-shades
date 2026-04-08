# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import format_date


# ── Predefined category codes (must match seeded data) ───────────────────────
_CATEGORY_CODES = ['electrical', 'civil', 'lighting', 'plumbing', 'hvac', 'finishing']


class BoqBoq(models.Model):
    """
    Main BOQ (Bill of Quantities) record.

    Key design: `category_ids` (Many2many) drives which notebook tabs
    are visible. A boolean compute field per category is evaluated
    by the view's `invisible` attribute — this is the cleanest approach
    that works in Odoo 19 without JavaScript patches.
    """
    _name = 'boq.boq'
    _description = 'Bill of Quantities'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'
    _rec_name = 'name'
    _check_company_auto = True

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
    )

    # ── Customer / Project ────────────────────────────────────────────────
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
        domain=[('is_company', '=', True)],
    )
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string='Site Contact',
        domain="[('parent_id', '=', partner_id)]",
    )
    # project_id: non-stored computed — uses project_name (existing column) as
    # backing storage so no new DB column is ever required on boq_boq.
    project_id = fields.Many2one(
        comodel_name='project.project',
        string='Project',
        compute='_compute_project_id',
        inverse='_inverse_project_id',
        store=False,
        help='Link this BOQ to an existing Odoo Project. '
             'The project name is persisted in the Project Name field.',
    )
    project_name = fields.Char(
        string='Project Name',
        tracking=True,
    )
    project_location = fields.Char(string='Site / Location')
    date = fields.Date(
        string='BOQ Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    validity_date = fields.Date(string='Valid Until')
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )

    # ── Status ────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft',     'Draft'),
            ('submitted', 'Submitted'),
            ('approved',  'Approved'),
            ('rejected',  'Rejected'),
            ('done',      'Done'),
        ],
        string='Status',
        default='draft',
        copy=False,
        tracking=True,
        index=True,
    )
    priority = fields.Selection(
        selection=[('0', 'Normal'), ('1', 'Urgent')],
        string='Priority',
        default='0',
    )
    notes = fields.Html(
        string='Terms & Notes',
        sanitize_overridable=True,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY VISIBILITY CONTROL
    # category_ids drives which notebook tabs appear.
    # One boolean compute field per category enables `invisible` in views.
    # ═══════════════════════════════════════════════════════════════════════
    category_ids = fields.Many2many(
        comodel_name='boq.category',
        relation='boq_boq_category_rel',
        column1='boq_id',
        column2='category_id',
        string='Work Categories',
        help='Select work categories to activate their tabs below. '
             'Unselected categories will be hidden.',
    )

    # Boolean visibility flags (non-stored computes, evaluated in view)
    show_electrical = fields.Boolean(compute='_compute_tab_flags')
    show_civil      = fields.Boolean(compute='_compute_tab_flags')
    show_lighting   = fields.Boolean(compute='_compute_tab_flags')
    show_plumbing   = fields.Boolean(compute='_compute_tab_flags')
    show_hvac       = fields.Boolean(compute='_compute_tab_flags')
    show_finishing  = fields.Boolean(compute='_compute_tab_flags')

    # Per-category reference fields used in view context for default_category_id
    electrical_category_id = fields.Many2one('boq.category', compute='_compute_category_refs')
    civil_category_id      = fields.Many2one('boq.category', compute='_compute_category_refs')
    lighting_category_id   = fields.Many2one('boq.category', compute='_compute_category_refs')
    plumbing_category_id   = fields.Many2one('boq.category', compute='_compute_category_refs')
    hvac_category_id       = fields.Many2one('boq.category', compute='_compute_category_refs')
    finishing_category_id  = fields.Many2one('boq.category', compute='_compute_category_refs')

    # ═══════════════════════════════════════════════════════════════════════
    # TRADE-LEVEL VENDOR SELECTION
    # Vendors selected at trade/category level — ALL items in the trade go
    # to these vendors.  Multiple vendors per trade = comparative quotes.
    # Drives action_create_rfq (takes priority over line-level vendor_ids).
    # ═══════════════════════════════════════════════════════════════════════
    electrical_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_boq_electrical_vendor_rel',
        column1='boq_id',
        column2='vendor_id',
        string='Electrical Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors for ALL Electrical items. Add 2+ for comparative quotes.',
    )
    civil_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_boq_civil_vendor_rel',
        column1='boq_id',
        column2='vendor_id',
        string='Civil Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors for ALL Civil items. Add 2+ for comparative quotes.',
    )
    lighting_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_boq_lighting_vendor_rel',
        column1='boq_id',
        column2='vendor_id',
        string='Lighting Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors for ALL Lighting items. Add 2+ for comparative quotes.',
    )
    plumbing_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_boq_plumbing_vendor_rel',
        column1='boq_id',
        column2='vendor_id',
        string='Plumbing Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors for ALL Plumbing items. Add 2+ for comparative quotes.',
    )
    hvac_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_boq_hvac_vendor_rel',
        column1='boq_id',
        column2='vendor_id',
        string='HVAC Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors for ALL HVAC items. Add 2+ for comparative quotes.',
    )
    finishing_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_boq_finishing_vendor_rel',
        column1='boq_id',
        column2='vendor_id',
        string='Finishing Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Vendors for ALL Finishing items. Add 2+ for comparative quotes.',
    )

    @api.depends('project_name')
    def _compute_project_id(self):
        Project = self.env['project.project']
        for rec in self:
            if rec.project_name:
                rec.project_id = Project.search(
                    [('name', '=', rec.project_name)], limit=1
                )
            else:
                rec.project_id = False

    def _inverse_project_id(self):
        for rec in self:
            if rec.project_id:
                rec.project_name = rec.project_id.name

    @api.depends('category_ids')
    def _compute_tab_flags(self):
        for rec in self:
            codes = set(rec.category_ids.mapped('code'))
            rec.show_electrical = 'electrical' in codes
            rec.show_civil      = 'civil'      in codes
            rec.show_lighting   = 'lighting'   in codes
            rec.show_plumbing   = 'plumbing'   in codes
            rec.show_hvac       = 'hvac'       in codes
            rec.show_finishing  = 'finishing'  in codes

    def _compute_category_refs(self):
        cats = {c.code: c for c in self.env['boq.category'].search([])}
        empty = self.env['boq.category']
        for rec in self:
            rec.electrical_category_id = cats.get('electrical', empty)
            rec.civil_category_id      = cats.get('civil',      empty)
            rec.lighting_category_id   = cats.get('lighting',   empty)
            rec.plumbing_category_id   = cats.get('plumbing',   empty)
            rec.hvac_category_id       = cats.get('hvac',       empty)
            rec.finishing_category_id  = cats.get('finishing',  empty)

    # ═══════════════════════════════════════════════════════════════════════
    # ORDER LINES — one domain-filtered O2M per category tab
    # ═══════════════════════════════════════════════════════════════════════
    line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='All Lines',
        copy=True,
    )
    electrical_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'electrical')],
        string='Electrical Lines',
    )
    civil_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'civil')],
        string='Civil Lines',
    )
    lighting_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'lighting')],
        string='Lighting Lines',
    )
    plumbing_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'plumbing')],
        string='Plumbing Lines',
    )
    hvac_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'hvac')],
        string='HVAC Lines',
    )
    finishing_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'finishing')],
        string='Finishing Lines',
    )

    # ── Totals ────────────────────────────────────────────────────────────
    electrical_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    civil_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    lighting_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    plumbing_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    hvac_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    finishing_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Untaxed Amount',
        compute='_compute_totals',
        store=False,
        currency_field='currency_id',
    )
    total_tax = fields.Monetary(
        string='Total Tax',
        compute='_compute_totals',
        store=False,
        currency_field='currency_id',
    )
    grand_total = fields.Monetary(
        string='Grand Total',
        compute='_compute_totals',
        store=False,
        currency_field='currency_id',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_totals',
        store=False,
    )

    # ── Linked Purchase RFQs ──────────────────────────────────────────────
    rfq_ids = fields.Many2many(
        comodel_name='purchase.order',
        relation='boq_boq_purchase_order_rel',
        column1='boq_id',
        column2='purchase_id',
        string='RFQs / Purchase Orders',
        copy=False,
    )
    rfq_count = fields.Integer(
        string='RFQs',
        compute='_compute_rfq_count',
        store=True,
    )

    @api.depends('rfq_ids')
    def _compute_rfq_count(self):
        for rec in self:
            rec.rfq_count = len(rec.rfq_ids)

    # ── _compute_totals ────────────────────────────────────────────────────
    # IMPORTANT: Only depend on stored `line_ids.*` fields.
    # tax_amount on boq.order.line is store=False — using a non-stored computed
    # field in @api.depends causes Odoo ORM to silently drop ALL triggers in the
    # decorator, making every total show 0.  We therefore compute taxes inline
    # here using tax_ids.compute_all() directly, mirroring _compute_total_value
    # on the line, so no non-stored field is ever accessed through mapped().
    @api.depends('line_ids.subtotal', 'line_ids.tax_ids', 'line_ids.qty',
                 'line_ids.unit_price', 'line_ids.discount', 'line_ids.category_id',
                 'partner_id')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids

            def cat_sum(code):
                return sum(
                    l.subtotal for l in lines
                    if l.category_id and l.category_id.code == code
                )

            rec.electrical_total = cat_sum('electrical')
            rec.civil_total      = cat_sum('civil')
            rec.lighting_total   = cat_sum('lighting')
            rec.plumbing_total   = cat_sum('plumbing')
            rec.hvac_total       = cat_sum('hvac')
            rec.finishing_total  = cat_sum('finishing')

            subtotal = sum(lines.mapped('subtotal'))

            # ── Compute taxes inline (avoid non-stored tax_amount) ──────
            # Mirrors _compute_total_value logic on boq.order.line.
            tax_total = 0.0
            for line in lines:
                if line.tax_ids and (line.qty or line.unit_price):
                    price_after_disc = line.unit_price * (
                        1.0 - (line.discount or 0.0) / 100.0
                    )
                    taxes = line.tax_ids.compute_all(
                        price_after_disc,
                        currency=line.currency_id or None,
                        quantity=line.qty,
                        product=line.product_id or None,
                        partner=rec.partner_id or None,
                    )
                    tax_total += (
                        taxes['total_included'] - taxes['total_excluded']
                    )

            rec.total_amount = subtotal
            rec.total_tax    = tax_total
            rec.grand_total  = subtotal + tax_total
            rec.line_count   = len(lines)

    # ── Sequence / Create ─────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('boq.boq') or 'New'
                )
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = 'New'
        return super().copy(default)

    # ── Workflow actions ──────────────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Cannot submit a BOQ with no lines.'))
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ── Smart button: open all lines ──────────────────────────────────────
    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ Lines — %s') % self.name,
            'res_model': 'boq.order.line',
            'view_mode': 'list,form',
            'domain': [('boq_id', '=', self.id)],
            'context': {'default_boq_id': self.id},
        }

    # ── Create RFQ ────────────────────────────────────────────────────────
    def action_create_rfq(self):
        """
        Group BOQ lines by vendor and create one RFQ (purchase.order)
        per vendor. Lines with no vendor are skipped.
        After creation, opens the resulting RFQ(s).
        """
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('Cannot create RFQ: the BOQ has no line items.'))

        # Trade-level vendor field map
        _TRADE_VENDOR_FIELDS = {
            'electrical': 'electrical_vendor_ids',
            'civil':      'civil_vendor_ids',
            'lighting':   'lighting_vendor_ids',
            'plumbing':   'plumbing_vendor_ids',
            'hvac':       'hvac_vendor_ids',
            'finishing':  'finishing_vendor_ids',
        }

        # Build vendor → lines mapping
        # Trade-level vendors take priority; fall back to line-level vendor_ids
        vendor_lines = {}
        for line in self.line_ids:
            cat_code   = line.category_id.code if line.category_id else None
            trade_fld  = _TRADE_VENDOR_FIELDS.get(cat_code) if cat_code else None
            vendors    = getattr(self, trade_fld) if trade_fld else self.env['res.partner']
            if not vendors:          # fallback: line-level vendor_ids
                vendors = line.vendor_ids
            for vendor in vendors:
                vendor_lines.setdefault(vendor.id, []).append(line)

        if not vendor_lines:
            raise UserError(_(
                'No vendors assigned to any trade.\n'
                'Please select vendors at the trade level in each category tab.\n'
                'Add at least 2 vendors per trade to get comparative quotes.'
            ))

        PO = self.env['purchase.order']
        POLine = self.env['purchase.order.line']
        today = fields.Datetime.now()
        created_orders = PO

        for vendor_id, lines in vendor_lines.items():
            po = PO.create({
                'partner_id': vendor_id,
                'origin': '%s — %s' % (self.name, self.project_name or '-'),
            })
            for line in lines:
                POLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.product_name or line.product_id.display_name,
                    'product_qty': line.qty,
                    'product_uom_id': line.uom_id.id or line.product_id.uom_po_id.id,
                    'price_unit': 0,
                    'date_planned': today,
                })
            created_orders |= po

        # Link newly created RFQs to this BOQ
        self.rfq_ids = [(4, po.id) for po in created_orders]

        # Notify & redirect
        if len(created_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Request for Quotation'),
                'res_model': 'purchase.order',
                'res_id': created_orders.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('%d RFQs Created') % len(created_orders),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_orders.ids)],
            'target': 'current',
        }

    def action_view_rfqs(self):
        """Open linked RFQs / Purchase Orders from the smart button."""
        self.ensure_one()
        if not self.rfq_count:
            return
        if self.rfq_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('RFQ'),
                'res_model': 'purchase.order',
                'res_id': self.rfq_ids.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQs — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.rfq_ids.ids)],
            'target': 'current',
        }

    # ── Model helper ──────────────────────────────────────────────────────
    @api.model
    def _get_category_id(self, code):
        """Return the ID of the category with the given code."""
        cat = self.env['boq.category'].search(
            [('code', '=', code)], limit=1
        )
        return cat.id if cat else False

    # ═══════════════════════════════════════════════════════════════════════
    # DASHBOARD DATA METHODS  (Task 4)
    # Called via RPC from the BoqDashboard OWL component.
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def get_dashboard_stats(self):
        """
        Return top-level aggregate stats for the BOQ dashboard header cards.
        """
        company_domain = [('company_id', '=', self.env.company.id)]
        boqs = self.search(company_domain)

        # boq_id on purchase.order is non-stored — query M2M table directly
        rfqs = self.env['purchase.order']
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            rfq_ids = [r[0] for r in self.env.cr.fetchall()]
            if rfq_ids:
                rfqs = self.env['purchase.order'].browse(rfq_ids)

        state_counts = {}
        for state, _label in self._fields['state'].selection:
            state_counts[state] = len(boqs.filtered(lambda b, s=state: b.state == s))

        total_value = sum(boqs.mapped('total_amount'))
        total_tax   = sum(boqs.mapped('total_tax'))
        grand_total = sum(boqs.mapped('grand_total'))
        rfq_total = sum(rfqs.mapped('amount_total'))
        rfq_tax = sum(rfqs.mapped('amount_tax'))

        return {
            'total_boqs': len(boqs),
            'total_value': total_value,
            'total_tax': total_tax,
            'grand_total': grand_total,
            'state_counts': state_counts,
            'total_rfqs': len(rfqs),
            'rfq_draft': len(rfqs.filtered(lambda r: r.state in ('draft', 'sent'))),
            'rfq_total_value': rfq_total,
            'rfq_total_tax': rfq_tax,
            'currency_symbol': self.env.company.currency_id.symbol or '$',
            'currency_position': self.env.company.currency_id.position or 'before',
        }

    @api.model
    def get_dashboard_alerts(self):
        """
        Return two alert lists for the dashboard Reports section:
          done_no_rfq — BOQs in 'done' state with zero RFQs created
          pending_pos — BOQs that have at least one RFQ still in draft/sent
                        (purchase order not yet confirmed)
        """
        company_domain = [('company_id', '=', self.env.company.id)]

        # ── 1. Done BOQs with no RFQ ─────────────────────────────────────
        done_boqs = self.search(company_domain + [('state', '=', 'done')])
        done_no_rfq = []
        for boq in done_boqs.filtered(lambda b: not b.rfq_ids):
            done_no_rfq.append({
                'id':      boq.id,
                'name':    boq.name,
                'partner': boq.partner_id.name if boq.partner_id else '—',
                'project': boq.project_name or '—',
                'date':    boq.date.strftime('%d/%m/%Y') if boq.date else '—',
                'total':   boq.grand_total,
            })

        # ── 2. BOQs with unconfirmed POs (draft / sent) ──────────────────
        pending_pos = []
        all_boqs = self.search(company_domain)
        if all_boqs.ids:
            self.env.cr.execute(
                "SELECT boq_id, purchase_id "
                "FROM boq_boq_purchase_order_rel "
                "WHERE boq_id IN %s",
                (tuple(all_boqs.ids),)
            )
            rows = self.env.cr.fetchall()
            all_po_ids = list({r[1] for r in rows})
            if all_po_ids:
                pending = self.env['purchase.order'].browse(all_po_ids).filtered(
                    lambda p: p.state in ('draft', 'sent')
                )
                pending_set = {p.id for p in pending}
                boq_idx = {b.id: b for b in all_boqs}
                po_idx  = {p.id: p for p in pending}

                for boq_id, po_id in rows:
                    if po_id not in pending_set:
                        continue
                    boq = boq_idx.get(boq_id)
                    po  = po_idx.get(po_id)
                    if not boq or not po:
                        continue
                    pending_pos.append({
                        'boq_id':   boq.id,
                        'boq_name': boq.name,
                        'project':  boq.project_name or '—',
                        'po_id':    po.id,
                        'po_name':  po.name,
                        'vendor':   po.partner_id.name if po.partner_id else '—',
                        'amount':   po.amount_total,
                        'po_state': dict(po._fields['state'].selection).get(po.state, po.state),
                        'date':     po.date_order.strftime('%d/%m/%Y') if po.date_order else '—',
                    })

        return {
            'done_no_rfq': done_no_rfq,
            'pending_pos': pending_pos,
        }

    @api.model
    def get_vendor_summary(self):
        """
        Return vendor-wise RFQ summary for dashboard kanban cards.
        Each entry: vendor name, rfq count, total value, avg margin, project stages,
        payment status.
        """
        company_domain = [('company_id', '=', self.env.company.id)]
        boqs = self.search(company_domain)

        # boq_id on purchase.order is non-stored — query M2M table directly
        # rfq_boq_map: {purchase_id: boq_id}
        rfq_boq_map = {}
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id, boq_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            rfq_boq_map = {row[0]: row[1] for row in self.env.cr.fetchall()}
        rfqs = self.env['purchase.order'].browse(list(rfq_boq_map.keys())) if rfq_boq_map else self.env['purchase.order']

        # Build boq_id → project info map
        boq_info = {
            b.id: {
                'project_name': b.project_name or b.project_id.name or '—',
                'state': b.state,
                'total_amount': b.total_amount,
            }
            for b in boqs
        }

        vendor_map = {}
        for rfq in rfqs:
            vid = rfq.partner_id.id
            if vid not in vendor_map:
                vendor_map[vid] = {
                    'vendor_id': vid,
                    'vendor_name': rfq.partner_id.name,
                    'vendor_email': rfq.partner_id.email or '',
                    'vendor_rating_avg': round(rfq.partner_id.vendor_rating_avg, 2),
                    'vendor_rating_count': rfq.partner_id.vendor_rating_count,
                    'rfq_count': 0,
                    'total_value': 0.0,
                    'total_tax': 0.0,
                    'paid_value': 0.0,
                    'states': [],
                    'project_names': [],
                    'rfq_states': [],
                }
            entry = vendor_map[vid]
            entry['rfq_count'] += 1
            entry['total_value'] += rfq.amount_total
            entry['total_tax'] += rfq.amount_tax

            # Payment status: invoice status on PO
            rfq_state_label = {
                'draft': 'RFQ',
                'sent': 'Sent',
                'to approve': 'To Approve',
                'purchase': 'PO',
                'done': 'Done',
                'cancel': 'Cancelled',
            }.get(rfq.state, rfq.state)
            if rfq_state_label not in entry['rfq_states']:
                entry['rfq_states'].append(rfq_state_label)

            boq_id_val = rfq_boq_map.get(rfq.id)
            if boq_id_val and boq_id_val in boq_info:
                b = boq_info[boq_id_val]
                pname = b['project_name']
                if pname not in entry['project_names']:
                    entry['project_names'].append(pname)
                state = b['state']
                if state not in entry['states']:
                    entry['states'].append(state)

        # Compute margin per vendor using BOQ lines
        vendor_margins = {}
        for boq in boqs:
            for line in boq.line_ids:
                for vendor in line.vendor_ids:
                    vid = vendor.id
                    if vid not in vendor_margins:
                        vendor_margins[vid] = {'total_sell': 0.0, 'total_cost': 0.0}
                    sell = line.unit_price * line.qty * (1.0 - line.discount / 100.0)
                    cost = (line.cost_price or 0.0) * line.qty
                    vendor_margins[vid]['total_sell'] += sell
                    vendor_margins[vid]['total_cost'] += cost

        # Build vendor → trades mapping from trade-level vendor fields
        _TRADE_VENDOR_FLD = {
            'electrical': 'electrical_vendor_ids',
            'civil':      'civil_vendor_ids',
            'lighting':   'lighting_vendor_ids',
            'plumbing':   'plumbing_vendor_ids',
            'hvac':       'hvac_vendor_ids',
            'finishing':  'finishing_vendor_ids',
        }
        vendor_trades = {}
        for boq in boqs:
            for cat_code, fld in _TRADE_VENDOR_FLD.items():
                for vendor in getattr(boq, fld):
                    vendor_trades.setdefault(vendor.id, set()).add(cat_code)

        result = []
        for vid, entry in vendor_map.items():
            margin_data = vendor_margins.get(vid, {'total_sell': 0.0, 'total_cost': 0.0})
            sell = margin_data['total_sell']
            cost = margin_data['total_cost']
            entry['margin_percent'] = round(((sell - cost) / sell * 100) if sell > 0 else 0.0, 2)
            entry['project_names'] = ', '.join(entry['project_names']) or '—'
            entry['rfq_states']    = ', '.join(entry['rfq_states']) or '—'
            entry['boq_states']    = ', '.join(entry['states']) or '—'
            entry['trades']        = sorted(list(vendor_trades.get(vid, set())))
            result.append(entry)

        # Sort by total_value desc
        result.sort(key=lambda x: x['total_value'], reverse=True)
        return result

    @api.model
    def get_vendor_ratings(self, vendor_id):
        """
        Return all PO ratings for the given vendor, used by the dashboard
        Rating tab.
        """
        ratings = self.env['vendor.po.rating'].search([
            ('vendor_id', '=', vendor_id),
        ], order='rating_date desc')

        result = []
        for r in ratings:
            result.append({
                'po_name': r.purchase_order_id.name or '—',
                'rating': r.rating_value,
                'quality': int(r.quality_rating) if r.quality_rating else 0,
                'delivery': int(r.delivery_rating) if r.delivery_rating else 0,
                'pricing': int(r.pricing_rating) if r.pricing_rating else 0,
                'communication': int(r.communication_rating) if r.communication_rating else 0,
                'feedback': r.feedback or '',
                'rated_by': r.rated_by_id.name or '—',
                'rating_date': format_date(self.env, r.rating_date) if r.rating_date else '—',
            })
        return result

    @api.model
    def get_trade_summary(self):
        """
        Return trade-wise (category) value breakdown for the dashboard.
        Each entry: code, label, color, icon, total_value, item_count,
        vendor_count, pct (share of overall BOQ value).
        """
        company_domain = [('company_id', '=', self.env.company.id)]
        boqs = self.search(company_domain)

        _TRADE_INFO = [
            ('electrical', 'Electrical', '#0d6efd', 'fa-bolt'),
            ('civil',      'Civil',      '#6f42c1', 'fa-building'),
            ('lighting',   'Lighting',   '#f29000', 'fa-lightbulb-o'),
            ('plumbing',   'Plumbing',   '#0dcaf0', 'fa-tint'),
            ('hvac',       'HVAC',       '#20c997', 'fa-snowflake-o'),
            ('finishing',  'Finishing',  '#e05929', 'fa-paint-brush'),
        ]
        _TRADE_VENDOR_FLD = {
            'electrical': 'electrical_vendor_ids',
            'civil':      'civil_vendor_ids',
            'lighting':   'lighting_vendor_ids',
            'plumbing':   'plumbing_vendor_ids',
            'hvac':       'hvac_vendor_ids',
            'finishing':  'finishing_vendor_ids',
        }
        _TRADE_TOTAL_FLD = {
            'electrical': 'electrical_total',
            'civil':      'civil_total',
            'lighting':   'lighting_total',
            'plumbing':   'plumbing_total',
            'hvac':       'hvac_total',
            'finishing':  'finishing_total',
        }

        total_overall = sum(b.total_amount for b in boqs) or 1.0

        result = []
        for cat_code, label, color, icon in _TRADE_INFO:
            total_value = sum(getattr(b, _TRADE_TOTAL_FLD[cat_code], 0.0) for b in boqs)
            item_count  = sum(
                len([l for l in b.line_ids
                     if l.category_id and l.category_id.code == cat_code])
                for b in boqs
            )
            vendor_ids = set()
            for b in boqs:
                for v in getattr(b, _TRADE_VENDOR_FLD[cat_code]):
                    vendor_ids.add(v.id)

            result.append({
                'code':         cat_code,
                'label':        label,
                'color':        color,
                'icon':         icon,
                'total_value':  round(total_value, 2),
                'item_count':   item_count,
                'vendor_count': len(vendor_ids),
                'pct':          round(total_value / total_overall * 100, 1),
            })

        result.sort(key=lambda x: x['total_value'], reverse=True)
        return result

    @api.model
    def get_vendor_boq_lines(self, vendor_id):
        """
        Return all BOQ order lines assigned to vendor_id so the dashboard
        Summary tab can show a line-level breakdown (like the BOQ form view).
        """
        partner = self.env['res.partner'].browse(vendor_id)
        if not partner.exists():
            return []

        company_domain = [('company_id', '=', self.env.company.id)]
        boqs = self.search(company_domain)

        rows = []
        for boq in boqs:
            for line in boq.line_ids:
                if partner not in line.vendor_ids:
                    continue
                rows.append({
                    'boq_name':      boq.name or '—',
                    'product_name':  line.product_name or (line.product_id.name if line.product_id else '—'),
                    'qty':           line.qty,
                    'unit_price':    line.unit_price,
                    'cost_price':    line.cost_price,
                    'discount':      line.discount,
                    'subtotal':      line.subtotal,
                    'tax_amount':    line.tax_amount,
                    'total_value':   line.total_value,
                    'margin_percent': round(line.margin_percent, 2),
                })
        return rows
