# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    """
    Extends res.config.settings to add a configuration setting for selecting
    a default product for purchase advance payments.
    """
    _inherit = 'res.config.settings'

    purchase_advance_product_id = fields.Many2one('product.product', string="Product",
                                                  config_parameter='purchase.advance_payment_product_id',
                                                  domain=[('purchase_ok', '=', True)])
