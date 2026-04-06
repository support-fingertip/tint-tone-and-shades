# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MarginThresholdConfig(models.Model):
    _name = 'margin.threshold.config'
    _description = 'Trade-wise Margin Threshold Configuration'
    _rec_name = 'category_id'

    category_id = fields.Many2one(
        'product.category',
        string="Trade (Product Category)",
        required=True,
    )
    minimum_margin = fields.Float(
        string="Minimum Margin (%)",
        required=True,
    )
    approver_id = fields.Many2one(
        'res.users',
        string="Approver (Head of Supply Chain)",
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('unique_category_company', 'unique(category_id, company_id)',
         'A threshold already exists for this product category in this company.'),
    ]
