# -*- coding: utf-8 -*-

from odoo import models,fields

class is_fiche_travail(models.Model):
    _name='is.fiche.travail'
    _description='is.fiche.travail'
    _order='name'

    name              = fields.Date("Date",required=True)
    ordre_fabrication = fields.Many2one('mrp.production', 'Ordre de fabrication', required=True)
    quantite          = fields.Integer('Quantité', required=True)
    commentaire       = fields.Text('Commentaire')




