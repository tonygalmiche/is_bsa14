# -*- coding: utf-8 -*-
from odoo import models,fields,api
from datetime import datetime, timedelta, date


class is_inventaire_tournant(models.Model):
    _name = "is.inventaire.tournant"
    _inherit = ['mail.thread']
    _description = "Inventaire tournant"
    _order='name desc'

    name               = fields.Char("N°", readonly=True, tracking=True)
    stock_category_ids = fields.Many2many('is.stock.category', 'is_inventaire_tournant_stock_category_rel', 'inventaire_id', 'stock_category_id', 'Catégorie de stock', required=True)
    location_id        = fields.Many2one('stock.location', "Emplacement à inventorier", readonly=True)
    location_dest_id   = fields.Many2one('stock.location', "Emplacement d'inventaire" , readonly=True)
    ligne_ids          = fields.One2many('is.inventaire.tournant.ligne' , 'inventaire_id', 'Lignes')
    saisie_ids         = fields.One2many('is.inventaire.tournant.saisie', 'inventaire_id', 'Saisies')
    state              = fields.Selection([
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
    ], "État", default='encours', copy=False, tracking=True)


    @api.model
    def create(self, vals):
        location_id      = self.env['stock.location'].search([('usage', '=', 'internal')],limit=1)[0].id
        location_dest_id = self.env['stock.location'].search([('usage', '=', 'inventory'),('scrap_location', '=', False)],limit=1)[0].id
        vals['location_id']      = location_id
        vals['location_dest_id'] = location_dest_id
        vals['name'] = self.env['ir.sequence'].next_by_code('is.inventaire.tournant')
        res = super(is_inventaire_tournant, self).create(vals)
        return res


    def recherche_article_action(self):
        for obj in self:
            obj.ligne_ids.unlink()
            for line in obj.stock_category_ids:
                domain=[
                    ('is_stock_category_id'   ,'=', line.id),
                    ('is_frequence_inventaire','>',0),
                ]
                products = self.env['product.product'].search(domain,order="name")
                for product in products:
                    test=True
                    if product.is_date_inventaire and product.is_frequence_inventaire:
                        date_limite =  product.is_date_inventaire + timedelta(days=product.is_frequence_inventaire*30) 
                        if date_limite>=date.today():
                            test=False
                    if test:
                        #** Recherche stock article *******************************
                        domain=[
                            ('product_id' ,'=', product.id),
                            ('location_id','=',obj.location_id.id),
                        ]
                        quants = self.env['stock.quant'].search(domain)
                        qt=0
                        for quant in quants:
                            qt+=quant.quantity
                        #**********************************************************
                        vals={
                            'inventaire_id'    : obj.id,
                            'product_id'       : product.id,
                            'stock_category_id': product.is_stock_category_id.id,
                            'designation'      : product.name,
                            'reference'        : product.default_code,
                            'qt_theorique'     : qt,
                            'qt_comptee'       : qt,
                        }
                        self.env['is.inventaire.tournant.ligne'].create(vals)


    def voir_lignes_action(self):
        for obj in self:
            return {
                "name": 'Lignes',
                "view_mode": "tree",
                "res_model": "is.inventaire.tournant.ligne",
                "domain": [
                    ("inventaire_id" ,"=",obj.id),
                ],
                "type": "ir.actions.act_window",
            }


    def voir_saisies_action(self):
        for obj in self:
            return {
                "name": 'Saisies',
                "view_mode": "tree",
                "res_model": "is.inventaire.tournant.saisie",
                "domain": [
                    ("inventaire_id" ,"=",obj.id),
                ],
                "type": "ir.actions.act_window",
                'context': {'default_inventaire_id': obj.id }
            }


    def actualiser_lignes_action(self):
        for obj in self:
            mydict={}
            for saisie in obj.saisie_ids:
                if saisie.product_id not in mydict:
                    mydict[saisie.product_id] = 0
                mydict[saisie.product_id]+=saisie.quantite
            for ligne in obj.ligne_ids:
                if ligne.product_id in mydict:
                    ligne.qt_comptee = mydict[ligne.product_id]
            
    
    def voir_mouvements_action(self):
        view_id = self.env['ir.model.data'].get_object_reference('is_bsa14', 'is_view_move_tree')[1]
        for obj in self:
            ids=[]
            for line in obj.ligne_ids:
                if line.move_id:
                    ids.append(line.move_id.id)
            return {
                "name": obj.name,
                "view_mode": "tree,form",
                "res_model": "stock.move",
                "domain": [
                    ("id" ,"in",ids),
                ],
                "type": "ir.actions.act_window",
                'views': [(view_id, 'tree'),(False, 'form')],
            }


    def valider_inventaire_action(self):
        for obj in self:
            for line in obj.ligne_ids:
                line.product_id.is_date_inventaire = date.today()   
                if line.ecart!=0:
                    line.correction_stock_action()
            obj.state='termine'


class is_inventaire_tournant_ligne(models.Model):
    _name = "is.inventaire.tournant.ligne"
    _description = "Lignes inventaire tournant"
    _order='designation'

    inventaire_id     = fields.Many2one('is.inventaire.tournant', 'Inventaire', required=True, ondelete='cascade')
    product_id        = fields.Many2one('product.product', 'Article', required=True)
    reference         = fields.Char("Référence"  , readonly=True)
    designation       = fields.Char("Désignation", readonly=True)
    stock_category_id = fields.Many2one('is.stock.category', "Catégorie stock", readonly=True)
    qt_theorique      = fields.Float("Quantité théorique", digits='Product Unit of Measure')
    qt_comptee        = fields.Float("Quantité comptée"  , digits='Product Unit of Measure')
    ecart             = fields.Float("Écart"             , digits='Product Unit of Measure', store=True, readonly=True, compute='_compute_ecart')
    state             = fields.Selection(related="inventaire_id.state")
    date_inventaire   = fields.Date(related="product_id.is_date_inventaire")
    move_id           = fields.Many2one('stock.move', 'Mouvement', readonly=True)



    @api.depends('qt_theorique','qt_comptee')
    def _compute_ecart(self):
        for obj in self:
            ecart =  obj.qt_comptee - obj.qt_theorique
            obj.ecart = ecart
 


    def enlever_article_action(self):
        for obj in self:
            obj.product_id.is_frequence_inventaire = 0
            obj.unlink()



    def correction_stock_action(self):
        for obj in self:
            if obj.ecart>0:
                ecart            = obj.ecart
                location_id      = obj.inventaire_id.location_dest_id.id
                location_dest_id = obj.inventaire_id.location_id.id
            else:
                ecart            = -obj.ecart
                location_id      = obj.inventaire_id.location_id.id
                location_dest_id = obj.inventaire_id.location_dest_id.id
            reference="Inventaire tournant %s du %s"%(obj.inventaire_id.name, str(obj.inventaire_id.create_date)[0:10])
            vals={
                "product_id": obj.product_id.id,
                "product_uom": obj.product_id.uom_id.id,
                "location_id": location_id,
                "location_dest_id": location_dest_id,
                "origin": reference,
                "name": reference,
                "reference": reference,
                "product_uom_qty": ecart,
                "scrapped": False,
                "propagate_cancel": True,
                "additional": False,
            }
            move=self.env['stock.move'].create(vals)
            vals={
                "move_id": move.id,
                "product_id": obj.product_id.id,
                "product_uom_id": obj.product_id.uom_id.id,
                "location_id": location_id,
                "location_dest_id": location_dest_id,
                "qty_done": ecart,
                "reference": reference,
            }
            self.env['stock.move.line'].create(vals)
            move._action_done()
            obj.move_id = move.id





class is_inventaire_tournant_saisie(models.Model):
    _name = "is.inventaire.tournant.saisie"
    _description = "Saisies pour inventaire tournant"
    _order='product_id'

    inventaire_id = fields.Many2one('is.inventaire.tournant', 'Inventaire', required=True, ondelete='cascade')
    product_id    = fields.Many2one('product.product', 'Article', required=True)
    quantite      = fields.Float("Quantité", digits='Product Unit of Measure')


