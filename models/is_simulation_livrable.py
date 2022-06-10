# -*- coding: utf-8 -*-
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


        # 'move_lines': fields.one2many('stock.move', 'raw_material_production_id', 'Products to Consume',
        #     domain=[('state', 'not in', ('done', 'cancel'))], readonly=True, states={'draft': [('readonly', False)]}),
        # 'move_lines2': fields.one2many('stock.move', 'raw_material_production_id', 'Consumed Products',
        #     domain=[('state', 'in', ('done', 'cancel'))], readonly=True),




    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.simulation.livrable')
        res = super(is_simulation_livrable, self).create(vals)
        return res


    def bom(self, demande, niv, product, qt):
        print(demande,niv,"-"*niv,qt,product,product.name)
        vals = {
            'simulation_id': self.id,
            'demande_id'   : demande.id,
            'niv'          : niv,
            'niv_txt'      : "-"*niv,
            'product_id'   : product.id,
            'qt'           : qt,
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
                self.bom(demande,niv,line.product_id,qt*line.product_qty)


    # TODO : 
    # - Tenir compte du stock ou du stock prévu (en multi-nivaux et ne compter le stock qu'un fois...)
    # - Eclater la nomenlcatue sulment si c'est un produit à fabricque
    # - Regrouper les besoins => Ajouter le stock sur chaque article et recalculaer en négatif les besoins sur les articles à fabriquer 
    # - Indiquer les alertes demandées dans le CDC
    # - Il faut peur-être faire un regroupement des besoins pour cahque niveau de nomenlcatue
    # -- Regrouper les besoins du premeure niveau  => Tenir compte du stock
    # -- Regrouper les besoins du niveau suivant tant qu'il y a des nomenlcatues à traiter
    # -- Il ne faut donc pas faire du récurif mais un traitement niveau par niveaux x fois (10 niveux maxi)


    def calcul_besoins_action(self):
        for obj in self:
            print(obj)
            filtre=[
                ('simulation_id', '=' , obj.id),
                ('type_ligne'   , '!=' , 'demande')
            ]
            self.env['is.simulation.livrable.ligne'].search(filtre).unlink()

            niv=1
            for demande in obj.demande_ids:
                self.bom(demande,niv,demande.product_id,demande.qt)


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
    qt            = fields.Float("Quantité")
    type_ligne    = fields.Selection([
            ('demande'        , 'Demande'),
            ('besoin_detaille', 'Besoin détaillé'),
            ('besoin_regroupe', 'Besoin regroupé'),
        ], "Type", default="demande", required=True)


