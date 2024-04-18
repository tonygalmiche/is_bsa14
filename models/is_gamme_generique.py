# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_gamme_generique(models.Model):
    _name='is.gamme.generique'
    _description='Gamme générique'
    _order='name'

    name      = fields.Char("Gamme", required=True)
    ligne_ids = fields.One2many('is.gamme.generique.ligne', 'gamme_id', 'Lignes')


class is_gamme_generique_ligne(models.Model):
    _name = 'is.gamme.generique.ligne'
    _description = "Lignes gamme générique"
    _order='sequence'

    gamme_id      = fields.Many2one('is.gamme.generique', 'Gamme', required=True, ondelete='cascade')
    name          = fields.Char("Opération", required=True)
    sequence      = fields.Integer("Séquence", default=100)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Poste de Travail', required=True)
    duree         = fields.Float("Durée (HH:MN)", required=True)
    recouvrement  = fields.Integer("Recouvrement (%)", required=True, default=0, help="0%: Cette ligne commence à la fin de la ligne précédente\n50%: Cette ligne commence quand la ligne précédente est terminée à 50%\n100%: Cette ligne commence en même temps que la ligne précédente" )
    tps_apres     = fields.Float("Tps passage après (HH:MN)", default=0, help="Temps d'attente après cette opération avant de commencer la suivante (en heures ouvrées)")
    libre         = fields.Boolean("Libre", default=False, help="Permet de démarrer le suivi du temps sur cette opération à tout moment")
