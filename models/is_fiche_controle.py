# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime


class is_fiche_controle(models.Model):
    _name='is.fiche.controle'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Fiche contrôle"
    _order='name desc'

    name               = fields.Char("Fiche")
    type_fiche         = fields.Selection([
        ('interne', 'Interne'),
        ('client' , 'Client'),
    ], "Type de fiche")
    product_id         = fields.Many2one('product.product', 'Article', tracking=True)
    date_creation      = fields.Date("Date de création"              , required=True, default=lambda *a: fields.Date.today())
    createur_id        = fields.Many2one('res.users', 'Créateur'     , required=True, default=lambda self: self.env.user.id)
    controleur_id      = fields.Many2one('res.users', 'Contrôleur fabrication')
    soudeur_id         = fields.Many2one('res.users', 'Soudeur')
    ligne_ids          = fields.One2many('is.fiche.controle.ligne', 'fiche_id', 'Lignes', copy=True)
    observation        = fields.Text("Observations", tracking=True)
    modele             = fields.Boolean("Modèle", default=False)
    operateur_id       = fields.Many2one('hr.employee', 'Contrôleur')
    operateur_ids      = fields.Many2many('hr.employee', 'is_fiche_controle_operateur_rel', 'fiche_id', 'operateur_id', 'Opérateurs', compute="_compute_operateur_ids", readonly=True, store=False)
    ot_line_id         = fields.Many2one('is.ordre.travail.line', 'Ligne ordre de travail')
    modele_id          = fields.Many2one('is.fiche.controle', "Modèle utilisé")
    active             = fields.Boolean("Actif", default="True", tracking=True)


    @api.depends("ot_line_id","ot_line_id.temps_passe_ids.employe_id")
    def _compute_operateur_ids(self):
        for obj in self:
            ids=[]
            for line in obj.ot_line_id.temps_passe_ids:
                if line.employe_id:
                    ids.append(line.employe_id.id)
            obj.operateur_ids = ids


    @api.model
    def create(self, vals):
        if vals.get('modele')!=True:
            vals['name'] = self.env['ir.sequence'].next_by_code('is.fiche.controle')
        res = super(is_fiche_controle, self).create(vals)
        return res

    @api.onchange('type_fiche')
    def _onchange_type_fiche(self):
        if self.type_fiche:
            if not self.modele:
                self.ligne_ids=False
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
    conforme       = fields.Selection([
            ('oui'   , '1-vert'),
            ('jaune' , '2-jaune'),
            ('orange', '3-orange'),
            ('non'   , '4-rouge'),
        ], "Conforme", required=False)
    action_corrective = fields.Text("Si non, action corrective")


class is_fiche_controle_point(models.Model):
    _name = 'is.fiche.controle.point'
    _description = "Points à contrôler"
    _order='ordre'

    name  = fields.Char("Point à contrôler", required=True)
    ordre = fields.Integer("Ordre")







