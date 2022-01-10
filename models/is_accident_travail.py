# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import Warning
import datetime

class is_accident_travail(models.Model):
    _name='is.accident.travail'
    _description='is.accident.travail'
    _inherit = ['mail.thread']
    _order='name desc'

    name            = fields.Char("N°", readonly=True)
    createur_id     = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation   = fields.Date("Date de création", required=True, default=lambda *a: fields.Date.today())
    type_accident   = fields.Selection([
                        ('sans_visite_medecin', 'Sans visite de médecin et sans arrêt'),
                        ('sans_visite_medecin', 'Visite de médecin et sans arrêt'),
                        ('avec_arret_travail' , 'Avec arrêt de travail'),
                        ('amelioration'       , 'Amélioration'),
                    ], "Type", required=True)
    employe_id          = fields.Many2one('hr.employee', 'Employé')
    description         = fields.Text("Description du problème")
    individu            = fields.Text("L'individu")
    tache               = fields.Text("La tache")
    materiel            = fields.Text("Le matériel")
    milieu              = fields.Text("Le milieu")
    resolution          = fields.Text("Résolution")
    evaluation          = fields.Text("Évaluation")
    date_evaluation     = fields.Date("Date évaluation")
    evaluateur_id       = fields.Many2one('res.users', 'Evaluateur')
    attachment_ids      = fields.Many2many('ir.attachment', 'is_accident_travail_attachment_rel', 'accident_id', 'attachment_id', 'Pièces jointes')
    state               = fields.Selection([
                        ('ouverte', 'Ouverte'),
                        ('encours', 'En cours'),
                        ('fermee' , 'Fermée'),
                    ], "État", default="ouverte")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.accident.travail')
        res = super(is_accident_travail, self).create(vals)
        return res
