# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    boq_ids = fields.One2many(
        comodel_name='boq.boq',
        inverse_name='partner_id',
        string='Bills of Quantities',
    )
    boq_count = fields.Integer(
        string='BOQ Count',
        compute='_compute_boq_count',
    )

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for partner in self:
            partner.boq_count = len(partner.boq_ids)

    def action_view_boqs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills of Quantities'),
            'res_model': 'boq.boq',
            'view_mode': 'list,kanban,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

 
    partner_type = fields.Selection(
        selection=[
            ('vendor',   'Vendor'),
            ('supplier', 'Supplier'),
            ('employee', 'Employee'),
            ('customer', 'Customer'),
        ],
        string='Partner Type',
        index=True,
        help='Controls how this partner is used in BOQ workflows. '
             '"Vendor" creates Vendor RFQs; "Supplier" creates Supplier RFQs.',
    )


    work_category_ids = fields.Many2many(
        comodel_name='boq.category',
        relation='boq_partner_category_rel',
        column1='partner_id',
        column2='category_id',
        string='Work Categories',
        help='Trades / work categories this partner handles.\n'
             'Used to auto-assign this partner to RFQs when Create RFQ is '
             'clicked on a BOQ that shares the same categories.',
    )

    rating_ids = fields.One2many(
        comodel_name='boq.vendor.rating',
        inverse_name='partner_id',
        string='Vendor Ratings',
    )
    avg_rating = fields.Float(
        string='Average Rating',
        compute='_compute_avg_rating',
        store=True,
        digits=(2, 1),
        help='Average of all vendor ratings (1–5 scale).',
    )
    rating_count = fields.Integer(
        string='Rating Count',
        compute='_compute_avg_rating',
        store=True,
    )

    @api.depends('rating_ids', 'rating_ids.rating_int')
    def _compute_avg_rating(self):
        for partner in self:
            ratings = partner.rating_ids.mapped('rating_int')
            valid = [r for r in ratings if r > 0]
            if valid:
                partner.avg_rating = sum(valid) / len(valid)
                partner.rating_count = len(valid)
            else:
                partner.avg_rating = 0.0
                partner.rating_count = 0

    def action_rate_vendor(self):
        """Open rating dialog directly from the vendor/partner form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rate — %s') % self.name,
            'res_model': 'boq.vendor.rating',
            'view_mode': 'form',
            'view_id': self.env.ref('boq_management_v19.view_boq_vendor_rating_form').id,
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'show_rating_tab': True,
            },
        }

    def action_reload_ratings(self):
        """Reload the vendor master form fresh so the rating_ids list reflects
        any ratings added from POs since the page was last loaded."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_ratings(self):
        """Open the list of ratings for this partner."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ratings — %s') % self.name,
            'res_model': 'boq.vendor.rating',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
            },
        }
