# -*- coding: utf-8 -*-
from odoo import models,fields,api

class is_sav(models.Model):
    _name = "is.sav"
    _inherit = ['mail.thread']
    _description = "SAV"

    name              = fields.Char("N°SAV"      , readonly=True, tracking=True)
    date_defaut       = fields.Date("Date défaut",required=True, tracking=True)
    partner_id        = fields.Many2one('res.partner', 'Client',required=True, tracking=True)
    etiquette_id      = fields.Many2one('is.tracabilite.livraison', 'N°série', tracking=True)
    libelle           = fields.Text('Libellé du défaut', tracking=True)
    action_preventive = fields.Text('Action préventive', tracking=True)
    action_corrective = fields.Text('Action corrective', tracking=True)
    order_id          = fields.Many2one('sale.order', 'Devis client', tracking=True)
    temps_passe       = fields.Float('Temps passé (HH:MM)', tracking=True)
    state             = fields.Selection([
            ('creation'      , 'Création'),
            ('encours'       , 'En cours'),
            ('attente_client', 'Attente client'),
            ('traite'        , 'Traité'),
        ], "État", default='creation', tracking=True)


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.sav')
        res = super(is_sav, self).create(vals)
        return res

