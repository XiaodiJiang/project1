# -*- coding: utf-8 -*-
from odoo import http

# class StockBarcodeRule(http.Controller):
#     @http.route('/stock_barcode_rule/stock_barcode_rule/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_barcode_rule/stock_barcode_rule/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_barcode_rule.listing', {
#             'root': '/stock_barcode_rule/stock_barcode_rule',
#             'objects': http.request.env['stock_barcode_rule.stock_barcode_rule'].search([]),
#         })

#     @http.route('/stock_barcode_rule/stock_barcode_rule/objects/<model("stock_barcode_rule.stock_barcode_rule"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_barcode_rule.object', {
#             'object': obj
#         })