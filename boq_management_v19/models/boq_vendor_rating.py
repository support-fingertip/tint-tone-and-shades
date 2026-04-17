# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BoqVendorRating(models.Model):
    
    _name = 'boq.vendor.rating'
    _description = 'Vendor Rating'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _rec_name = 'partner_id'

    # ── Relations ────────────────────────────────────────────────────────
    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        required=True,
        index=True,
    )

    # ── Rating ───────────────────────────────────────────────────────────
    rating = fields.Selection(
        selection=[
            ('1', '1 — Poor'),
            ('2', '2 — Below Average'),
            ('3', '3 — Average'),
            ('4', '4 — Good'),
            ('5', '5 — Excellent'),
        ],
        string='Rating',
        required=True,
        default='3',
        tracking=True,
    )
    rating_int = fields.Integer(
        string='Rating (int)',
        compute='_compute_rating_int',
        store=True,
    )

    # ── Details ──────────────────────────────────────────────────────────
    comments = fields.Text(string='Comments / Remarks')
    date = fields.Date(string='Rating Date', default=fields.Date.today)

    # ── Compatibility shim for stale ir.rule ─────────────────────────────
    # A legacy ir.rule on this model has domain_force [('res_model','=',
    # 'res.partner')].  Without this field the ORM raises ValueError on every
    # res.partner read that loads the rating_ids One2many.
    #
    # Adding res_model as a non-stored computed field makes the domain VALID:
    #   • The field always returns 'res.partner' (all ratings belong to partners)
    #   • _search_res_model maps ('res_model','=','res.partner') → [] (no filter)
    #     so the stale rule silently becomes a no-op instead of crashing.
    # No DB column is needed — this fix takes effect on a plain restart (no -u).
    res_model = fields.Char(
        string='Resource Model',
        compute='_compute_res_model',
        search='_search_res_model',
        store=False,
    )

    def _compute_res_model(self):
        for rec in self:
            rec.res_model = 'res.partner'

    def _search_res_model(self, operator, value):
        """Make the stale ir.rule domain a no-op.

        The rule says ('res_model','=','res.partner').  Since all ratings
        belong to res.partner records, the correct answer is 'all records'
        which in Odoo domain syntax is an empty list (no restriction).
        """
        if operator == '=' and value == 'res.partner':
            return []          # no filter → all records visible
        return [('id', '=', 0)]  # any other combination → no records

    # ── Partner type (vendor or supplier) ────────────────────────────────
    partner_type = fields.Selection(
        related='partner_id.partner_type',
        string='Partner Type',
        store=True,
        index=True,
        help='Mirrors the rated partner\'s type (Vendor or Supplier).',
    )

    # ── Context fields (read-only, from PO) ──────────────────────────────
    company_id = fields.Many2one(
        related='purchase_order_id.company_id',
        store=True,
        index=True,
    )

    # ── Constraints ──────────────────────────────────────────────────────
    _unique_po_rating = models.Constraint(
        'unique(purchase_order_id)',
        'A rating already exists for this Purchase Order. Edit the existing rating.',
    )

    @api.depends('rating')
    def _compute_rating_int(self):
        for rec in self:
            try:
                rec.rating_int = int(rec.rating or 0)
            except (ValueError, TypeError):
                rec.rating_int = 0

    @api.constrains('rating')
    def _check_rating(self):
        for rec in self:
            if rec.rating and int(rec.rating) not in range(1, 6):
                raise ValidationError(_('Rating must be between 1 and 5.'))

    def _register_hook(self):
        """Remove the stale ir.rule on THIS model on every server startup.

        Runs during Registry.setup_models() — before the ir.rule ORM cache
        is ever populated — so a raw SQL DELETE is safe and sufficient.
        Having the cleanup here (on the affected model) is more targeted and
        reliable than placing it only on boq.order.line.
        """
        res = super()._register_hook()
        try:
            self.env.cr.execute("""
                DELETE FROM ir_rule
                 WHERE domain_force LIKE %s
                   AND model_id = (
                       SELECT id FROM ir_model
                        WHERE model = 'boq.vendor.rating'
                        LIMIT 1
                   )
            """, ('%res_model%',))
        except Exception:
            pass
        return res

    def _auto_init(self):
        """Same cleanup, runs during install / -u upgrade."""
        res = super()._auto_init()
        try:
            self.env.cr.execute("""
                DELETE FROM ir_rule
                 WHERE domain_force LIKE %s
                   AND model_id IN (
                       SELECT id FROM ir_model
                        WHERE model IN ('boq.vendor.rating', 'vendor.po.rating')
                   )
            """, ('%res_model%',))
        except Exception:
            pass
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.purchase_order_id.message_post(
                body=_('Vendor rated: %s/5 — %s') % (
                    rec.rating, rec.comments or _('No comment.')
                ),
                subtype_xmlid='mail.mt_note',
            )
        return records
