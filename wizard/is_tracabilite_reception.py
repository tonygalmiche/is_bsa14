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
                    res.append(vals)
        return res
    
    # def default_get(self, cr, uid, fields, context=None):
    #     if context is None: context = {}
    #     res = super(is_imprimer_etiquette, self).default_get(cr, uid, fields, context=context)
    #     picking_ids = context.get('active_ids', [])
    #     active_model = context.get('active_model')

    #     if not picking_ids or len(picking_ids) != 1:
    #         return res
    #     assert active_model in ('stock.picking'), 'Bad context propagation'
    #     picking_id, = picking_ids
    #     picking = self.pool.get('stock.picking').browse(cr, uid, picking_id, context=context)
    #     if 'etiquette_lines' in fields:
    #         lines = self.get_lines_picking(cr, uid, picking, context=context)
    #         res.update(etiquette_lines=lines)        
    #     return res
    
    
    def exist_etiquette(self, move_id):
        tracab_obj = self.pool.get('is.tracabilite.reception')
        ids = tracab_obj.search(cr, uid, [('move_id','=',move_id)], context=context)
        if ids:
            return ids[0]
        else:
            return False
        
        
    def create_etiquette(self, lines, num_bl, picking_id):
        tracab_obj = self.pool.get('is.tracabilite.reception')
        
        res = []
        etiquettes=""
        for line in lines:
            etiquette_id = self.exist_etiquette(cr, uid, line.move_id.id, context)
            vals = {
                'picking_id': picking_id,
                'bl_fournisseur': num_bl,
                'move_id': line.move_id and line.move_id.id,
                'quantity': line.quantity
            }
            if etiquette_id:
                tracab_obj.write(cr, uid, etiquette_id, vals, context=context)
                res.append(etiquette_id)
            else:
                new_id = tracab_obj.create(cr, uid, vals, context=context)
                res.append(new_id)
                etiquette_id=new_id

            i = 0
            while i < line.quantity:
                etiquettes=etiquettes+tracab_obj.generer_etiquette(cr, uid, [etiquette_id], context=context)
                i += 1


        self.pool.get('is.tracabilite.reception').imprimer_etiquette(cr, uid, etiquettes)


        return res
    
    
    def verifier_etiquettes_picking(self, etiquettes, move_lines):
        tracab_obj = self.pool.get('is.tracabilite.reception')
        
        for move in move_lines:
            etiquette_ids = tracab_obj.search(cr, uid, [('move_id','=',move.id)], context=context)
            if etiquette_ids:
                if etiquette_ids[0] in etiquettes:
                    continue
                else:
                    etiquettes.append(etiquette_ids[0])
        return etiquettes

    
    def imprimer_etiquette(self):
        picking_obj = self.pool.get('stock.picking')
        
        picking = picking_obj.browse(cr, uid, context.get(('active_ids'), []), context=context)
        data = self.browse(cr, uid , ids[0], context=context)
        
        """ Créer Etiquettes en réception """
        etiquettes = self.create_etiquette(cr, uid, data.etiquette_lines, data.num_bl, picking.id, context)
        etiquette_ids = self.verifier_etiquettes_picking(cr, uid, etiquettes, picking.move_lines, context=context)
        picking_obj.write(cr, uid, picking.id, {'etiquette_reception_ids': [(6, 0, etiquette_ids)]}, context=context)
        return True
                    
