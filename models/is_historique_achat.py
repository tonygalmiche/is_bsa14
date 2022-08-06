# -*- coding: utf-8 -*-
from itertools import product
from odoo import models,fields,api
import datetime


class is_historique_achat(models.Model):
    _name='is.historique.achat'
    _description='Historique des achats'
    _order='famille_id'
    _rec_name = 'famille_id'

    famille_id = fields.Many2one('is.famille', 'Famille', required=True)

    def actualiser_action(self):
        for obj in self:
            print(obj)

            annees=self.env['is.annee'].search([])
            for line in annees:
                products=self.env['product.product'].search([('is_famille_id', '=', obj.famille_id.id)])
                for product in products:


                    historiques=self.env['is.historique.achat.annee'].search([('annee', '=', line.annee),('product_id', '=', product.id)])
                    print(historiques)
                    if len(historiques)==0:
                        vals={
                            "product_id": product.id,
                            "annee"     : line.annee
                        }
                        self.env['is.historique.achat.annee'].create(vals)



class is_historique_achat_annee(models.Model):
    _name = 'is.historique.achat.annee'
    _description = "Historique des achats - Années"
    _order='annee desc, product_id'
    _rec_name = 'annee'

    annee                   = fields.Char("Année", required=True, index=True)
    product_id              = fields.Many2one('product.product', 'Article', required=True, index=True)
    masse_tole              = fields.Float("Masse tôle", related="product_id.is_masse_tole", readonly=True)
    qt_recue_importee       = fields.Float("Qt reçue importée (unité)"               , readonly=True)
    qt_recue_correction     = fields.Float("Qt reçue correction (unité)")
    qt_recue                = fields.Float("Qt reçue (unité)"                        , readonly=True)
    qt_recue_kg             = fields.Float("Qt reçue (Kg)"                           , readonly=True)
    qt_consommee_importee   = fields.Float("Qt consommée importée (unité)"           , readonly=True)
    qt_consommee_correction = fields.Float("Qt consommée correction (unité)")
    qt_consommee            = fields.Float("Qt consommée (unité)"                    , readonly=True)
    qt_consommee_kg         = fields.Float("Qt consommée (Kg)"                       , readonly=True)


class is_annee(models.Model):
    _name = 'is.annee'
    _description = "Années"
    _order='annee'
    _rec_name = 'annee'
    annee = fields.Char("Année", required=True)


