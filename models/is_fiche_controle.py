# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime


class is_fiche_controle(models.Model):
    _name='is.fiche.controle'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Fiche contrôle"
    _order='name desc'

    name               = fields.Char("Fiche", readonly=True)
    type_fiche         = fields.Selection([('interne', u'Interne'),('client', u'Client')], "Type de fiche", required=True)
    product_id         = fields.Many2one('product.product', 'Article', required=True)
    date_creation      = fields.Date("Date de création"              , required=True, default=lambda *a: fields.Date.today())
    createur_id        = fields.Many2one('res.users', 'Créateur'     , required=True, default=lambda self: self.env.user.id)
    controleur_id      = fields.Many2one('res.users', 'Contrôleur fabrication')
    soudeur_id         = fields.Many2one('res.users', 'Soudeur')
    ligne_ids          = fields.One2many('is.fiche.controle.ligne', 'fiche_id', u'Lignes')
    observation        = fields.Text("Observations")

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.fiche.controle')
        res = super(is_fiche_controle, self).create(vals)
        return res

    @api.onchange('type_fiche')
    def _onchange_type_fiche(self):
        if self.type_fiche:
            lignes = []
            points = self.env['is.fiche.controle.point'].search([])
            for point in points:
                lignes.append((0, 0, {
                    'fiche_id': self.id,
                    'point'   : point.name,
                }))
            self.ligne_ids = lignes


class is_fiche_controle_ligne(models.Model):
    _name = 'is.fiche.controle.ligne'
    _description = "Lignes fiche contrôle"

    fiche_id = fields.Many2one('is.fiche.controle', 'Fiche', required=True, ondelete='cascade')
    point          = fields.Char("Point à contrôler")
    conforme       = fields.Selection([('oui', u'Oui'),('non', u'Non')], "Conforme", required=True)
    action_corrective = fields.Text("Si non, action corrective")


class is_fiche_controle_point(models.Model):
    _name = 'is.fiche.controle.point'
    _description = "Points à contrôler"
    _order='ordre'

    name  = fields.Char("Point à contrôler", required=True)
    ordre = fields.Integer("Ordre")







