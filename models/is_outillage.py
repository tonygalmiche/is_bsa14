# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_outillage(models.Model):
    _name='is.outillage'
    _inherit = ['mail.thread']
    _description = "Outillage"
    _order='name'

    name           = fields.Char("Outillage", required=True)
    ligne_id       = fields.Many2one('is.outillage.ligne', 'Ligne de production', required=True)
    reference      = fields.Char("Référence")
    marque         = fields.Char("Marque")
    responsable_id = fields.Many2one('res.users', 'Responsable', required=True)
    fin_garantie   = fields.Date("Date de fin de garantie", required=True)
    active         = fields.Boolean("Actif", default=True)


class is_outillage_ligne(models.Model):
    _name='is.outillage.ligne'
    _description = "Ligne de production outillage"
    _order='name'

    name = fields.Char("Ligne de production", required=True)

