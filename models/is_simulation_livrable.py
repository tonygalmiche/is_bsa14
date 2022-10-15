# -*- coding: utf-8 -*-
from email.policy import default
from itertools import product
from odoo import models,fields,api
import datetime
from odoo.exceptions import Warning
import unicodedata


class is_simulation_livrable(models.Model):
    _name='is.simulation.livrable'
    _description='Simulation livrable vente'
    _order='name desc'

    name          = fields.Char("N°", readonly=True)
    commentaire   = fields.Text("Commentaire")
    createur_id   = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    demande_ids   = fields.One2many('is.simulation.livrable.ligne', 'simulation_id', 'Lignes', copy=True, domain=[('type_ligne', '=', 'demande')])
    type_stock    = fields.Selection([
        ('sans_stock' , 'Sans stock'),
        ('stock_reel' , 'Stock réel'),
        ('stock_prevu', 'Stock prévu'),
    ], "Type de stock", required=True, default="stock_reel")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.simulation.livrable')
        res = super(is_simulation_livrable, self).create(vals)
        return res


    def bom(self, demande, niv, product, qt, type_stock, stocks={}):
        if product not in stocks:
            val=0
            if type_stock=="stock_reel":
                val=product.qty_available
            if type_stock=="stock_prevu":
                val=product.virtual_available
            stocks[product]=val
        stock = stocks[product]
        besoin = qt-stock
        if besoin<0:
            besoin=0
        reste = stocks[product] - qt
        if reste<0:
            reste=0
        stocks[product]=reste
        vals = {
            'simulation_id': self.id,
            'demande_id'   : demande.id,
            'niv'          : niv,
            'niv_txt'      : "-"*niv,
            'product_id'   : product.id,
            'demande'      : qt,
            'stock'        : stock,
            'besoin'       : besoin,
            'type_ligne'   : 'besoin_detaille',
        }
        res = self.env['is.simulation.livrable.ligne'].create(vals)
        filtre=[
            ('product_tmpl_id', '=' , product.product_tmpl_id.id),
        ]
        boms = self.env['mrp.bom'].search(filtre, limit=1)
        for bom in boms:
            niv+=1
            for line in bom.bom_line_ids:
                stocks = self.bom(demande,niv,line.product_id,besoin*line.product_qty, type_stock, stocks)
        return stocks


    # TODO : 
    # - Tenir compte du stock ou du stock prévu (en multi-nivaux et ne compter le stock qu'un fois...)


    def calcul_besoins_action(self):
        for obj in self:
            filtre=[
                ('simulation_id', '=' , obj.id),
                ('type_ligne'   , '!=' , 'demande')
            ]
            self.env['is.simulation.livrable.ligne'].search(filtre).unlink()
            niv=1
            for demande in obj.demande_ids:
                self.bom(demande,niv,demande.product_id,demande.demande, obj.type_stock)

            #** regroupement des besoins **************************************
            filtre=[
                ("simulation_id", "=", obj.id),
                ("type_ligne"   , "=", "besoin_detaille"),
            ]
            lines = self.env['is.simulation.livrable.ligne'].search(filtre)
            products={}
            for line in lines:
                if line.product_id not in products:
                    products[line.product_id]=0

                products[line.product_id]+=line.besoin
            for product in products:
                besoin = products[product]
                if besoin>0:
                    vals = {
                        'simulation_id': self.id,
                        'product_id'   : product.id,
                        'besoin'       : besoin,
                        'type_ligne'   : 'besoin_regroupe',
                    }
                    res = self.env['is.simulation.livrable.ligne'].create(vals)


class is_simulation_livrable_ligne(models.Model):
    _name='is.simulation.livrable.ligne'
    _description='Lignes simulation livrable vente'
    _order='simulation_id,id'
    _rec_name = 'product_id'

    simulation_id = fields.Many2one('is.simulation.livrable', 'Simulation', required=True, ondelete='cascade')
    demande_id    = fields.Many2one('is.simulation.livrable.ligne', 'Origine')
    niv           = fields.Char("Niv")
    niv_txt       = fields.Char("-")
    product_id    = fields.Many2one('product.product', 'Article', required=True)
    simulation_livrable = fields.Boolean('Simulation livrable', related="product_id.is_simulation_livrable")
    demande       = fields.Float("Demande", help="Demande initiale")
    stock         = fields.Float("Stock"  , help="Stock restant")
    besoin        = fields.Float("Besoin" , help="Demande - Stock" )
    type_ligne    = fields.Selection([
            ('demande'        , 'Demande'),
            ('besoin_detaille', 'Besoin détaillé'),
            ('besoin_regroupe', 'Besoin regroupé'),
        ], "Type", default="demande", required=True)


