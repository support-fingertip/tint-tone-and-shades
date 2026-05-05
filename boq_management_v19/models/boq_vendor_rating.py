# -*- coding: utf-8 -*-
from markupsafe import Markup, escape
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class BoqVendorRating(models.Model):
    
    _name = 'boq.vendor.rating'
    _description = 'Vendor Rating'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _rec_name = 'partner_id'

    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        required=False,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        required=True,
        index=True,
    )

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

    comments = fields.Text(string='Comments / Remarks')
    date = fields.Date(string='Rating Date', default=fields.Date.today)

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
            return []        
        return [('id', '=', 0)] 

    partner_type = fields.Selection(
        related='partner_id.partner_type',
        string='Partner Type',
        store=True,
        index=True,
        help='Mirrors the rated partner\'s type (Vendor or Supplier).',
    )

    company_id = fields.Many2one(
        related='purchase_order_id.company_id',
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            'unique_po_rating',
            'unique(purchase_order_id)',
            'A rating already exists for this Purchase Order. Edit the existing rating.',
        ),
    ]

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

    def action_save_and_close(self):
        """Save the rating and navigate to the partner form so the parent view
        loads fresh data (One2many list + avg_rating / rating_count).

        When opened from the vendor master (show_rating_tab in context) we
        navigate the main window back to that partner — this gives a guaranteed
        fresh load.  When opened from a PO we just close the dialog so the user
        stays on the PO.
        """
        if self.env.context.get('show_rating_tab') and self.partner_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rating_label = dict(rec._fields['rating'].selection).get(rec.rating, rec.rating)
            body = Markup('<b>Vendor Rated: %s / 5</b>') % rating_label
            if rec.comments:
                body += Markup('<br/>') + escape(rec.comments)
            if rec.partner_id:
                rec.partner_id.message_post(body=body, subtype_xmlid='mail.mt_note')
            if rec.purchase_order_id:
                rec.purchase_order_id.message_post(body=body, subtype_xmlid='mail.mt_note')
        return records

    def write(self, vals):
        before = {
            rec.id: {'rating': rec.rating, 'comments': rec.comments}
            for rec in self
        }
        result = super().write(vals)
        for rec in self:
            b = before.get(rec.id, {})
            msgs = []
            if 'rating' in vals and b.get('rating') != rec.rating:
                sel = dict(rec._fields['rating'].selection)
                old_lbl = sel.get(b.get('rating'), b.get('rating') or '—')
                new_lbl = sel.get(rec.rating, rec.rating or '—')
                msgs.append(Markup('Rating updated: <b>%s → %s</b> / 5') % (old_lbl, new_lbl))
            if 'comments' in vals and b.get('comments') != rec.comments:
                msgs.append(Markup('Comments updated: %s') % escape(rec.comments or '(cleared)'))
            if msgs:
                body = Markup('<br/>').join(msgs)
                if rec.partner_id:
                    rec.partner_id.message_post(body=body, subtype_xmlid='mail.mt_note')
                if rec.purchase_order_id:
                    rec.purchase_order_id.message_post(body=body, subtype_xmlid='mail.mt_note')
        return result
