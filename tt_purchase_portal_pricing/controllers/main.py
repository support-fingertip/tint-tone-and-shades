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

    @http.route(['/my/purchase/<int:order_id>/submit'], type='http', auth='user', website=True)
    def submit_purchase_order(self, order_id, **post):

        order = request.env['purchase.order'].sudo().browse(order_id).exists()

        # Check order exists
        if not order:
            return request.redirect('/my')

        # Security check
        if order.partner_id != request.env.user.partner_id:
            raise AccessError("You are not allowed to access this document.")

        # Only allow submit when RFQ is in 'sent' state
        if order.state == 'sent':
            # Plain text message (NO HTML)
            body_text = (
                f"Dear {order.company_id.name},\n\n"
                f"The vendor {order.partner_id.name} has successfully submitted "
                f"against the RFQ {order.name}. Please review and proceed further.\n\n"
                f"Best regards,\n"
                f"{order.partner_id.name}"
            )

            order.sudo().message_post(
                subject=f"Vendor Submission: {order.name}",
                body=body_text,
                message_type='email',
                subtype_xmlid='mail.mt_comment',
            )

            # Change state
            order.action_submit()

        return request.redirect('/my/rfq/submitted')

    @http.route(['/my/rfq/submitted', '/my/rfq/submitted/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_submitted_rfqs(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):

        return self._render_portal(
            "purchase.portal_my_purchase_rfqs",
            page, date_begin, date_end, sortby, filterby,
            [('state', 'in', ['draft', 'submitted', 'to approve', 'cancel'])],
            {},
            None,
            "/my/rfq/submitted",
            'my_submitted_rfqs_history',
            'rfq',
            'rfqs'
        )