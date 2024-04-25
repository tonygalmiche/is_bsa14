# -*- coding: utf-8 -*-
from odoo import models,fields,api


class account_move_line(models.Model):
    _inherit = "account.move.line"
    _order='is_stock_move_id,sequence,id'

    @api.depends('debit','credit')
    def _compute_is_solde(self):
        for obj in self:
            obj.is_solde = obj.credit - obj.debit

    @api.depends('product_id')
    def _compute_is_sale_order_id(self):
        for obj in self:
            order_id = False
            for line in obj.sale_line_ids:
                order_id = line.order_id.id
            obj.is_sale_order_id = order_id

    @api.depends('product_id')
    def _compute_is_picking_id(self):
        for obj in self:
            picking_id =  obj.is_stock_move_id.picking_id.id
            obj.is_picking_id = picking_id
 

    is_solde         = fields.Float("Solde", store=True, readonly=True, compute='_compute_is_solde')
    is_stock_move_id = fields.Many2one('stock.move', string='Stock Move')
    is_sale_order_id = fields.Many2one('sale.order'   , string="Commande client", store=False, readonly=True, compute='_compute_is_sale_order_id')
    is_picking_id    = fields.Many2one('stock.picking', string="Picking"        , store=False, readonly=True, compute='_compute_is_picking_id')

    is_sale_line_id        = fields.Many2one('sale.order.line', 'Ligne de commande', index=True, default=False, copy=False)
    is_facturable_pourcent = fields.Float("% facturable", digits=(14,2), copy=False, store=True)
    is_a_facturer          = fields.Float("A Facturer"  , digits=(14,2), copy=False, help="Montant à facturer sur cette facture")

