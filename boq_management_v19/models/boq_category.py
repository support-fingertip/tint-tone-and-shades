# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api

# ir.config_parameter key that stores the set of category IDs with is_dynamic=True.
# Format: JSON-encoded list of integers, e.g. "[1, 5, 12]"
# Using an existing system-parameter table means zero new DB columns needed.
_DYNAMIC_PARAM = 'boq.category.dynamic_ids'


class BoqCategory(models.Model):
    """
    BOQ Work Category — maps to a notebook tab in the BOQ form.
    Examples: Electrical, Civil, Lighting, Plumbing, HVAC, Finishing.

    Task 1 — Work Category UI fix:
    'is_dynamic' controls whether the "Add new category" (sub-categories) section
    is visible on the form.  It is stored in ir.config_parameter so no new
    DB column is required on boq_category.
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
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )

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

    # ── Task 1: Dynamic Category Flag ────────────────────────────────────
    # Stored in ir.config_parameter (existing table) — NO new DB column.
    # Hidden by default (is_dynamic=False).  Enable to reveal the
    # "Add new category" sub-categories section on this category's form.
    is_dynamic = fields.Boolean(
        string='Dynamic Category',
        compute='_compute_is_dynamic',
        inverse='_inverse_is_dynamic',
        store=False,
        help='When enabled, the "Add new category" section becomes visible '
             'on this Work Category form.  Disabled by default.',
    )

    # ── Status ───────────────────────────────────────────────────────────
    active = fields.Boolean(default=True)

    # ── Statistics ───────────────────────────────────────────────────────
    boq_count = fields.Integer(
        string='BOQs',
        compute='_compute_boq_count',
    )
    line_count = fields.Integer(
        string='Total Lines',
        compute='_compute_boq_count',
    )

    # ── Constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name must be unique.'),
        ('code_uniq', 'unique(code)', 'Category code must be unique.'),
    ]

    # ── Helpers ───────────────────────────────────────────────────────────
    def _get_dynamic_ids(self):
        """Return the set of category IDs that have is_dynamic=True."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            _DYNAMIC_PARAM, '[]'
        )
        try:
            return set(json.loads(raw))
        except (ValueError, TypeError):
            return set()

    def _set_dynamic_ids(self, id_set):
        """Persist the set of dynamic category IDs to ir.config_parameter."""
        self.env['ir.config_parameter'].sudo().set_param(
            _DYNAMIC_PARAM, json.dumps(sorted(id_set))
        )

    # ── is_dynamic compute / inverse ─────────────────────────────────────
    @api.depends()
    def _compute_is_dynamic(self):
        dynamic_ids = self._get_dynamic_ids()
        for rec in self:
            rec.is_dynamic = rec.id in dynamic_ids

    def _inverse_is_dynamic(self):
        dynamic_ids = self._get_dynamic_ids()
        for rec in self:
            if rec.is_dynamic:
                dynamic_ids.add(rec.id)
            else:
                dynamic_ids.discard(rec.id)
        self._set_dynamic_ids(dynamic_ids)

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
            boqs = self.env['boq.boq'].search_count(
                [('category_ids', 'in', rec.id)]
            )
            lines = Line.search_count([('category_id', '=', rec.id)])
            rec.boq_count = boqs
            rec.line_count = lines
