# -*- coding: utf-8 -*-
from odoo import models,fields,api
import os
import time
import datetime


class is_etiquette_line(models.TransientModel):
    _name = 'is.etiquette.line'
    _description = 'Lignes des etiquettes'
    
    product_id   = fields.Many2one('product.product', 'Produit', required=True)
    quantity     = fields.Float('Quantité', required=True)
    move_id      = fields.Many2one('stock.move', 'Mouvement de stock', required=True)
    etiquette_id = fields.Many2one('is.imprimer.etiquette', 'Etiquette')
    
    
class is_imprimer_etiquette(models.TransientModel):
    _name = 'is.imprimer.etiquette'
    _description = "Imprimer Etiquette"
    
    num_bl          = fields.Char('Numéro du BL fournisseur', required=True)
    etiquette_lines = fields.One2many('is.etiquette.line', 'etiquette_id', required=True)
    

    def get_lines_picking(self, picking):
        res = []
        if picking:
            for move in picking.move_lines:
                if move.product_id.is_trace_reception:
                    vals = {
                        'product_id': move.product_id.id,
                        'quantity': move.product_uom_qty,
                        'move_id': move.id,
                    }
                    res.append((0,0, vals))
        return res
    

    @api.model
    def default_get(self, fields_list):
        res={}
        picking = self.env['stock.picking'].browse(self._context.get(('active_ids'), []))
        if 'etiquette_lines' in fields_list:
            lines = self.get_lines_picking(picking)
            res.update(etiquette_lines=lines)
        return res
    

    def exist_etiquette(self, move_id):
        tracab_obj = self.env['is.tracabilite.reception']
        ids = tracab_obj.search([('move_id','=',move_id)])
        if ids:
            return ids[0]
        else:
            return False
        
        
    def create_etiquette(self, picking):
        tracab_obj = self.env['is.tracabilite.reception']
        res = []
        etiquettes=""
        for line in self.etiquette_lines:
            etiquette = self.exist_etiquette(line.move_id.id)
            vals = {
                'picking_id': picking.id,
                'bl_fournisseur': self.num_bl,
                'move_id': line.move_id.id,
                'quantity': line.quantity
            }
            if etiquette:
                etiquette.write(vals)
                res.append(etiquette.id)
            else:
                new_id = tracab_obj.create(vals)
                res.append(new_id)
                etiquette_id=new_id
            i = 0
            while i < line.quantity:
                #etiquettes=line.generer_etiquette()
                #line.imprimer_etiquette(etiquettes)
                #etiquettes=etiquettes+tracab_obj.generer_etiquette(cr, uid, [etiquette_id], context=context)
                i += 1
        #self.pool.get('is.tracabilite.reception').imprimer_etiquette(cr, uid, etiquettes)
        return res
        

    def verifier_etiquettes_picking(self, etiquettes, picking):
        tracab_obj = self.env['is.tracabilite.reception']
        res=[]
        for move in picking.move_ids_without_package:
            etiquettes = tracab_obj.search([('move_id','=',move.id)])
            for etiquette in etiquettes:
                res.append(etiquette.id)
        return res
    

    def imprimer_etiquette(self):
        context = self._context
        picking_obj = self.env['stock.picking']
        picking = picking_obj.browse(context.get(('active_ids'), []))        
        etiquettes = self.create_etiquette(picking)
        etiquette_ids = self.verifier_etiquettes_picking(etiquettes, picking)
        picking.write({'etiquette_reception_ids': [(6, 0, etiquette_ids)]})


        res=""
        for etiquette in picking.etiquette_reception_ids:
            for x in range(0, int(etiquette.quantity)):
                #etiquette.imprimer_etiquette_direct()
                res+=etiquette.generer_etiquette()
        self.env['is.tracabilite.reception'].imprimer_etiquette(res)
        return True
