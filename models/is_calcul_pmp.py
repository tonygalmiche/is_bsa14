# -*- coding: utf-8 -*-
from functools import total_ordering
from itertools import product
from odoo import models,fields,api
import datetime
import logging
_logger = logging.getLogger(__name__)



class is_calcul_pmp(models.Model):
    _name='is.calcul.pmp'
    _description = "Calcul PMP"
    _order='date_creation desc'
    _rec_name = 'date_creation'


    location_id       = fields.Many2one('stock.location', 'Emplacement', required=True)
    inventory_id      = fields.Many2one('stock.inventory', 'Inventaire initial pour PMP Odoo 8', required=True)
    date_limite       = fields.Date("Date de fin", help="Calcul du PMP à cette date de fin", required=True, default=lambda *a: fields.Date.today())
    date_debut        = fields.Date("Export des mouvements depuis cette date de début sans calculer le PMP")
    stock_category_id = fields.Many2one('is.stock.category', 'Catégorie de stock')
    product_id        = fields.Many2one('product.product', 'Article')
    date_creation     = fields.Date("Date de création"                 , required=True, default=lambda *a: fields.Date.today())
    createur_id       = fields.Many2one('res.users', 'Créateur'        , required=True, default=lambda self: self.env.user.id)
    move_ids          = fields.One2many('is.calcul.pmp.move'   , 'calcul_id', 'Mouvements de stocks')
    product_ids       = fields.One2many('is.calcul.pmp.product', 'calcul_id', 'Articles')


    def calcul_pmp_action(self):
        cr=self._cr
        for obj in self:
            obj.move_ids.unlink()
            obj.product_ids.unlink()
            filtre=[('purchase_ok', '=', True)]
            if obj.stock_category_id:
                filtre.append(('is_stock_category_id', '=', obj.stock_category_id.id))
            if obj.product_id:
               filtre.append(('id', '=', obj.product_id.id))
            products=self.env['product.product'].search(filtre)
            nb=len(products)
            ct=1
            for product in products:
                mini=maxi=last=nb_rcp=total_qt=total_montant=0
                stock_actuel = product.qty_available
                stock_date   = stock_actuel
                stock_date_limite = 0
                SQL="""
                    SELECT 
                        product_id,
                        date,
                        product_uom_qty,
                        location_id,
                        location_dest_id,
                        product_uom,
                        price_unit,
                        origin,
                        picking_id,
                        id,
                        inventory_id,
                        reference
                    FROM stock_move
                    WHERE 
                        product_id=%s and 
                        state='done' and
                        (location_id=%s or location_dest_id=%s)
                """
                if obj.date_debut:
                    SQL+=" and  date>=%s"
                SQL+="ORDER BY date desc"

                if obj.date_debut:
                    cr.execute(SQL,[product.id, obj.location_id.id, obj.location_id.id, obj.date_debut])
                else:
                    cr.execute(SQL,[product.id, obj.location_id.id, obj.location_id.id])



                for row in cr.fetchall():
                    if row[1].date()<=obj.date_limite and stock_date_limite==0:
                        stock_date_limite=stock_date
                    qt = row[2]
                    if row[3]==obj.location_id.id:
                        qt=-qt
                    price_unit = row[6] or 0.0

                    picking_id   = row[8]
                    inventory_id = row[10]
                    test=False
                    if obj.inventory_id.id==inventory_id:
                        price_unit = product.is_pmp_odoo8 or 0.0
                        test=True
                    if picking_id:
                        test=True
                    if test and row[1].date()<=obj.date_limite and price_unit>0.0:
                        nb_rcp+=1
                        if last==0 and price_unit>0:
                            last=price_unit
                        total_qt+=qt
                        total_montant+=qt*price_unit
                        if mini>price_unit or mini==0:
                            mini=price_unit
                        if price_unit>maxi:
                            maxi=price_unit
                    vals = {
                        'calcul_id'       : obj.id,
                        'product_id'      : product.id,
                        'date'            : row[1],
                        'product_uom_qty' : qt,
                        'location_id'     : row[3],
                        'location_dest_id': row[4],
                        'stock_date'      : stock_date,
                        'product_uom'     : row[5],
                        'price_unit'      : price_unit,
                        'origin'          : row[7],
                        'picking_id'      : picking_id,
                        'move_id'         : row[9],
                        'inventory_id'    : inventory_id,
                        'reference'       : row[11],
                    }
                    id = self.env['is.calcul.pmp.move'].create(vals)
                    stock_date-=qt

                    if not obj.date_debut:
                        if stock_date<0.01:
                            break
                pmp=0
                if total_qt>0:
                    pmp=total_montant/total_qt
                vals = {
                    'calcul_id'    : obj.id,
                    'product_id'   : product.id,
                    'last'         : last,
                    'mini'         : mini,
                    'maxi'         : maxi,
                    'nb_rcp'       : nb_rcp,
                    'total_qt'     : total_qt,
                    'total_montant': total_montant,
                    'pmp'          : pmp,
                    'stock_date_limite': stock_date_limite,
                    'stock_actuel'     : stock_actuel,
                }
                id = self.env['is.calcul.pmp.product'].create(vals)
                _logger.info("%s/%s : pmp=%s : %s (id=%s))", ct,nb,round(pmp,2), product.name, product.id)
                ct+=1




class is_calcul_pmp_product(models.Model):
    _name = 'is.calcul.pmp.product'
    _description = "Articles calcul PMP"
    _order='product_id'

    calcul_id     = fields.Many2one('is.calcul.pmp', 'Calcul PMP', required=True, index=True)
    product_id    = fields.Many2one('product.product', 'Article', required=True, index=True)
    last          = fields.Float("Dernier prix")
    mini          = fields.Float("Prix mini")
    maxi          = fields.Float("Prix maxi")
    nb_rcp        = fields.Float("Nb réceptions")
    total_qt      = fields.Float("Quantité réceptionnée")
    total_montant = fields.Float("Montant")
    pmp           = fields.Float("PMP")
    stock_date_limite = fields.Float("Stock date limite")
    stock_actuel      = fields.Float("Stock actuel")


    def liste_mouvements_action(self):
        for obj in self: 
            return {
                "name": "Mouvements "+obj.product_id.name,
                "view_mode": "tree,form",
                "res_model": "is.calcul.pmp.move",
                "domain": [
                    ("calcul_id" ,"=",obj.calcul_id.id),
                    ("product_id","=",obj.product_id.id),
                ],
                "type": "ir.actions.act_window",
            }





class is_calcul_pmp_move(models.Model):
    _name = 'is.calcul.pmp.move'
    _description = "Mouvements calcul PMP"
    _order='product_id,date desc'

    calcul_id        = fields.Many2one('is.calcul.pmp', 'Calcul PMP', required=True, index=True)
    product_id       = fields.Many2one('product.product', 'Article', required=True, index=True)
    date             = fields.Datetime("Date", index=True)
    product_uom_qty  = fields.Float("Quantité")
    location_id      = fields.Many2one('stock.location', 'Emplacement source')
    location_dest_id = fields.Many2one('stock.location', 'Emplacement destination')
    stock_date       = fields.Float("Stock à date")
    product_uom      = fields.Many2one('uom.uom', 'Unité')
    price_unit       = fields.Float("Prix")
    origin           = fields.Char("Origine")
    reference        = fields.Char("Référence")
    picking_id       = fields.Many2one('stock.picking', 'Picking')
    inventory_id     = fields.Many2one('stock.inventory', 'Inventaire')
    move_id          = fields.Many2one('stock.move', 'Mouvement')



