# -*- coding: utf-8 -*-
# from odoo import http


# class PurchaseOrderApproval(http.Controller):
#     @http.route('/purchase_order_approval/purchase_order_approval', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/purchase_order_approval/purchase_order_approval/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('purchase_order_approval.listing', {
#             'root': '/purchase_order_approval/purchase_order_approval',
#             'objects': http.request.env['purchase_order_approval.purchase_order_approval'].search([]),
#         })

#     @http.route('/purchase_order_approval/purchase_order_approval/objects/<model("purchase_order_approval.purchase_order_approval"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('purchase_order_approval.object', {
#             'object': obj
#         })

