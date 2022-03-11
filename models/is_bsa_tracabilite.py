# -*- coding: utf-8 -*-
from itertools import product
from odoo import models,fields,api
from datetime import datetime, timedelta
import time
import os


def datamax(sizex, sizey, y, x, txt):
    sizex="0"+str(sizex)
    sizex=sizex[-1:]

    sizey="0"+str(sizey)
    sizey=sizey[-1:]

    x="0000"+str(x)
    x=x[-4:]

    y="0000"+str(y)
    y=y[-4:]

    r="10"+sizex+sizey+"000"+y+x+(txt or '')+chr(10)
    return r


class is_tracabilite_reception(models.Model):
    _name = 'is.tracabilite.reception'
    _description = "Traçabilité réception"
    _order = "create_date desc"
    
    name           = fields.Char('Numéro', required=True, readonly=True, default=" ")
    picking_id     = fields.Many2one('stock.picking', 'Réception', readonly=False)
    product_id     = fields.Many2one('product.template', 'Article', readonly=False)
    bl_fournisseur = fields.Char('Numéro du BL fournisseur', readonly=False)
    move_id        = fields.Many2one('stock.move', 'Mouvement de stock', readonly=False)
    quantity       = fields.Float('Quantité', readonly=False)
    
    @api.model
    def create(self, vals):
        self.update_product(vals)
        vals['name'] = self.env['ir.sequence'].next_by_code('is.tracabilite.reception')
        res = super(is_tracabilite_reception, self).create(vals)
        return res


    def write(self, vals):
        self.update_product(vals)
        res = super(is_tracabilite_reception, self).write(vals)
        return res


    def update_product(self, vals):
        if "move_id" in vals:
            obj = self.env['stock.move']
            doc = obj.browse(vals["move_id"])
            product_id=doc.product_id.product_tmpl_id.id
            vals.update({'product_id': product_id})
        return vals


    def imprimer_etiquette_direct(self):
        for obj in self:
            etiquettes=obj.generer_etiquette()
            obj.imprimer_etiquette(etiquettes)


    def generer_etiquette(self):
        for eti in self:
            txt=""
            txt=txt+chr(2)+"qC"+chr(10)
            txt=txt+chr(2)+"qC"+chr(10)
            txt=txt+chr(2)+"n"+chr(10)
            txt=txt+chr(2)+"e"+chr(10)
            txt=txt+chr(2)+"c0000"+chr(10)
            txt=txt+chr(2)+"Kf0000"+chr(10)
            txt=txt+chr(2)+"V0"+chr(10)
            txt=txt+chr(2)+"M0591"+chr(10)
            txt=txt+chr(2)+"L"+chr(10)
            txt=txt+"A2"+chr(10)
            txt=txt+"D11"+chr(10)
            txt=txt+"z"+chr(10)
            txt=txt+"PG"+chr(10)
            txt=txt+"SG"+chr(10)
            txt=txt+"pC"+chr(10)
            txt=txt+"H20"+chr(10)

            txt=txt+datamax(x=15,y=220,sizex=2,sizey=2,txt="ARTICLE:")
            if eti.product_id:
                txt=txt+datamax(x=15,y=200,sizex=3,sizey=4,txt=eti.product_id.name) #.encode("utf-8"))

            if eti.product_id:
                txt=txt+datamax(x=190,y=220,sizex=2,sizey=2,txt="ID:"+str(eti.product_id.id))

            txt=txt+datamax(x=15,y=180,sizex=2,sizey=2,txt="FOURNISSEUR:")
            if eti.picking_id:
                txt=txt+datamax(x=15,y=160,sizex=4,sizey=4,txt=eti.picking_id.partner_id.name) #.encode("utf-8"))

            txt=txt+datamax(x=15,y=140,sizex=2,sizey=2,txt="RECEPTION:")
            if eti.picking_id:
                txt=txt+datamax(x=15,y=120,sizex=4,sizey=4,txt=eti.picking_id.name) #.encode("utf-8"))

            txt=txt+datamax(x=190,y=140,sizex=2,sizey=2,txt="BL FOURNISSEUR:")
            if eti.bl_fournisseur:
                txt=txt+datamax(x=190,y=120,sizex=4,sizey=4,txt=eti.bl_fournisseur) #.encode("utf-8"))

            txt=txt+datamax(x=15,y=100 ,sizex=2,sizey=2,txt="DATE:")
            if eti.move_id:
                txt=txt+datamax(x=15,y=80  ,sizex=4,sizey=4,txt=str(eti.move_id.create_date)[0:10])

            txt=txt+datamax(x=190,y=100 ,sizex=2,sizey=2,txt="LOT:")
            txt=txt+datamax(x=190,y=80  ,sizex=4,sizey=4,txt=eti.name) #.encode("utf-8"))

            txt=txt+"1E1406100060025B"+str(eti.name)+chr(10) # Code barre

            txt=txt+"^01"+chr(10)
            txt=txt+"Q0001"+chr(10)
            txt=txt+"E"+chr(10)
            return txt


    def imprimer_etiquette(self, etiquettes):
        #etiquettes=unicode(etiquettes,'utf-8')
        #etiquettes=etiquettes.encode("windows-1252")
        path="/tmp/etiquette.txt"
        err=""
        fichier = open(path, "w")
        if err=="":
            fichier.write(etiquettes)
            fichier.close()
            user  = self.env['res.users'].browse(self._uid)
            imprimante = user.company_id.is_nom_imprimante or 'Datamax'
            cmd="lpr -h -P"+imprimante+" "+path
            os.system(cmd)


class is_tracabilite_livraison(models.Model):
    _name = 'is.tracabilite.livraison'
    _description = u"Traçabilité livraison"
    _order = "name"
    
    name                    = fields.Char('Numéro de série', required=True, readonly=True, default=" ")
    production_id           = fields.Many2one('mrp.production', 'OF', required=False)
    lot_fabrication         = fields.Integer('Lot de fabrication', default=1)
    product_id              = fields.Many2one('product.template', 'Article', readonly=False)
    fabrique                = fields.Datetime("Produit fabriqué le")
    consomme                = fields.Datetime("Semi-fini consommé le")
    operateur_ids           = fields.Many2many('hr.employee', 'is_tracabilite_livraison_operateur_rel', 'tracabilite_livraison_id', 'employee_id', 'Opérateurs Fabrication')
    sale_id                 = fields.Many2one('sale.order', 'Commande Client')
    move_id                 = fields.Many2one('stock.move', 'Ligne de livraison')
    picking_id              = fields.Many2one('stock.picking', 'Réception', readonly=False)
    quantity                = fields.Float('Quantité')
    livraison               = fields.Datetime("Produit livré le")
    operateur_livraison_ids = fields.Many2many('hr.employee', 'is_tracabilite_livraison_operateur_livraison_rel', 'tracabilite_livraison_id', 'employee_id', 'Opérateurs Livraison')
    etiquette_reception_id  = fields.One2many('is.tracabilite.reception.line', 'livraison_id', 'Etiquettes réception')
    etiquette_livraison_id  = fields.One2many('is.tracabilite.livraison.line', 'livraison_id', 'Etiquettes semi-fini')
    #etiquette_reception     = fields.Many2one('etiquette_reception_id', 'etiquette_id', type='many2one', related='is.tracabilite.reception.line', string='Etiquette réception'),
    #etiquette_livraison     = fields.Many2one('etiquette_livraison_id', 'etiquette_id', type='many2one', related='is.tracabilite.livraison.line', string='Etiquette semi-fini'),


    def ajouter_etiquette_of(self, etiquette, production_id):
        """ Ajouter l'etiquette à la liste des etiquettes de l'OF correspondant """
        if production_id:
            production_obj = self.env['mrp.production']
            productions = production_obj.search([('id','=',production_id)])
            for production in productions:
                ids=[etiquette.id]
                for line in production.etiquette_ids:
                    ids.append(line.id)
                production.write({'etiquette_ids': [(6, 0, ids)]})
        return True
            
        
    @api.model
    def create(self, vals):
        self.update_product(vals)
        vals['name'] = self.env['ir.sequence'].next_by_code('is.tracabilite.livraison')
        res = super(is_tracabilite_livraison, self).create(vals)
        self.ajouter_etiquette_of(res, vals['production_id'])
        return res


    def write(self, vals):
        self.update_product(vals)
        res = super(is_tracabilite_livraison, self).write(vals)
        return res


    def update_product(self, vals):
        print(self)
        if "production_id" in vals:
            obj = self.env['mrp.production']
            doc = obj.browse(vals["production_id"])
            product_id=doc.product_id.product_tmpl_id.id
            vals.update({'product_id': product_id})
        return vals


    # def update_product(self, vals):
    #     if "production_id" in vals:
    #         obj = self.pool.get('mrp.production')
    #         doc = obj.browse(cr, uid, vals["production_id"], context=context)
    #         product_id=doc.product_id.product_tmpl_id.id
    #         vals.update({'product_id': product_id})
    #     return vals


    def imprimer_etiquette_livraison_direct(self):
        for obj in self:
            etiquettes=obj.generer_etiquette_livraison()
            self.env['is.tracabilite.reception'].imprimer_etiquette(etiquettes)


    def generer_etiquette_livraison(self):
        #obj = self.env('is.tracabilite.livraison')
        #eti = obj.browse(cr, uid, ids[0], context)
        for eti in self:
            txt=""
            txt=txt+chr(2)+"qC"+chr(10)
            txt=txt+chr(2)+"qC"+chr(10)
            txt=txt+chr(2)+"n"+chr(10)
            txt=txt+chr(2)+"e"+chr(10)
            txt=txt+chr(2)+"c0000"+chr(10)
            txt=txt+chr(2)+"Kf0000"+chr(10)
            txt=txt+chr(2)+"V0"+chr(10)
            txt=txt+chr(2)+"M0591"+chr(10)
            txt=txt+chr(2)+"L"+chr(10)
            txt=txt+"A2"+chr(10)
            txt=txt+"D11"+chr(10)
            txt=txt+"z"+chr(10)
            txt=txt+"PG"+chr(10)
            txt=txt+"SG"+chr(10)
            txt=txt+"pC"+chr(10)
            txt=txt+"H20"+chr(10)
            txt=txt+datamax(x=15,y=220,sizex=2,sizey=2,txt="ARTICLE:")
            txt=txt+datamax(x=15,y=200,sizex=3,sizey=4,txt=eti.product_id.name) #.encode("utf-8"))
            txt=txt+datamax(x=15,y=180,sizex=2,sizey=2,txt="REF")
            default_code=eti.product_id.default_code or ''
            txt=txt+datamax(x=15,y=160,sizex=4,sizey=4,txt=default_code) #.encode("utf-8"))
            txt=txt+datamax(x=200,y=180,sizex=2,sizey=2,txt="QT:")
            txt=txt+datamax(x=200,y=160,sizex=3,sizey=4,txt=str(eti.lot_fabrication))
            txt=txt+datamax(x=15,y=140 ,sizex=2,sizey=2,txt="DATE:")
            txt=txt+datamax(x=15,y=120  ,sizex=3,sizey=4,txt=str(eti.production_id.date_planned)[0:10])
            txt=txt+datamax(x=120,y=140 ,sizex=2,sizey=2,txt="LOT:")
            txt=txt+datamax(x=120,y=120  ,sizex=3,sizey=4,txt=eti.name) #.encode("utf-8"))
            txt=txt+datamax(x=200,y=140,sizex=2,sizey=2,txt="OF:")
            txt=txt+datamax(x=200,y=120,sizex=3,sizey=4,txt=eti.production_id.name) #.encode("utf-8"))
            t=str(eti.name)
            sizex="3"
            sizey="7"
            x="025"
            y="020"
            txt=txt+"1E1"+sizex+"0"+sizey+"10"+y+"0"+x+"B"+t+chr(10) # Code barre
            txt=txt+"^01"+chr(10)
            txt=txt+"Q0001"+chr(10)
            txt=txt+"E"+chr(10)
            return txt


    def get_picking_id(self, pick_ids):
        if pick_ids:
            return max(pick_ids)
        else:
            return False       


    def get_products_from_move_lines(self, picking):
        products = []
        if picking.move_lines:
            for move in picking.move_lines:
                if move.product_id.id in products:
                    continue
                else:
                    products.append(move.product_id.product_tmpl_id)
        return products


    def verifier_product_etiquette(self, etiquettes, products):
        if etiquettes:
            for etiquette in etiquettes:
                #if etiquette.production_id.product_id.id in products:
                if etiquette.product_id.id in products:
                    continue
                else:
                    return False
        return True


    def livrer_produits(self, picking, etiquettes):
        wiz_obj = self.pool.get('stock.transfer_details')
        """ préparer le contenu de wizard de transfer de stock """
        items = []
        packs = []
        if not picking.pack_operation_ids:
            picking.do_prepare_partial()
        for op in picking.pack_operation_ids:
            etiquette_qty = self.existe_etiquette(cr, uid, etiquettes, op.product_id.id, context)
            if etiquette_qty: 
                item = {
                    'packop_id': op.id,
                    'product_id': op.product_id.id,
                    'product_uom_id': op.product_uom_id.id,
                    'quantity': etiquette_qty,
                    'package_id': op.package_id.id,
                    'lot_id': op.lot_id.id,
                    'sourceloc_id': op.location_id.id,
                    'destinationloc_id': op.location_dest_id.id,
                    'result_package_id': op.result_package_id.id,
                    'date': op.date, 
                    'owner_id': op.owner_id.id,
                }
                if op.product_id:
                    items.append([0, False, item])
                elif op.package_id:
                    packs.append([0, False, item])
        vals = {'picking_id': picking.id,
                'item_ids': items,
                'packop_ids': packs}
        wizard = wiz_obj.create(cr, uid, vals, context=context)
        return wiz_obj.do_detailed_transfer(cr, uid, [wizard], context=context)


    def existe_etiquette(self, etiquettes, product_id):
        lst = self.grouper_etiquettes_product(cr, uid, etiquettes, context)
        for item in lst:
            if item['product_id'] == product_id:
                return item['qty']
            else:
                continue
        return False


    def grouper_etiquettes_product(self, etiquettes):
        lst = []
        for etiquette in etiquettes:
            if not lst:
                lst.append({'product_id': etiquette.production_id.product_id.id, 'qty':etiquette.quantity})
            else:
                item = self.etiquette_in_list(cr, uid, lst, etiquette.production_id.product_id.id, context)
                if item:
                    item['qty'] += etiquette.quantity
                else:
                    lst.append({'product_id': etiquette.production_id.product_id.id, 'qty':etiquette.quantity})
        return lst


    def etiquette_in_list(self, list, product_id):
        for item in list:
            if item['product_id'] == product_id:
                return item
            else:
                continue
        return False


    def lier_etiquettes_mouvement(self, picking, etiquette):
        etiquette_obj = self.pool.get('is.tracabilite.livraison')
        if picking.move_lines:
            for move in picking.move_lines:
                if move.product_id.id == etiquette.production_id.product_id.id:
                    vals={
                        'move_id':move.id,
                        'livraison': time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())
                    }
                    etiquette_obj.write(cr, uid, etiquette.id, vals, context=context)
                else:
                    continue
        return True
                    



class sale_order(models.Model):
    _inherit = "sale.order"


    def act_livraison(self,etiquettes):

        print(self, etiquettes)


        err=""
        for obj in self:
            filtre=[
                ('state'       , 'in' , ['assigned','waiting','confirmed']),
                ('sale_id'        , '=' , obj.id)
            ]
            pickings = self.env['stock.picking'].search(filtre, limit=1)
            for picking in pickings:
                picking.move_line_ids_without_package.unlink()


                lines = self.env['is.tracabilite.livraison'].search([('id', 'in', etiquettes)])
                for line in lines:
                    #line.livraison = 
                      #  'livraison': time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())



                    product = line.product_id
                    vals={
                        "picking_id"        : picking.id,
                        "product_id"        : line.product_id.product_variant_id.id,
                        "company_id"        : picking.company_id.id,
                        "product_uom_id"    : line.product_id.uom_id.id,
                        "location_id"       : picking.location_id.id,
                        "location_dest_id"  : picking.location_dest_id.id,
                        "qty_done"          : 1,
                    }
                    res = self.env['stock.move.line'].create(vals)

                    line.sale_id   = obj.id
                    line.move_id   = res.move_id.id
                    line.livraison = res.move_id.date

                    print("res=",res)
                picking.button_validate()
        return {"err":err,"data":""}


        #     self.livrer_produits(cr, uid, picking, etiquettes, context)
        #     for etiquette in etiquettes:
        #         self.lier_etiquettes_mouvement(cr, uid, picking, etiquette, context)
        #         etiquette_obj.write(cr, uid, etiquette.id, {'sale_id': sale_id})
        #     etiquette_ids = [etiquette.id for etiquette in etiquettes]
        #     err="Commande non livrable"
        # return {"err":err,"data":""}




class is_tracabilite_reception_line(models.Model):
    _name = 'is.tracabilite.reception.line'
    _description = "Traçabilité reception line"
    
    etiquette_id = fields.Many2one('is.tracabilite.reception', 'Etiquettes réception', required=True)
    quantity     = fields.Float('Quantité', required=True, default=1.0)
    livraison_id = fields.Many2one('is.tracabilite.livraison', 'Etiquette livraison')
    

class is_tracabilite_livraison_line(models.Model):
    _name = 'is.tracabilite.livraison.line'
    _description = "Traçabilité livraison line"
    
    etiquette_id = fields.Many2one('is.tracabilite.livraison', 'Etiquettes semi-fini', required=True)
    quantity     = fields.Float('Quantité', required=True, default=1.0)
    livraison_id = fields.Many2one('is.tracabilite.livraison', 'Etiquette livraison')
    





        
