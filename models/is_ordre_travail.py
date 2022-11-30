# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import Warning
import datetime


class is_ordre_travail(models.Model):
    _name='is.ordre.travail'
    _description='Ordre de travail'
    _inherit = ['mail.thread']
    _order='name desc'

    name                = fields.Char("N°", readonly=True)
    createur_id         = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation       = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    production_id       = fields.Many2one('mrp.production', 'Ordre de production', required=True)
    quantite            = fields.Float('Qt prévue', digits=(14,2))
    date_prevue         = fields.Datetime('Date prévue' , related='production_id.date_planned_start')
    bom_id              = fields.Many2one('mrp.bom', 'Nomenclature', related='production_id.bom_id')
    state               = fields.Selection([
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
        ], "État", default='encours')



    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.ordre.travail')
        res = super(is_ordre_travail, self).create(vals)
        return res
