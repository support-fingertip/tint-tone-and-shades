# -*- coding: utf-8 -*-
from datetime import timedelta

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
    # Approval workflow removed: Draft → Done only.
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done',  'Done'),
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
    # ── BOQ Type: controls which dashboard this BOQ flows into ───────────
    boq_type = fields.Selection(
        selection=[
            ('vendor',   'Vendor (Installation / Services)'),
            ('supplier', 'Supplier (Supply Only)'),
        ],
        string='BOQ Type',
        required=True,
        default='vendor',
        tracking=True,
        help='Vendor BOQs appear on the Vendor Manager Dashboard. '
             'Supplier BOQs appear on the Procurement Manager Dashboard.',
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

    # ── Trade-Level Vendor Assignments ───────────────────────────────────
    trade_vendor_ids = fields.One2many(
        comodel_name='boq.trade.vendor',
        inverse_name='boq_id',
        string='Trade Vendor Assignments',
        copy=True,
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
    )

    @api.depends('rfq_ids')
    def _compute_rfq_count(self):
        user_partner = self.env.user.partner_id
        ptype = user_partner.partner_type
        allowed_companies = self.env.companies.ids  # multi-company support
        for rec in self:
            rfqs = rec.rfq_ids.filtered(lambda r: r.company_id.id in allowed_companies)
            if ptype in ('vendor', 'supplier'):
                rfqs = rfqs.filtered(lambda r: r.partner_id.partner_type == ptype)
            rec.rfq_count = len(rfqs)

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

    # ── Auto-populate trade_vendor_ids when categories are added ─────────
    @api.onchange('category_ids')
    def _onchange_category_ids(self):
        """
        Rebuild trade_vendor_ids so there is exactly one row per unique
        category in category_ids.  Rows for removed categories are kept
        (so the user doesn't lose vendor selections by accident).

        ROOT-CAUSE FIX for the duplication bug (Task 3):
        ─────────────────────────────────────────────────
        Recordset assignment (self.trade_vendor_ids = recordset) only sends
        a diff to the client — it does NOT emit the (5, 0, 0) clear-all
        command.  When the many2many_tags widget fires onchange multiple
        times before the client applies the first response (race condition),
        each call sees trade_vendor_ids = [] on the virtual record and
        independently creates the same rows.  Both deltas reach the client
        and are both applied → duplicate rows.

        The definitive fix uses explicit ORM commands starting with (5,0,0),
        which forces the client to clear ALL rows before applying the new
        list.  This makes the onchange fully idempotent: running it N times
        with the same input always yields exactly one row per category.

        partner_type inherits from boq_type so Supplier BOQs automatically
        produce supplier-typed rows that appear on the Procurement Dashboard.
        """
        default_type = self.boq_type or 'vendor'

        # Snapshot existing rows: preserve vendor/supplier selections and
        # partner_type overrides so they survive the clear-and-rebuild.
        # First occurrence wins if there are already duplicates from a
        # previous save (this handles legacy data gracefully).
        existing = {}
        for row in self.trade_vendor_ids:
            cid = row.category_id.id
            if cid and cid not in existing:
                existing[cid] = {
                    'partner_type': row.partner_type or default_type,
                    'vendor_ids':   [(4, v.id) for v in (row.vendor_ids   or [])],
                    'supplier_ids': [(4, s.id) for s in (row.supplier_ids or [])],
                }

        # (5, 0, 0) — clear all rows on the client before adding new ones.
        # This is the critical command that prevents duplication.
        commands = [(5, 0, 0)]
        seen = set()

        # One (0,0,vals) command per unique selected category
        for cat in self.category_ids:
            if cat.id in seen:
                continue
            seen.add(cat.id)
            d = existing.get(cat.id, {})
            vals = {
                'boq_id':       self._origin.id or False,
                'category_id':  cat.id,
                'partner_type': d.get('partner_type', default_type),
            }
            if d.get('vendor_ids'):
                vals['vendor_ids'] = d['vendor_ids']
            if d.get('supplier_ids'):
                vals['supplier_ids'] = d['supplier_ids']
            commands.append((0, 0, vals))

        # Re-append rows for removed categories so the user doesn't lose
        # their vendor selections by accidentally deselecting a category.
        for cid, d in existing.items():
            if cid not in seen:
                vals = {
                    'boq_id':       self._origin.id or False,
                    'category_id':  cid,
                    'partner_type': d.get('partner_type', default_type),
                }
                if d.get('vendor_ids'):
                    vals['vendor_ids'] = d['vendor_ids']
                if d.get('supplier_ids'):
                    vals['supplier_ids'] = d['supplier_ids']
                commands.append((0, 0, vals))

        self.trade_vendor_ids = commands

    @api.onchange('boq_type')
    def _onchange_boq_type(self):
        """
        When the user changes BOQ type (Vendor ↔ Supplier), update all
        trade assignment rows that still carry the OLD default partner_type
        so the right dashboard picks them up.

        Only rows where partner_type was never manually changed by the user
        (i.e. still matches the previous boq_type default) are updated.
        Rows that were explicitly set to the opposite type are left alone.
        """
        if not self.boq_type:
            return
        for row in self.trade_vendor_ids:
            # Update rows that carry a boq-level default (vendor or supplier)
            # but DON'T touch rows explicitly set to the other type, in case
            # the user intentionally mixed types on a single BOQ.
            if row.partner_type != self.boq_type:
                row.partner_type = self.boq_type

    # ── Sequence / Create / Write ─────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('boq.boq') or 'New'
                )
            # Deduplicate trade_vendor_ids CREATE commands before saving.
            # Concurrent onchange calls (many2many_tags race condition) can
            # produce multiple (0,0,{category_id:X}) commands for the same
            # category.  Filter them here so the DB is always clean.
            if 'trade_vendor_ids' in vals:
                vals['trade_vendor_ids'] = self._dedup_trade_vendor_cmds(
                    vals['trade_vendor_ids']
                )
        return super().create(vals_list)

    def write(self, vals):
        if 'trade_vendor_ids' in vals:
            vals = dict(vals)
            vals['trade_vendor_ids'] = self._dedup_trade_vendor_cmds(
                vals['trade_vendor_ids']
            )
        return super().write(vals)

    @api.model
    def _dedup_trade_vendor_cmds(self, commands):
        """
        Remove duplicate CREATE commands for the same category_id.

        When the many2many_tags widget fires @api.onchange('category_ids')
        multiple times before the first RPC response is applied (race
        condition), the form accumulates one CREATE command per call for the
        same category.  This filter keeps only the FIRST create per category
        so the database always has exactly one row per category regardless of
        how many concurrent onchanges fired.
        """
        seen = set()
        result = []
        for cmd in (commands or []):
            op = cmd[0] if isinstance(cmd, (list, tuple)) else None
            if op == 5:
                seen = set()          # CLEAR resets the dedup window
                result.append(cmd)
            elif op == 0:
                # CREATE — skip if we already queued a create for this category
                cat_id = cmd[2].get('category_id') if isinstance(cmd[2], dict) else None
                if cat_id is None or cat_id not in seen:
                    if cat_id is not None:
                        seen.add(cat_id)
                    result.append(cmd)
                # else: duplicate CREATE — silently drop it
            else:
                result.append(cmd)   # UPDATE, DELETE, LINK, SET — keep as-is
        return result

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = 'New'
        return super().copy(default)

    # ── Workflow actions ──────────────────────────────────────────────────
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
        Create one RFQ (purchase.order) per partner.

        Strategy A (primary) — BOQ Trade assignments (boq.trade.vendor):
          For each row in the "Vendor / Supplier Assignment" section, pick the
          partners (vendor_ids when Type=Vendor, supplier_ids when Type=Supplier).
          All BOQ lines whose category matches that trade row are added to every
          matched partner's RFQ.  Multiple trade rows for the same partner produce
          a single PO containing lines from all those trades.

        Strategy B (fallback) — Line-level vendor_ids:
          If no trade assignments exist, falls back to the Many2many vendor_ids
          on individual BOQ lines.
        """
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('Cannot create RFQ: the BOQ has no line items.'))

        # ── Build partner_id → [line, …] map ─────────────────────────────
        partner_lines = {}   # {partner_id: [boq.order.line, …]}

        if self.trade_vendor_ids:
            # Strategy A: BOQ trade-level assignments
            for trade in self.trade_vendor_ids:
                trade_lines = self.line_ids.filtered(
                    lambda l, cat=trade.category_id: l.category_id == cat
                )
                if not trade_lines:
                    continue
                partners = (
                    trade.vendor_ids
                    if trade.partner_type == 'vendor'
                    else trade.supplier_ids
                )
                for partner in partners:
                    bucket = partner_lines.setdefault(partner.id, [])
                    for line in trade_lines:
                        if line not in bucket:
                            bucket.append(line)

        if not partner_lines:
            # Strategy B: fallback to line-level vendor_ids
            for line in self.line_ids:
                for vendor in line.vendor_ids:
                    bucket = partner_lines.setdefault(vendor.id, [])
                    if line not in bucket:
                        bucket.append(line)

        if not partner_lines:
            raise UserError(_(
                'No vendors / suppliers mapped.\n\n'
                'In the "Vendor / Supplier Assignment" section:\n'
                '1. Select a Trade (work category)\n'
                '2. Set Type to Vendor or Supplier\n'
                '3. Pick the partners in the Vendors / Suppliers field\n'
                '4. Click Create RFQ\n\n'
                'Tip: Work Categories are auto-populated as rows when you '
                'select them at the top of the BOQ form.'
            ))

        # ── Create one PO per partner ─────────────────────────────────────
        PO = self.env['purchase.order']
        POLine = self.env['purchase.order.line']
        today = fields.Datetime.now()
        created_orders = PO

        for partner_id, lines in partner_lines.items():
            po = PO.create({
                'partner_id': partner_id,
                'origin': '%s — %s' % (self.name, self.project_name or '-'),
            })
            for line in lines:
                POLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.product_name or (
                        line.product_id.display_name if line.product_id else '/'
                    ),
                    'product_qty': line.qty,
                    'product_uom_id': (
                        line.uom_id.id
                        or (line.product_id.uom_po_id.id if line.product_id else False)
                    ),
                    'price_unit': 0,
                    'date_planned': today,
                    'customer_price': line.unit_price,
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
        self.ensure_one()
        user_partner = self.env.user.partner_id
        ptype = user_partner.partner_type
        allowed_companies = self.env.companies.ids
        domain = [
            ('id', 'in', self.rfq_ids.ids),
            ('company_id', 'in', allowed_companies),
        ]

        if ptype in ('vendor', 'supplier'):
            domain.append(('partner_id.partner_type', '=', ptype))
        rfqs = self.env['purchase.order'].search(domain)
        if len(rfqs) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': rfqs.id,
                'view_mode': 'form',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQs — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': domain,
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
    # DASHBOARD DATA METHODS  (Tasks 1, 2, 4, 5)
    # Called via RPC from OWL dashboard components.
    # ═══════════════════════════════════════════════════════════════════════

    def _get_allowed_company_ids(self):
        """
        Task 5 — Multi-company support.
        Returns list of company IDs the user is allowed to see.
        Uses allowed_company_ids from context (set by Odoo company switcher).
        Falls back to the current company.
        """
        ctx_ids = self.env.context.get('allowed_company_ids')
        if ctx_ids:
            return list(ctx_ids)
        return [self.env.company.id]

    @staticmethod
    def _vendor_payment_status(rfqs):
        """
        Compute a single payment status string for a list of purchase.order records.
        Returns: 'paid' | 'partial' | 'in_payment' | 'not_paid'
        """
        all_states = []
        for rfq in rfqs:
            for inv in rfq.invoice_ids:
                if inv.payment_state:
                    all_states.append(inv.payment_state)
        if not all_states:
            return 'not_paid'
        if all(s in ('paid', 'in_payment') for s in all_states):
            return 'paid'
        if any(s in ('paid', 'in_payment', 'partial') for s in all_states):
            return 'partial'
        return 'not_paid'

    @api.model
    def get_dashboard_stats(self, dashboard_type='vendor'):
        """
        Return top-level aggregate stats for the BOQ dashboard header cards.
        Task 5: uses allowed_company_ids for multi-company support.
        dashboard_type: 'vendor' | 'supplier'
        """
        company_ids = self._get_allowed_company_ids()
        company_domain = [('company_id', 'in', company_ids), ('boq_type', '=', dashboard_type)]
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
                # Use search (not browse) so Odoo's ir.rules + explicit company
                # filter are both applied — prevents AccessError on company switch.
                rfqs = self.env['purchase.order'].search([
                    ('id', 'in', rfq_ids),
                    ('company_id', 'in', company_ids),
                ])

        state_counts = {
            'draft': len(boqs.filtered(lambda b: b.state == 'draft')),
            'done':  len(boqs.filtered(lambda b: b.state == 'done')),
        }

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
    def get_vendor_summary(self, dashboard_type='vendor'):
        """
        Return vendor-wise RFQ summary for dashboard kanban cards.
        Task 5: uses allowed_company_ids for multi-company support.
        dashboard_type: 'vendor' | 'supplier'
        """
        company_ids = self._get_allowed_company_ids()
        company_domain = [('company_id', 'in', company_ids), ('boq_type', '=', dashboard_type)]
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
        if rfq_boq_map:
            rfqs = self.env['purchase.order'].search([
                ('id', 'in', list(rfq_boq_map.keys())),
                ('company_id', 'in', company_ids),
            ])
            # Narrow the map to only records accessible in the current company context
            found_ids = set(rfqs.ids)
            rfq_boq_map = {k: v for k, v in rfq_boq_map.items() if k in found_ids}
        else:
            rfqs = self.env['purchase.order']

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
                    'partner_type': rfq.partner_id.partner_type or 'vendor',
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

        result = []
        for vid, entry in vendor_map.items():
            margin_data = vendor_margins.get(vid, {'total_sell': 0.0, 'total_cost': 0.0})
            sell = margin_data['total_sell']
            cost = margin_data['total_cost']
            entry['margin_percent'] = round(((sell - cost) / sell * 100) if sell > 0 else 0.0, 2)
            entry['project_names'] = ', '.join(entry['project_names']) or '—'
            entry['rfq_states'] = ', '.join(entry['rfq_states']) or '—'
            entry['boq_states'] = ', '.join(entry['states']) or '—'
            result.append(entry)

        # BUG 6 — Add payment_status from account.move (vendor bills) linked to each PO
        for rfq in rfqs:
            vid = rfq.partner_id.id
            if vid not in vendor_map:
                continue
            entry = vendor_map[vid]
            if 'payment_states' not in entry:
                entry['payment_states'] = []
            for inv in rfq.invoice_ids:
                ps = inv.payment_state or 'not_paid'
                entry['payment_states'].append(ps)

        for vid, entry in vendor_map.items():
            ps_list = entry.pop('payment_states', [])
            if not ps_list:
                entry['payment_status'] = 'not_paid'
                entry['payment_status_label'] = 'Not Paid'
            elif all(s in ('paid', 'in_payment') for s in ps_list):
                entry['payment_status'] = 'paid'
                entry['payment_status_label'] = 'Fully Paid'
            elif any(s in ('paid', 'in_payment', 'partial') for s in ps_list):
                entry['payment_status'] = 'partial'
                entry['payment_status_label'] = 'Partially Paid'
            else:
                entry['payment_status'] = 'not_paid'
                entry['payment_status_label'] = 'Not Paid'

        # Sort by total_value desc
        result.sort(key=lambda x: x['total_value'], reverse=True)
        return result

    @api.model
    def get_trade_summary(self, dashboard_type='vendor'):
        """
        Trade Assignments for the dashboard.
        Group BOQ lines by work_category_id (trade) and sum total_value per trade.
        Task 5: uses allowed_company_ids for multi-company support.
        dashboard_type: 'vendor' | 'supplier'
        """
        company_ids = self._get_allowed_company_ids()
        company_domain = [('company_id', 'in', company_ids), ('boq_type', '=', dashboard_type)]
        boqs = self.search(company_domain)

        # Collect rfq_boq_map for vendor→rfq count per trade
        rfq_boq_map = {}
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id, boq_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            rfq_boq_map = {row[0]: row[1] for row in self.env.cr.fetchall()}

        if rfq_boq_map:
            rfqs = self.env['purchase.order'].search([
                ('id', 'in', list(rfq_boq_map.keys())),
                ('company_id', 'in', company_ids),
            ])
            found_ids = set(rfqs.ids)
            rfq_boq_map = {k: v for k, v in rfq_boq_map.items() if k in found_ids}
        else:
            rfqs = self.env['purchase.order']

        trade_map = {}
        for boq in boqs:
            for line in boq.line_ids:
                if not line.category_id:
                    continue
                cat_id = line.category_id.id
                if cat_id not in trade_map:
                    trade_map[cat_id] = {
                        'trade_id': cat_id,
                        'trade_name': line.category_id.name,
                        'trade_code': line.category_id.code or '',
                        'trade_icon': line.category_id.icon or 'fa-cogs',
                        'total_value': 0.0,
                        'line_count': 0,
                        'vendor_id_set': set(),
                        'vendor_names': [],
                        'boq_ids': set(),
                    }
                entry = trade_map[cat_id]
                entry['total_value'] += line.subtotal
                entry['line_count'] += 1
                entry['boq_ids'].add(boq.id)
                for vendor in line.vendor_ids:
                    if vendor.id not in entry['vendor_id_set']:
                        entry['vendor_id_set'].add(vendor.id)
                        entry['vendor_names'].append(vendor.name or '—')

        # Compute RFQ count per trade: count how many POs have at least one line
        # whose partner is in the trade's vendor set
        rfq_vendor_map = {}  # vendor_id → list of rfq.id
        for rfq in rfqs:
            vid = rfq.partner_id.id
            rfq_vendor_map.setdefault(vid, []).append(rfq.id)

        result = []
        for cat_id, entry in trade_map.items():
            rfq_ids_for_trade = set()
            for vid in entry['vendor_id_set']:
                for rid in rfq_vendor_map.get(vid, []):
                    rfq_ids_for_trade.add(rid)
            entry['rfq_count'] = len(rfq_ids_for_trade)
            entry['vendor_count'] = len(entry['vendor_id_set'])
            entry['vendor_names_str'] = ', '.join(entry['vendor_names']) or '—'
            entry['boq_count'] = len(entry['boq_ids'])
            # Clean up sets (not JSON-serializable)
            del entry['vendor_id_set']
            del entry['vendor_names']
            del entry['boq_ids']
            result.append(entry)

        result.sort(key=lambda x: x['total_value'], reverse=True)
        return result

    # ── NEW Task 2 — Hierarchical Tree Data ───────────────────────────────
    @api.model
    def get_dashboard_tree_data(self, dashboard_type='vendor'):
        """
        Task 2 — Returns a 3-level hierarchical structure:
          Level 1: Trades (Electrical, Civil, Plumbing, …)
          Level 2: Vendors/Suppliers per trade
          Level 3: RFQs per vendor with state breakdown

        Task 5: multi-company using allowed_company_ids.
        dashboard_type: 'vendor' | 'supplier'

        State labels (Task 4.6):
          draft      → 'Quote Requested'  (more meaningful than 'Draft')
          sent       → 'Sent to Vendor'
          submitted  → 'Submitted'
          to approve → 'Awaiting Approval'
          purchase   → 'Approved'
          done       → 'Done'
          cancel     → 'Cancelled'
        """
        RFQ_STATE_LABELS = {
            'draft':      'Quote Requested',
            'sent':       'Sent to Vendor',
            'submitted':  'Submitted',
            'to approve': 'Awaiting Approval',
            'purchase':   'Approved',
            'done':       'Done',
            'cancel':     'Cancelled',
        }
        PENDING_STATES = {'draft', 'sent'}
        recently_cutoff = fields.Datetime.now() - timedelta(days=7)

        company_ids = self._get_allowed_company_ids()
        company_domain = [
            ('company_id', 'in', company_ids),
            ('boq_type',   '=',  dashboard_type),
        ]
        boqs = self.search(company_domain)
        if not boqs:
            return []

        # ── Fetch all RFQs linked to these BOQs ──────────────────────────
        rfq_boq_map = {}   # {rfq_id: boq_id}
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id, boq_id "
                "FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            for row in self.env.cr.fetchall():
                rfq_boq_map[row[0]] = row[1]

        if rfq_boq_map:
            all_rfqs = self.env['purchase.order'].search([
                ('id', 'in', list(rfq_boq_map.keys())),
                ('company_id', 'in', company_ids),
            ])
            # Drop map entries for records inaccessible in the current company context
            found_ids = set(all_rfqs.ids)
            rfq_boq_map = {k: v for k, v in rfq_boq_map.items() if k in found_ids}
        else:
            all_rfqs = self.env['purchase.order']

        # ── Filter RFQs by partner_type matching dashboard_type ──────────
        # 'vendor' dashboard → exclude pure suppliers (partner_type == 'supplier')
        # 'supplier' dashboard → include only partners with type == 'supplier'
        if dashboard_type == 'supplier':
            filtered_rfqs = all_rfqs.filtered(
                lambda r: r.partner_id.partner_type == 'supplier'
            )
        else:
            filtered_rfqs = all_rfqs.filtered(
                lambda r: r.partner_id.partner_type != 'supplier'
            )

        # Build: partner_id → [rfq, …]
        partner_rfq_map = {}
        for rfq in filtered_rfqs:
            partner_rfq_map.setdefault(rfq.partner_id.id, []).append(rfq)

        # ── Build trade → vendor assignments ─────────────────────────────
        # Primary: from boq.trade.vendor rows
        trade_data = {}   # {cat_id: {'category': rec, 'vendors': {vid: partner}}}
        trade_rows = self.env['boq.trade.vendor'].search([
            ('boq_id',       'in', boqs.ids),
            ('partner_type', '=',  dashboard_type),
        ])
        for row in trade_rows:
            cat_id = row.category_id.id
            entry = trade_data.setdefault(cat_id, {
                'category': row.category_id,
                'vendors':  {},
            })
            partners = (
                row.vendor_ids if dashboard_type == 'vendor' else row.supplier_ids
            )
            for p in partners:
                entry['vendors'][p.id] = p

        # Secondary: from line-level vendor_ids (fallback / supplement)
        for boq in boqs:
            for line in boq.line_ids:
                if not line.category_id:
                    continue
                cat_id = line.category_id.id
                entry = trade_data.setdefault(cat_id, {
                    'category': line.category_id,
                    'vendors':  {},
                })
                for vendor in line.vendor_ids:
                    vtype = vendor.partner_type or 'vendor'
                    if dashboard_type == 'supplier':
                        if vtype == 'supplier':
                            entry['vendors'][vendor.id] = vendor
                    else:
                        if vtype != 'supplier':
                            entry['vendors'][vendor.id] = vendor

        # ── Assemble tree ────────────────────────────────────────────────
        tree = []
        for cat_id, cat_data in trade_data.items():
            category = cat_data['category']
            vendors_dict = cat_data['vendors']

            trade_node = {
                'trade_id':       cat_id,
                'trade_name':     category.name,
                'trade_icon':     category.icon or 'fa-cogs',
                'trade_code':     category.code or '',
                'rfq_count':      0,
                'pending_count':  0,
                'submitted_count': 0,
                'total_value':    0.0,
                'vendor_count':   len(vendors_dict),
                'vendors':        [],
            }

            for vid, partner in vendors_dict.items():
                rfqs_for_v = partner_rfq_map.get(vid, [])

                pending_rfqs   = [r for r in rfqs_for_v if r.state in PENDING_STATES]
                submitted_rfqs = [
                    r for r in rfqs_for_v
                    if r.state == 'submitted'
                    and r.write_date and r.write_date >= recently_cutoff
                ]

                # RFQ list — Task 2.4: NO payment info inside vendor-expanded section
                rfq_list = []
                for rfq in rfqs_for_v:
                    rfq_list.append({
                        'rfq_id':     rfq.id,
                        'rfq_name':   rfq.name,
                        'state':      rfq.state,
                        'state_label': RFQ_STATE_LABELS.get(rfq.state, rfq.state),
                        'amount_untaxed': rfq.amount_untaxed,
                        'amount_total':   rfq.amount_total,
                        'is_pending':     rfq.state in PENDING_STATES,
                        'is_recently_submitted': rfq in submitted_rfqs,
                        'date_order': (
                            rfq.date_order.strftime('%d %b %Y')
                            if rfq.date_order else ''
                        ),
                    })

                # Payment status badge at vendor-row level (Task 4.5)
                pay_status = self._vendor_payment_status(rfqs_for_v)
                pay_label  = {
                    'paid':      'Fully Paid',
                    'partial':   'Partially Paid',
                    'in_payment':'In Payment',
                    'not_paid':  'Not Paid',
                }.get(pay_status, 'Not Paid')

                # Task 2.3 — State breakdown summary for vendor expansion header
                # Shows counts per state so users can quickly see Draft/Sent/Submitted/Approved
                _state_counts = {}
                for rfq in rfqs_for_v:
                    _state_counts[rfq.state] = _state_counts.get(rfq.state, 0) + 1
                _state_order = ['draft', 'sent', 'submitted', 'to approve', 'purchase', 'done', 'cancel']
                state_summary = [
                    {
                        'state':       s,
                        'state_label': RFQ_STATE_LABELS.get(s, s),
                        'count':       _state_counts[s],
                    }
                    for s in _state_order if s in _state_counts
                ]

                vendor_node = {
                    'vendor_id':      vid,
                    'vendor_name':    partner.name,
                    'vendor_email':   partner.email or '',
                    'rfq_count':      len(rfqs_for_v),
                    'pending_count':  len(pending_rfqs),
                    'recently_submitted_count': len(submitted_rfqs),
                    'total_value':    sum(r.amount_total for r in rfqs_for_v),
                    'payment_status': pay_status,
                    'payment_status_label': pay_label,
                    'state_summary':  state_summary,
                    'rfqs':           rfq_list,
                }

                trade_node['vendors'].append(vendor_node)
                trade_node['rfq_count']      += vendor_node['rfq_count']
                trade_node['pending_count']  += vendor_node['pending_count']
                trade_node['submitted_count'] += vendor_node['recently_submitted_count']
                trade_node['total_value']    += vendor_node['total_value']

            # Sort vendors: recently-submitted first, then by name
            trade_node['vendors'].sort(
                key=lambda v: (-v['recently_submitted_count'], v['vendor_name'])
            )
            tree.append(trade_node)

        # Sort trades by name
        tree.sort(key=lambda t: t['trade_name'])
        return tree

    # ── Task 2.5 — Pending RFQ vendors (awaiting quotation) ──────────────
    @api.model
    def get_pending_rfq_vendors(self, dashboard_type='vendor'):
        """
        Task 2.5 — Return vendors/suppliers who received RFQs (state draft/sent)
        but have NOT yet submitted a quotation.

        Returns a list of vendors sorted by oldest-pending first, each with:
          - vendor_id, vendor_name, vendor_email
          - rfq_count       total pending RFQs for this vendor
          - oldest_days     days since the oldest pending RFQ was created
          - rfqs            list of pending RFQ details (with trade_name, days_pending)

        dashboard_type: 'vendor' | 'supplier'
        """
        PENDING_STATES = {'draft', 'sent'}
        RFQ_STATE_LABELS = {
            'draft': 'Quote Requested',
            'sent':  'Sent to Vendor',
        }

        company_ids = self._get_allowed_company_ids()
        boqs = self.search([
            ('company_id', 'in', company_ids),
            ('boq_type',   '=',  dashboard_type),
        ])
        if not boqs:
            return []

        # Get all linked RFQ ids
        rfq_boq_map = {}
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id, boq_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            for row in self.env.cr.fetchall():
                rfq_boq_map[row[0]] = row[1]

        if not rfq_boq_map:
            return []

        all_rfqs = self.env['purchase.order'].search([
            ('id', 'in', list(rfq_boq_map.keys())),
            ('company_id', 'in', company_ids),
        ])
        # Drop map entries for records inaccessible in the current company context
        found_ids = set(all_rfqs.ids)
        rfq_boq_map = {k: v for k, v in rfq_boq_map.items() if k in found_ids}

        if not all_rfqs:
            return []


        # Filter to pending states only
        pending_rfqs = all_rfqs.filtered(lambda r: r.state in PENDING_STATES)

        # Filter by partner_type matching dashboard_type
        if dashboard_type == 'supplier':
            pending_rfqs = pending_rfqs.filtered(
                lambda r: r.partner_id.partner_type == 'supplier'
            )
        else:
            pending_rfqs = pending_rfqs.filtered(
                lambda r: r.partner_id.partner_type != 'supplier'
            )

        if not pending_rfqs:
            return []

        # Build bulk trade lookup: (boq_id, partner_id) -> category_name
        trade_vendor_recs = self.env['boq.trade.vendor'].search([
            ('boq_id',       'in', boqs.ids),
            ('partner_type', '=',  dashboard_type),
        ])
        trade_map = {}   # (boq_id, partner_id) -> category_name
        for tv in trade_vendor_recs:
            partners = tv.vendor_ids if dashboard_type == 'vendor' else tv.supplier_ids
            for p in partners:
                key = (tv.boq_id.id, p.id)
                if key not in trade_map:
                    trade_map[key] = tv.category_id.name

        # Group RFQs by vendor
        now = fields.Datetime.now()
        vendor_map = {}
        for rfq in pending_rfqs:
            vid = rfq.partner_id.id
            if vid not in vendor_map:
                vendor_map[vid] = {
                    'vendor_id':   vid,
                    'vendor_name': rfq.partner_id.name,
                    'vendor_email': rfq.partner_id.email or '',
                    'rfq_count':   0,
                    'oldest_days': 0,
                    'rfqs':        [],
                }
            entry = vendor_map[vid]

            days_pending = 0
            if rfq.date_order:
                days_pending = max(0, (now - rfq.date_order).days)

            boq_id = rfq_boq_map.get(rfq.id)
            trade_name = trade_map.get((boq_id, vid), '—') if boq_id else '—'

            entry['rfqs'].append({
                'rfq_id':      rfq.id,
                'rfq_name':    rfq.name,
                'state':       rfq.state,
                'state_label': RFQ_STATE_LABELS.get(rfq.state, rfq.state),
                'date_order':  rfq.date_order.strftime('%d %b %Y') if rfq.date_order else '',
                'amount_total': rfq.amount_total,
                'days_pending': days_pending,
                'trade_name':  trade_name,
            })
            entry['rfq_count'] += 1
            if days_pending > entry['oldest_days']:
                entry['oldest_days'] = days_pending

        result = list(vendor_map.values())
        # Sort: longest-pending first (most urgent at top)
        result.sort(key=lambda x: -x['oldest_days'])
        return result

    # ── Notification banner — Recently submitted quotations ───────────────
    @api.model
    def get_recently_submitted_rfqs(self, dashboard_type='vendor'):
        """
        Returns a flat list of purchase.orders in 'submitted' state
        with write_date in the last 7 days.  Used by the amber notification
        banner at the top of the dashboard.

        Each entry:
          - rfq_id, rfq_name
          - vendor_id, vendor_name, vendor_initial
          - trade_name
          - amount_total
          - days_ago        (0 = today, 1 = yesterday, …)
          - submitted_date  (formatted string)

        Sorted: most recent first (smallest days_ago first).
        """
        company_ids = self._get_allowed_company_ids()
        recently_cutoff = fields.Datetime.now() - timedelta(days=7)

        boqs = self.search([
            ('company_id', 'in', company_ids),
            ('boq_type',   '=',  dashboard_type),
        ])
        if not boqs:
            return []

        # Collect linked RFQ → BOQ mapping
        rfq_boq_map = {}
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id, boq_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            for row in self.env.cr.fetchall():
                rfq_boq_map[row[0]] = row[1]

        if not rfq_boq_map:
            return []

        # Fetch recently submitted — multi-company safe via search()
        submitted_rfqs = self.env['purchase.order'].search([
            ('id',          'in', list(rfq_boq_map.keys())),
            ('company_id',  'in', company_ids),
            ('state',       '=',  'submitted'),
            ('write_date',  '>=', recently_cutoff),
        ])

        if not submitted_rfqs:
            return []

        # Filter by partner_type matching dashboard_type
        if dashboard_type == 'supplier':
            submitted_rfqs = submitted_rfqs.filtered(
                lambda r: r.partner_id.partner_type == 'supplier'
            )
        else:
            submitted_rfqs = submitted_rfqs.filtered(
                lambda r: r.partner_id.partner_type != 'supplier'
            )

        if not submitted_rfqs:
            return []

        # Build trade lookup: (boq_id, partner_id) → category_name
        trade_vendor_recs = self.env['boq.trade.vendor'].search([
            ('boq_id',       'in', boqs.ids),
            ('partner_type', '=',  dashboard_type),
        ])
        trade_map = {}
        for tv in trade_vendor_recs:
            partners = tv.vendor_ids if dashboard_type == 'vendor' else tv.supplier_ids
            for p in partners:
                key = (tv.boq_id.id, p.id)
                if key not in trade_map:
                    trade_map[key] = tv.category_id.name

        now = fields.Datetime.now()
        result = []
        for rfq in submitted_rfqs:
            boq_id    = rfq_boq_map.get(rfq.id)
            trade_name = trade_map.get((boq_id, rfq.partner_id.id), '—') if boq_id else '—'
            days_ago  = max(0, (now - rfq.write_date).days) if rfq.write_date else 0
            result.append({
                'rfq_id':         rfq.id,
                'rfq_name':       rfq.name,
                'vendor_id':      rfq.partner_id.id,
                'vendor_name':    rfq.partner_id.name,
                'vendor_initial': (rfq.partner_id.name or '?')[0].upper(),
                'trade_name':     trade_name,
                'amount_total':   rfq.amount_total,
                'days_ago':       days_ago,
                'submitted_date': rfq.write_date.strftime('%d %b %Y') if rfq.write_date else '',
            })

        # Sort: most recent first
        result.sort(key=lambda r: r['days_ago'])
        return result

    # ── Head of Supplier Dashboard — per-company consolidated summary ─────
    @api.model
    def get_company_wise_summary(self, dashboard_type='supplier'):
        """
        Head of Supplier Dashboard only.

        Returns one record per allowed company showing aggregated BOQ/RFQ
        metrics so the head can see at a glance how each company is
        performing across procurement.

        Each entry:
          - company_id, company_name, company_initial
          - currency_symbol, currency_position
          - total_boqs, total_rfqs, total_value
          - pending_count      (draft / sent — no quote yet)
          - submitted_count    (submitted in last 7 days)
          - approval_pending   (to approve)

        Multi-company safe: uses search() throughout; iterates over
        allowed_company_ids from context.
        """
        company_ids = self._get_allowed_company_ids()
        if not company_ids:
            return []

        recently_cutoff = fields.Datetime.now() - timedelta(days=7)
        PENDING_STATES  = {'draft', 'sent'}

        # ── Fetch all BOQs across allowed companies in one query ──────────
        all_boqs = self.search([
            ('company_id', 'in', company_ids),
            ('boq_type',   '=',  dashboard_type),
        ])
        if not all_boqs:
            return []

        # ── Get all linked RFQ ids via join table ─────────────────────────
        rfq_boq_map = {}
        if all_boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id, boq_id FROM boq_boq_purchase_order_rel "
                "WHERE boq_id IN %s",
                (tuple(all_boqs.ids),)
            )
            for row in self.env.cr.fetchall():
                rfq_boq_map[row[0]] = row[1]

        all_rfqs = self.env['purchase.order']
        if rfq_boq_map:
            all_rfqs = self.env['purchase.order'].search([
                ('id',         'in', list(rfq_boq_map.keys())),
                ('company_id', 'in', company_ids),
            ])
            found_ids  = set(all_rfqs.ids)
            rfq_boq_map = {k: v for k, v in rfq_boq_map.items() if k in found_ids}

        # Filter by partner_type matching dashboard_type
        if dashboard_type == 'supplier':
            all_rfqs = all_rfqs.filtered(
                lambda r: r.partner_id.partner_type == 'supplier'
            )
        else:
            all_rfqs = all_rfqs.filtered(
                lambda r: r.partner_id.partner_type != 'supplier'
            )

        # ── Build per-company records ─────────────────────────────────────
        result = []
        for cid in company_ids:
            company      = self.env['res.company'].browse(cid)
            comp_boqs    = all_boqs.filtered(lambda b: b.company_id.id == cid)
            comp_rfqs    = all_rfqs.filtered(lambda r: r.company_id.id == cid)

            pending_count    = len(comp_rfqs.filtered(
                lambda r: r.state in PENDING_STATES))
            submitted_count  = len(comp_rfqs.filtered(
                lambda r: r.state == 'submitted'
                and r.write_date and r.write_date >= recently_cutoff))
            approval_pending = len(comp_rfqs.filtered(
                lambda r: r.state == 'to approve'))
            total_value      = sum(comp_rfqs.mapped('amount_total'))

            result.append({
                'company_id':        cid,
                'company_name':      company.name,
                'company_initial':   (company.name or '?')[0].upper(),
                'currency_symbol':   company.currency_id.symbol or '',
                'currency_position': company.currency_id.position or 'before',
                'total_boqs':        len(comp_boqs),
                'total_rfqs':        len(comp_rfqs),
                'total_value':       total_value,
                'pending_count':     pending_count,
                'submitted_count':   submitted_count,
                'approval_pending':  approval_pending,
            })

        result.sort(key=lambda c: c['company_name'])
        return result

    # ── NEW Task 1.6 — Approval-pending PO section ────────────────────────
    @api.model
    def get_approval_pending_pos(self, dashboard_type='vendor'):
        """
        Task 1.6 — Return purchase.order records in 'to approve' state that
        are linked to BOQs of the given type (vendor / supplier).

        Each entry includes:
          - po_id, po_name, partner_name, amount_total, currency_symbol
          - approval_lines: list of {level_name, status, approvers}
          - has_current_approver: True when the current user is the next approver
          - date_order

        Used by both Vendor Manager Dashboard and Procurement Manager Dashboard
        to display their respective "Pending Approvals" sections.
        """
        company_ids = self._get_allowed_company_ids()
        company_domain = [
            ('company_id', 'in', company_ids),
            ('boq_type',   '=',  dashboard_type),
        ]
        boqs = self.search(company_domain)
        if not boqs:
            return []

        # Collect all linked RFQ IDs
        rfq_ids = []
        if boqs.ids:
            self.env.cr.execute(
                "SELECT purchase_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                (tuple(boqs.ids),)
            )
            rfq_ids = [r[0] for r in self.env.cr.fetchall()]

        if not rfq_ids:
            return []

        # Use search (not browse) — applies ir.rules + explicit company filter
        # so switching companies never causes an AccessError.
        # The state filter is pushed into the domain for efficiency.
        pending_pos = self.env['purchase.order'].search([
            ('id', 'in', rfq_ids),
            ('company_id', 'in', company_ids),
            ('state', '=', 'to approve'),
        ])

        current_user = self.env.user
        result = []
        for po in pending_pos:
            # Filter by partner_type matching dashboard_type
            vtype = po.partner_id.partner_type or 'vendor'
            if dashboard_type == 'supplier' and vtype != 'supplier':
                continue
            if dashboard_type == 'vendor' and vtype == 'supplier':
                continue

            # Build approval lines list
            # Guard: approval_line_ids only exists when infinys_purchase_order_approval
            # is installed.  Use _fields check so the dashboard works even if that
            # module is absent (approval section simply shows empty progress).
            approval_lines = []
            has_current_approver = False
            approval_line_recs = (
                po.approval_line_ids.sorted('sequence')
                if 'approval_line_ids' in po._fields
                else []
            )
            for al in approval_line_recs:
                approver_names = ', '.join(al.user_ids.mapped('name')) or '—'
                is_current = al.status == 'current'
                if is_current and current_user in al.user_ids:
                    has_current_approver = True
                approval_lines.append({
                    'level_name':    al.level_id.name or '—',
                    'status':        al.status,
                    'status_label':  dict(al._fields['status'].selection).get(al.status, al.status),
                    'approvers':     approver_names,
                    'is_current':    is_current,
                    'is_mine':       is_current and current_user in al.user_ids,
                })

            result.append({
                'po_id':               po.id,
                'po_name':             po.name,
                'partner_name':        po.partner_id.name or '—',
                'amount_total':        po.amount_total,
                'amount_untaxed':      po.amount_untaxed,
                'currency_symbol':     po.currency_id.symbol or '$',
                'date_order':          po.date_order.strftime('%d %b %Y') if po.date_order else '',
                'approval_lines':      approval_lines,
                'has_current_approver': has_current_approver,
                'approval_count':      len(approval_lines),
                'approved_count':      len([a for a in approval_lines if a['status'] == 'approved']),
            })

        # Sort: POs where current user is next approver first, then by amount
        result.sort(key=lambda x: (-x['has_current_approver'], -x['amount_total']))
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

        company_ids = self._get_allowed_company_ids()
        company_domain = [('company_id', 'in', company_ids)]
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


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(string="Cc")

    def action_send_mail(self):
        return super(
            MailComposeMessage,
            self.with_context(custom_email_cc=self.email_cc)
        ).action_send_mail()


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def create(self, vals):
        cc = self.env.context.get('custom_email_cc')
        vals_list = vals if isinstance(vals, list) else [vals]
        for v in vals_list:
            if cc and not v.get('email_cc'):
                v['email_cc'] = cc
        return super().create(vals_list if isinstance(vals, list) else vals_list[0])