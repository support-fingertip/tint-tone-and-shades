# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqCategory(models.Model):
    """
    BOQ Work Category — maps to a notebook tab in the BOQ form.
    Examples: Electrical, Civil, Lighting, Plumbing, HVAC, Finishing.
    """
    _name = 'boq.category'
    _description = 'BOQ Work Category'
    _order = 'sequence asc, name asc'
    _rec_name = 'name'

    # ── Identity ─────────────────────────────────────────────────────────
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        index=True,
    )
    code = fields.Char(
        string='Technical Code',
        required=True,
        help='Short lowercase code with no spaces. Used internally to link tab fields.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description', translate=True)

    # ── Visual ───────────────────────────────────────────────────────────
    color = fields.Integer(string='Color', default=0)
    icon = fields.Char(
        string='Icon Class',
        default='fa-tools',
        help='FontAwesome class, e.g. fa-bolt, fa-building, fa-tint',
    )
    tag_color_class = fields.Char(
        string='Tag CSS Class',
        compute='_compute_tag_color_class',
        store=True,
    )

    # ── Status ───────────────────────────────────────────────────────────
    active = fields.Boolean(default=True)

    # ── Statistics ───────────────────────────────────────────────────────
    boq_count = fields.Integer(string='BOQs', compute='_compute_boq_count')
    line_count = fields.Integer(string='Total Lines', compute='_compute_boq_count')

    # ── Constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name must be unique.'),
        ('code_uniq', 'unique(code)', 'Category code must be unique.'),
    ]

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('color')
    def _compute_tag_color_class(self):
        color_map = {
            0: 'boq_tag_grey',   1: 'boq_tag_red',
            2: 'boq_tag_orange', 3: 'boq_tag_yellow',
            4: 'boq_tag_teal',   5: 'boq_tag_purple',
            6: 'boq_tag_slate',  7: 'boq_tag_cyan',
            8: 'boq_tag_green',  9: 'boq_tag_pink',
            10: 'boq_tag_blue',  11: 'boq_tag_indigo',
        }
        for rec in self:
            rec.tag_color_class = color_map.get(rec.color, 'boq_tag_grey')

    def _compute_boq_count(self):
        Line = self.env['boq.order.line']
        for rec in self:
            rec.boq_count = self.env['boq.boq'].search_count(
                [('category_ids', 'in', rec.id)]
            )
            rec.line_count = Line.search_count([('category_id', '=', rec.id)])
