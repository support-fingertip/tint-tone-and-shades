# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers import portal


class PurchasePortalPriceUpdate(portal.CustomerPortal):

    @http.route(['/my/purchase/<int:order_id>/update_line_price'], type='jsonrpc', auth='public', website=True)
    def portal_update_line_price(self, order_id, access_token=None, line_id=None, price_unit=None, **kw):
        try:
            order_sudo = self._document_check_access('purchase.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'success': False, 'error': 'Access denied'}

        if order_sudo.state not in ('draft', 'sent'):
            return {'success': False, 'error': 'Order is not in RFQ state'}

        line = order_sudo.order_line.filtered(lambda l: l.id == int(line_id))
        if not line:
            return {'success': False, 'error': 'Line not found'}

        line.sudo().write({'price_unit': float(price_unit)})
        return {'success': True}
