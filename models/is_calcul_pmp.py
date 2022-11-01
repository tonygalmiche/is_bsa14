# -*- coding: utf-8 -*-
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
    stock_category_id = fields.Many2one('is.stock.category', 'Catégorie de stock')
    product_id        = fields.Many2one('product.product', 'Article')
    date_creation     = fields.Date("Date de création"                 , required=True, default=lambda *a: fields.Date.today())
    createur_id       = fields.Many2one('res.users', 'Créateur'        , required=True, default=lambda self: self.env.user.id)
    move_ids          = fields.One2many('is.calcul.pmp.move'   , 'calcul_id', 'Mouvements de stocks')
    product_ids       = fields.One2many('is.calcul.pmp.product', 'calcul_id', 'Articles')


                        # <button name="extraire_mouvement_action" type="object" string="Extraire les mouvements"/>
                        # <button name="calcul_stock_date_action"  type="object" string="Calculer stock à date et période PMP"/>
                        # <button name="calcul_pmp_action"         type="object" string="Calculer le PMP"/>
                        # <button name="%(is_calcul_pmp_move_action)d"    type="action" string="Voir les mouvements"/>
                        # <button name="%(is_calcul_pmp_product_action)d" type="action" string="Voir les articles"/>



    def get_products(self):
        for obj in self:
            filtre=[('purchase_ok', '=', True)]
            if obj.stock_category_id:
                filtre.append(('is_stock_category_id', '=', obj.stock_category_id.id))
            if obj.product_id:
               filtre.append(('id', '=', obj.product_id.id))
            products=self.env['product.product'].search(filtre)
        return products



    def extraire_mouvement_action(self):
        cr=self._cr
        for obj in self:
            obj.move_ids.unlink()
            obj.product_ids.unlink()
            # filtre=[('purchase_ok', '=', True)]
            # if obj.stock_category_id:
            #     filtre.append(('is_stock_category_id', '=', obj.stock_category_id.id))
            # if obj.product_id:
            #    filtre.append(('id', '=', obj.product_id.id))
            # products=self.env['product.product'].search(filtre)

            products = obj.get_products()


            nb=len(products)
            ct=1
            for product in products:
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
                        (location_id=%s or location_dest_id=%s) and  
                        date>='2021-01-01'
                    ORDER BY date desc
                """
                cr.execute(SQL,[product.id, obj.location_id.id, obj.location_id.id])
                for row in cr.fetchall():
                    qt           = row[2]
                    price_unit   = row[6] or 0.0
                    picking_id   = row[8]
                    inventory_id = row[10]
                    if row[3]==obj.location_id.id:
                        qt=-qt
                    if not picking_id:
                        price_unit=0
                    if obj.inventory_id.id==inventory_id:
                        price_unit  = product.is_pmp_odoo8 or 0.0

                        print("test", price_unit)


                    vals = {
                        'calcul_id'       : obj.id,
                        'product_id'      : product.id,
                        'date'            : row[1],
                        'product_uom_qty' : qt,
                        'location_id'     : row[3],
                        'location_dest_id': row[4],
                        'product_uom'     : row[5],
                        'price_unit'      : price_unit,
                        'origin'          : row[7],
                        'picking_id'      : picking_id,
                        'move_id'         : row[9],
                        'inventory_id'    : inventory_id,
                        'reference'       : row[11],
                    }
                    id = self.env['is.calcul.pmp.move'].create(vals)
                _logger.info("%s/%s : %s (id=%s))", ct,nb, product.name, product.id)
                ct+=1



    def calcul_stock_date_action(self):
        for obj in self:
            products = obj.get_products()
            nb=len(products)
            ct=1
            for product in products:
                stock_actuel = product.qty_available
                stock_date   = stock_actuel
                stock_date_limite = 0
                periode_pmp=False
                stock0=False
                filtre=[
                    ('calcul_id', '=', obj.id),
                    ('product_id', '=', product.id),
                ]
                moves=self.env['is.calcul.pmp.move'].search(filtre, order="date desc, id desc")
                for move in moves:
                    qt = move.product_uom_qty
                    if (stock_date)<0.01:
                        stock0=True
                    if move.date.date()<obj.date_limite:
                        periode_pmp=True
                    if stock0:
                        periode_pmp=False
                    vals = {
                        'stock_date' : stock_date,
                        'periode_pmp': periode_pmp,
                     }
                    move.write(vals)
                    stock_date-=qt
                _logger.info(u"%s/%s calcul_stock_date_action : %s (id=%s))", ct,nb, product.name, product.id)
                ct+=1


    def calcul_pmp_action(self):
        for obj in self:
            obj.product_ids.unlink()
            products = obj.get_products()
            nb=len(products)
            ct=1
            for product in products:
                stock_actuel = product.qty_available
                stock_date_limite = pmp = price_unit = last = mini = maxi = nb_rcp = total_qt = total_montant = 0
                prix_moyen = 0
                filtre=[
                    ('calcul_id'  , '=', obj.id),
                    ('product_id' , '=', product.id),
                    ('periode_pmp', '=', True),
                ]
                moves=self.env['is.calcul.pmp.move'].search(filtre, order="date, id")
                for move in moves:
                    qt = move.product_uom_qty
                    qt_rcp=montant_rcp=montant_pmp=0


#                    if obj.inventory_id.id==inventory_id:


                    if move.picking_id or obj.inventory_id==move.inventory_id:
                        price_unit  = move.price_unit
                        if price_unit>0 and move.stock_date>0:
                            if pmp==0:
                                pmp = price_unit
                            else:
                                pmp = ((move.stock_date - qt)*pmp + qt*price_unit)/move.stock_date
                            last_pmp=pmp
                        nb_rcp+=1
                        total_qt+=qt
                        last = price_unit
                        if price_unit>0 and (price_unit<mini or mini==0):
                            mini = price_unit
                        if price_unit>maxi:
                            maxi=price_unit
                        qt_rcp      = move.product_uom_qty
                        montant_rcp = qt_rcp * price_unit
                        total_montant+=montant_rcp
                    montant_pmp = pmp*move.stock_date
                    vals = {
                        'pmp'        : pmp,
                        'montant_pmp': montant_pmp,
                        'qt_rcp'     : qt_rcp,
                        'montant_rcp': montant_rcp,
                     }
                    move.write(vals)
                    stock_date_limite = move.stock_date

                if total_qt>0:
                    prix_moyen = total_montant/total_qt
                stock_valorise_pmp = stock_date_limite*pmp
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
                    'prix_moyen'        : prix_moyen,
                    'stock_date_limite' : stock_date_limite,
                    'stock_actuel'      : stock_actuel,
                    'stock_valorise_last' : stock_date_limite*last,
                    'stock_valorise_moyen': stock_date_limite*prix_moyen,
                    'stock_valorise_pmp'  : stock_date_limite*pmp,
                }
                id = self.env['is.calcul.pmp.product'].create(vals)
                _logger.info(u"%s/%s calcul_pmp_action : %s (id=%s)(pmp=%s))", ct,nb, product.name, product.id,pmp)
                ct+=1




    # def calcul_pmp_action(self):
    #     cr=self._cr
    #     for obj in self:
    #         obj.move_ids.unlink()
    #         obj.product_ids.unlink()
    #         filtre=[('purchase_ok', '=', True)]
    #         if obj.stock_category_id:
    #             filtre.append(('is_stock_category_id', '=', obj.stock_category_id.id))
    #         if obj.product_id:
    #            filtre.append(('id', '=', obj.product_id.id))
    #         products=self.env['product.product'].search(filtre)
    #         nb=len(products)
    #         ct=1
    #         for product in products:
    #             mini=maxi=last=nb_rcp=total_qt=total_montant=0
    #             stock_actuel = product.qty_available
    #             stock_date   = stock_actuel
    #             stock_date_limite = 0
    #             SQL="""
    #                 SELECT 
    #                     product_id,
    #                     date,
    #                     product_uom_qty,
    #                     location_id,
    #                     location_dest_id,
    #                     product_uom,
    #                     price_unit,
    #                     origin,
    #                     picking_id,
    #                     id,
    #                     inventory_id,
    #                     reference
    #                 FROM stock_move
    #                 WHERE 
    #                     product_id=%s and 
    #                     state='done' and
    #                     (location_id=%s or location_dest_id=%s) and  
    #                     date>='2021-01-01'
    #                 ORDER BY date desc
    #             """
    #             cr.execute(SQL,[product.id, obj.location_id.id, obj.location_id.id])
    #             for row in cr.fetchall():
    #                 if row[1].date()<=obj.date_limite and stock_date_limite==0:
    #                     stock_date_limite=stock_date
    #                 qt = row[2]
    #                 if row[3]==obj.location_id.id:
    #                     qt=-qt
    #                 price_unit = row[6] or 0.0

    #                 picking_id   = row[8]
    #                 inventory_id = row[10]
    #                 qt_rcp=montant_rcp=0
    #                 periode_pmp=False
    #                 test=False
    #                 if obj.inventory_id.id==inventory_id:
    #                     price_unit  = product.is_pmp_odoo8 or 0.0
    #                     test=True
    #                 if picking_id:
    #                     test=True
    #                 if test and row[1].date()<=obj.date_limite and price_unit>0.0:
    #                     qt_rcp      = qt
    #                     montant_rcp = qt_rcp*price_unit
    #                     nb_rcp+=1
    #                     if last==0 and price_unit>0:
    #                         last=price_unit
    #                     total_qt+=qt
    #                     total_montant+=qt*price_unit
    #                     if mini>price_unit or mini==0:
    #                         mini=price_unit
    #                     if price_unit>maxi:
    #                         maxi=price_unit

    #                 if row[1].date()<=obj.date_limite:
    #                     periode_pmp=True


    #                 vals = {
    #                     'calcul_id'       : obj.id,
    #                     'product_id'      : product.id,
    #                     'date'            : row[1],
    #                     'product_uom_qty' : qt,
    #                     'location_id'     : row[3],
    #                     'location_dest_id': row[4],
    #                     'stock_date'      : stock_date,
    #                     'product_uom'     : row[5],
    #                     'price_unit'      : price_unit,
    #                     'qt_rcp'          : qt_rcp,
    #                     'montant_rcp'     : montant_rcp,
    #                     'periode_pmp'     : periode_pmp,
    #                     'origin'          : row[7],
    #                     'picking_id'      : picking_id,
    #                     'move_id'         : row[9],
    #                     'inventory_id'    : inventory_id,
    #                     'reference'       : row[11],
    #                 }
    #                 id = self.env['is.calcul.pmp.move'].create(vals)
    #                 stock_date-=qt

    #                 if stock_date<0.01:
    #                     break
    #             pmp=0
    #             if total_qt>0:
    #                 pmp=total_montant/total_qt
    #             vals = {
    #                 'calcul_id'    : obj.id,
    #                 'product_id'   : product.id,
    #                 'last'         : last,
    #                 'mini'         : mini,
    #                 'maxi'         : maxi,
    #                 'nb_rcp'       : nb_rcp,
    #                 'total_qt'     : total_qt,
    #                 'total_montant': total_montant,
    #                 'pmp'          : pmp,
    #                 'stock_date_limite': stock_date_limite,
    #                 'stock_actuel'     : stock_actuel,
    #             }
    #             id = self.env['is.calcul.pmp.product'].create(vals)
    #             _logger.info("%s/%s : pmp=%s : %s (id=%s))", ct,nb,round(pmp,2), product.name, product.id)
    #             ct+=1




class is_calcul_pmp_product(models.Model):
    _name = 'is.calcul.pmp.product'
    _description = "Articles calcul PMP"
    _order='product_id'

    calcul_id     = fields.Many2one('is.calcul.pmp', 'Calcul PMP', required=True, index=True)
    product_id    = fields.Many2one('product.product', 'Article', required=True, index=True)
    stock_category_id = fields.Many2one('is.stock.category', string='Catégorie de stock', related='product_id.is_stock_category_id' )
    last          = fields.Float("Dernier prix")
    mini          = fields.Float("Prix mini")
    maxi          = fields.Float("Prix maxi")
    nb_rcp        = fields.Float("Nb réceptions")
    total_qt      = fields.Float("Quantité réceptionnée")
    total_montant = fields.Float("Montant")
    pmp           = fields.Float("PMP")

    prix_moyen         = fields.Float(u"Prix moyen")
    stock_actuel       = fields.Float(u"Stock actuel")
    stock_date_limite  = fields.Float(u"Stock date limite")

    stock_valorise_last  = fields.Float(u"Stock valorisé au dernier prix")
    stock_valorise_moyen = fields.Float(u"Stock valorisé au prix moyen")
    stock_valorise_pmp   = fields.Float(u"Stock valorisé au PMP")




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

    qt_rcp           = fields.Float("Qt Rcp")
    montant_rcp      = fields.Float("Montant Rcp")
    pmp              = fields.Float("PMP")
    montant_pmp      = fields.Float("Montant PMP à date")
    periode_pmp      = fields.Boolean("Période PMP", help="Ce mouvement est compris dans le caclul du PMP")

    origin           = fields.Char("Origine")
    reference        = fields.Char("Référence")
    picking_id       = fields.Many2one('stock.picking', 'Picking')
    inventory_id     = fields.Many2one('stock.inventory', 'Inventaire')
    move_id          = fields.Many2one('stock.move', 'Mouvement')


