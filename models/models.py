# -*- coding: utf-8 -*-

from collections import namedtuple
import json
import time

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.addons.procurement.models import procurement
from odoo.exceptions import UserError, ValidationError

class stock_barcode_rule(models.Model):
    _name = 'stock.barcode.rule'

    name = fields.Char('名称',required = True)
    length = fields.Char('总位数',required = True)
    re = fields.Selection(selection=[
        ('draft', '正序'),
        ('done', '逆序')],string ='顺序',required = True)
    product_start = fields.Char('产品品类起位',required = True)
    product_end = fields.Char('产品品类止位',required = True)
    weight_start = fields.Char('产品重量起位',required = True)
    weight_end = fields.Char('产品重量止位',required = True)
    partner_id = fields.Many2one('res.partner',string ="所属供应商",required = True)
    product_id = fields.Many2one('product.product',string ="产品",required = True)
    partner_code = fields.Char('供应商条码',required = True)
    local_code =fields.Char('内部条码',required = True)
class Partner(models.Model):
    _inherit = 'res.partner'
    barcode_rule = fields.One2many('stock.barcode.rule','partner_id',string = "条码规则")
    batch_code = fields.Char("供应商代号")
  
class Picking(models.Model):
    _inherit = 'stock.picking'
    barcode_rule = fields.One2many('stock.barcode.rule',related = "partner_id.barcode_rule")
    should_received = fields.Float('计划总重量(千克)',compute="_compute_should_received")
    real_received = fields.Float('实际总重量(千克)',compute ="_compute_real_received")
    demaged_received = fields.Float('破损总重量(千克)',compute = "_compute_demaged_received")
    should_sum_uom = fields.Float('计划总件数',compute = "_compute_should_sum_uom")
    real_sum_uom = fields.Float('实际总件数',compute="_compute_real_sum_uom")
    orders_name = fields.Char('外部订单号') 
    batch_code = fields.Many2one('batch.code',"批次")
    min_date_copy = fields.Datetime('安排的日期',related = "min_date")
    financial_state = fields.Selection(selection=[('draft', '否'),('done', '是')],string ='融资状态',default = "draft")
    owner = fields.Many2one('res.partner',string="货主")
    	
    @api.onchange('partner_id')
    def _onchange_batch_code(self):
	batch_code = self.env['batch.code'].search([])
	for x in batch_code:pass
	if batch_code:
	    num = x.id
	else:num = 0
	if self.picking_type_code == "incoming":
	    if self.partner_id.batch_code:
	        date =  time.strftime('%Y%m%d',time.localtime(time.time()))
	        self.env['batch.code'].create({"name":str(self.partner_id.batch_code)+str(date)+'-'+str(num+1)})
	        self.batch_code = self.env['batch.code'].search([('name','=',str(self.partner_id.batch_code)+str(date)+'-'+str(num+1))]).id
	    else:self.batch_code = num

    @api.multi
    def _compute_real_sum_uom(self):
        uom = 0
	for r in self:pass
	for x in r.pack_operation_ids:
	   uom = uom + x.real_all_sum_uom
	r.real_sum_uom = uom

    @api.multi
    def _compute_demaged_received(self):
        uom = 0
	for r in self:pass
        for x in r.pack_operation_ids:
           uom = uom + x.all_demaged_received
        r.demaged_received = uom

    @api.multi
    def _compute_customer_real_send_uom(self):
	uom = 0
	for r in self:pass
	for x in r.pack_operation_ids:
	    uom = uom + sum([x.customer_real_send_uom for x in r.pack_operation_ids])
	if len(r.pack_operation_product_ids) > 1:
	    r.customer_real_send_uom = uom/2
	else:r.customer_real_send_uom = uom

    @api.multi
    def _compute_should_received(self):
	for r in self:pass
        r.should_received = self.env['stock.move'].read_group([('picking_id','=',r.id)],[],[],[])[0]['product_uom_weight']
        return
    @api.multi
    def _compute_should_sum_uom(self):
        for r in self:pass
        r.should_sum_uom = self.env['stock.move'].read_group([('picking_id','=',r.id)],[],[],[])[0]['product_uom_qty']
        return

    @api.multi
    def _compute_real_received(self):
        uom = 0
	for r in self:pass
        for x in r.pack_operation_ids:
            uom = uom + sum([x.all_real_received for x in r.pack_operation_ids])
        if len(r.pack_operation_product_ids) > 1:
            r.real_received = uom/2
        else:r.real_received = uom
        return

    @api.multi
    def _compute_real_send(self):
        uom = 0
	for r in self:pass
        for x in r.pack_operation_ids:
            uom = uom + sum([x.all_real_send for x in r.pack_operation_ids])
        if len(r.pack_operation_product_ids) > 1:
            r.real_send = uom/2
        else:r.real_send = uom
        return
    
    @api.multi
    def _compute_should_send(self):
        uom = 0
	for r in self:pass

        for x in r.pack_operation_ids:
            uom = uom + sum([x.all_should_send for x in r.pack_operation_ids])
        if len(r.pack_operation_product_ids) > 1:
            r.should_send = uom/2
        else:r.should_send = uom
        return

    def _create_lots_for_picking(self):
        Lot = self.env['stock.production.lot']
        for pack_op_lot in self.mapped('pack_operation_ids').mapped('pack_lot_ids'):
            if not pack_op_lot.lot_id:
                lot = Lot.create({'name': pack_op_lot.lot_name,'batch_code_line':self.batch_code.id,'partner_id':self.partner_id.id,'stock_picking_id':self.id,'product_id': pack_op_lot.operation_id.product_id.id,'real_received':pack_op_lot.real_received,'should_received':pack_op_lot.should_received,'demaged_received':pack_op_lot.demaged_received})
                pack_op_lot.write({'lot_id': lot.id})
        self.mapped('pack_operation_ids').mapped('pack_lot_ids').filtered(lambda op_lot: op_lot.qty == 0.0).unlink()
    create_lots_for_picking = _create_lots_for_picking

class PackOperation(models.Model):
    _inherit = "stock.pack.operation"
    all_real_received = fields.Float('实际总重量(千克)')
    all_should_received = fields.Float('扫码获得的总重量(千克)')
    call_weight = fields.Float('计划总重量(千克)',compute = "_call_weight")
    all_demaged_received = fields.Float('破损总重量(千克)')
    real_all_sum_uom = fields.Float('实际总件数',related = "qty_done")
    no_tips_weight = fields.Boolean('不再提醒重量警告')
    no_tips_qty = fields.Boolean('不再提醒数量警告')
    no_tips_product = fields.Boolean('不再提醒产品警告')
    no_tips_partner = fields.Boolean('不再提醒供应商警告')
    pack_lot_ids_copy = fields.One2many('stock.pack.operation.lot', 'operation_id', '批次使用情况',related = "pack_lot_ids")
    code = fields.Selection([('incoming', 'Vendors'), ('outgoing', 'Customers'), ('internal', 'Internal')], 'Type of Operation', related = "picking_id.picking_type_id.code")
    #_sql_constraints = [
    #    ('all_real_received', 'CHECK(all_real_received >= all_should_received)', 'all_received is more than should_received')]

    @api.multi
    def _call_weight(self):
	for i in self:
	    i.call_weight = self.env['stock.move'].read_group([('picking_id','=',i.picking_id.id),('product_id','=',i.product_id.id)],[],[],[])[0]['product_uom_weight']
        return

    @api.onchange('pack_lot_ids')
    def _onchange_packlots(self):
        self.qty_done = sum([x.qty for x in self.pack_lot_ids])
	self.all_real_received = sum([x.real_received for x in self.pack_lot_ids])
        self.all_should_received = sum([x.should_received for x in self.pack_lot_ids])
	self.all_demaged_received = sum([x.demaged_received for x in self.pack_lot_ids])
	print 'start'
	if self.picking_id.picking_type_id.code!='internal':
	    if not self.no_tips_qty:
                if self.real_all_sum_uom > self.product_qty:
	            uom = self.real_all_sum_uom - self.product_qty
	    	    self.no_tips_qty = True
		    print self.no_tips_qty
                    return {'warning': {'title': _('您已超出预定件数'),
                            'message': _('您已超出预定数量的%(barcode)s件,是否继续扫描') % {'barcode': uom},}} 

	    if not self.no_tips_weight:
                if self.all_real_received > self.call_weight:
	            weight = self.all_real_received - self.call_weight
		    self.no_tips_weight = True
		    if self.picking_id.financial_state !="done":
                        return {'warning': {'title': _('您已超出预定重量'),
                            'message': _('您已超出预定重量的%(barcode)s千克,是否继续扫描') % {'barcode': self.all_real_received - self.call_weight},}}
	    if int(self.all_real_received) - 200 > int(self.call_weight):
	        if self.picking_id.financial_state == "done":
		    return {'warning': {'title': _('警告'),
                            'message': _('总重量为"%(barcode)s千克",当前已扫%(call_weight)dKG') % {'barcode': self.all_real_received - self.call_weight,'call_weight':self.all_real_received},}}

        if self.picking_id.picking_type_id.name==u"收货":

            barcode_rule = self.picking_id.barcode_rule.search([('product_id','=',self.product_id.id),('partner_id.id','=',self.picking_id.partner_id.id)])
	    for line in self.pack_lot_ids:
	        if line.lot_name:
                    if barcode_rule.re == "draft":
                        barcode = line.lot_name[int(barcode_rule.product_start)-1:int(barcode_rule.product_end)]
                    else:barcode = line.lot_name[-int(barcode_rule.product_end):-int(barcode_rule.product_start)+1]
		    if barcode == barcode_rule.partner_code:
		        barcode = barcode_rule.local_code
	  	    else:
		        if not self.no_tips_product:
			    self.no_tips_product = True
			    return {'warning': {'title': _('内部条码出错'),
                            'message': _('请注意收货条码是否有对应的产品条码')}}
	            product = self.env['product.product'].search([('barcode','=',barcode.upper()),('id','=',self.product_id.id)])
	            if not product.id:
			if not self.no_tips_partner:
			    self.no_tips_partner = True
                            return {'warning': {'title': _('内部条码出错'),
                            'message': _('请注意收货条码是否与对应产品相符')}}
	

    @api.multi
    def save(self):
        # TDE FIXME: does not seem to be used -> actually, it does
        # TDE FIXME: move me somewhere else, because the return indicated a wizard, in pack op, it is quite strange
        # HINT: 4. How to manage lots of identical products?
        # Create a picking and click on the Mark as TODO button to display the Lot Split icon. A window will pop-up. Click on Add an item and fill in the serial numbers and click on save button
        for pack in self:
            if pack.product_id.tracking != 'none':
                pack.write({'qty_done': sum(pack.pack_lot_ids.mapped('qty'))})
	batch_code_line = self.picking_id.batch_code
	for pack_operation in self.pack_lot_ids:
	    print pack_operation.lot_id
	    pack_operation.lot_id.write({"batch_code_line":batch_code_line.id})
	print 'save'
        return {'type': 'ir.actions.act_window_close'}

class PackOperationLot(models.Model):
    _inherit = "stock.pack.operation.lot"
    real_received = fields.Float('实际重量(KG)')
    should_received = fields.Float('扫码重量(KG)',compute= "_compute_should_received",readonly = False)
    demaged_received = fields.Float('破损重量(KG)')
    barcode_rule = fields.One2many('stock.barcode.rule',related = "operation_id.picking_id.barcode_rule")

    @api.depends('barcode_rule', 'lot_name')
    def _compute_should_received(self):
        for line in self:
	    weight = line.lot_id.should_send
	    if line.lot_name:
	        if line.operation_id.picking_id.picking_type_id.name==u"收货":
		    barcode_rule = line.operation_id.picking_id.barcode_rule.search([('product_id','=',line.operation_id.product_id.id),('partner_id','=',line.operation_id.picking_id.partner_id.id)])
	            if barcode_rule.re == "draft":
	                weight = line.lot_name[int(barcode_rule.weight_start)-1:int(barcode_rule.weight_end)]
	            elif barcode_rule.re =="done":weight = line.lot_name[-int(barcode_rule.weight_end):-int(barcode_rule.weight_start)+1]
		    else:#raise ValidationError(_('请注意该供应商是否有对应条码规则'))
		        pass
            if weight:
                line.update({
                    'should_received':weight,
                    'real_received':weight
                    })

    @api.onchange('real_received', 'demaged_received')
    def _compute_real_received(self):
        for line in self:
	    if line.operation_id.picking_id.picking_type_id.name==u"收货":
                line.update({
                    'real_received':int(line.should_received)- int(line.demaged_received)
                })
	    else:pass

class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'
    real_received = fields.Float('实际总重量(千克)')
    should_received = fields.Float('扫码所得重量(千克)')
    demaged_received = fields.Float('破损重量(千克)')
    real_send = fields.Float('实际总重量(千克)',related = "should_send")
    should_send = fields.Float('计划总重量(千克)',related = "real_received")
    stock_picking_id = fields.Many2one('stock.picking',string = "调拨单")
    partner_id = fields.Many2one('res.partner',string = "货主")
    batch_code_line = fields.Many2one('batch.code','批次号码')
    lock = fields.Boolean('锁定')
    product_state = fields.Selection([('demaged','破损'),('ok','完整')],string = "商品状态",compute = '_compute_product_state')	
    location_id = fields.Many2one('stock.location',related = 'quant_ids.location_id',string = "位置",store=True)    

    @api.multi
    def _compute_product_state(self):
        if self.demaged_received ==0:
	    self.product_state = 'ok'
	elif self.demaged_received !=0:
	    self.product_state = 'demaged'
	else:pass

class BarchCode(models.Model):
    _name = 'batch.code'
    name = fields.Char('名称')
    stock_production_lot_id = fields.One2many('stock.production.lot','batch_code_line','商品批次',copy=True)
    auto_delect = fields.Char('预留冗余条目(条)',default = '5')
    data = fields.Char('发给单据的数据')
    owner = fields.Many2one('res.partner',string = "货主")
    state = fields.Boolean('锁定')
    @api.onchange('stock_production_lot_id')
    def _compute_template(self):
	for i in self.stock_production_lot_id:pass
	if i:self.owner = i.partner_id.id
	product_id = []
	location_id = []
	data = ''
        for product in self.stock_production_lot_id:
	    product_id.append(product.product_id.id)
	for location in self.stock_production_lot_id:
            location_id.append(location.quant_ids.location_id.id)
	product_id = list(set(product_id))
	location_id = list(set(location_id))
	print product_id
	print location_id
#	for L in range(len(location_id)):
#	    for P in range(len(product_id)):
#	        weight = self.env['stock.production.lot'].read_group([('batch_code_line.name','=',self.name),('quant_ids','=',location_id[L]),('product_id','=',product_id[P])],[],[])[0]['real_received']
#		if weight != None:
#	 	    x = []
#		    x.append(self.env['stock.location'].search([('id','=',location_id[L])]).name)
#		    x.append(self.env['product.product'].search([('id','=',product_id[P])]).name)
#		    x.append(weight)
#		    data.append(x)
#	print data
#	self.env['batch.code'].search([('name','=',self.name)]).write({'data':data})
        for L in range(len(location_id)):
            for P in range(len(product_id)):
                weight = self.env['stock.production.lot'].read_group([('batch_code_line.name','=',self.name),('quant_ids.location_id','=',location_id[L]),('product_id','=',product_id[P])],[],[])[0]['real_received']
                if weight != None:
                    data = data + str(location_id[L]) + '-' + str(product_id[P]) + '|'
        print data[:-1]
        self.env['batch.code'].search([('name','=',self.name)]).write({'data':data[:-1]})

    @api.onchange('name')
    def _delete_batch_code_unused(self):
        for i in self.env['batch.code'].search([]):pass
	last_id = i.id
	for i in self.env['batch.code'].search([]):
	    if i.id < last_id - int(i.auto_delect) + 2 :
	        if not len(i.stock_production_lot_id):
		    i.unlink()
    @api.multi
    def lock_all(self):
	for i in self.stock_production_lot_id:
	    i.lock = True
    
    @api.multi
    def unlock_all(self):
	for i in self.stock_production_lot_id:
	    i.lock = False

class StockMove(models.Model):
    _inherit = "stock.move"
    product_uom_weight = fields.Float('计划重量(千克)',required = True,default="0")

class StockBarcodeWizard(models.TransientModel):
    _name = "stock.barcode.wizard"
    weight = fields.Char('已超出重量')
    
