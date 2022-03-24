## -*- coding: utf-8 -*-
#from odoo import models,fields,api
#import time
#import datetime
#import os


#class is_imprimer_etiquette_mrp(models.TransientModel):
#    _name = 'is.imprimer.etiquette.mrp'
#    _description = u"Imprimer Etiquette livraison"
#    
#    
#    def create_etiquette_livraison(self, production_order):
#        tracab_obj = self.pool.get('is.tracabilite.livraison')
#        res = []
#        
#        etiquettes=""
#        if production_order.product_qty:
#            qty = production_order.product_qty
#            lot=1
#            if production_order.product_id.is_gestion_lot:
#                lot=qty
#            while ( qty >= 1):
#                vals = {
#                    'production_id': production_order.id,
#                    'quantity': 1.0,
#                    'lot_fabrication': lot,
#                }
#                new_id = tracab_obj.create(cr, uid, vals, context=context)
#                res.append(new_id)
#                qty = qty - lot
#                etiquettes=etiquettes+tracab_obj.generer_etiquette_livraison(cr, uid, [new_id], context=context)
#        self.pool.get('is.tracabilite.reception').imprimer_etiquette(cr, uid, etiquettes)
#        return res

#    
#    def imprimer_etiquette_livraison(self):
#        production_obj = self.pool.get('mrp.production')
#        production = production_obj.browse(cr, uid, context.get(('active_ids'), []), context=context)
#        data = self.browse(cr, uid , ids[0], context=context)
#        
#        """ Créer Etiquettes en livraison """
#        etiquettes = self.create_etiquette_livraison(cr, uid, production, context)
#        vals={
#            'generer_etiquette': True,
#            'is_gestion_lot': production.product_id.is_gestion_lot,
#        }
#        production_obj.write(cr, uid, production.id,vals, context=context)
#        return True
#                    
