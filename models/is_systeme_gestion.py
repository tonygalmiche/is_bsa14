# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_sg_revue(models.Model):
    _name='is.sg.revue'
    _inherit = ['mail.thread']
    _description = "Système de gestion - Revue"
    _order='name'

    name           = fields.Char("Nom", required=True)
    date           = fields.Date("Date")
    reference      = fields.Char("Référence")


class is_sg_audit(models.Model):
    _name='is.sg.audit'
    _inherit = ['mail.thread']
    _description = "Système de gestion - Audit"
    _order='name'

    name           = fields.Char("Nom", required=True)
    date           = fields.Date("Date")
    reference      = fields.Char("Référence")
    systeme_id     = fields.Many2one('is.sg.systeme', 'Système')
    responsable_id = fields.Many2one('res.users', "Responsable de l'audit", required=True)
    auditeurs      = fields.Text("Auditeurs")


class is_sg_systeme(models.Model):
    _name='is.sg.systeme'
    _description = "Système de gestion - Système"
    _order='name'

    name           = fields.Char("Nom", required=True)


class is_sg_manuel(models.Model):
    _name='is.sg.manuel'
    _inherit = ['mail.thread']
    _description = "Système de gestion - Manuel"
    _order='name'

    name      = fields.Char("Titre", required=True)
    parent_id = fields.Many2one('is.sg.manuel', "Catégorie")

