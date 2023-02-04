# -*- coding: utf-8 -*-

from odoo import models,fields,api

class is_salon(models.Model):
    _name = "is.salon"
    _description="Salon pour le suivi commercial"
    _order="name"
    name = fields.Char(string="Salon", required=True)


class is_suivi_commercial(models.Model):
    _name='is.suivi.commercial'
    _description='Suivi commercial'
    _order='numero desc'

    numero        = fields.Char("N°", readonly=True)
    name          = fields.Char("Intitulé",required=True)
    description   = fields.Text("Description")
    date_visite   = fields.Datetime("Date visite", required=True, default=lambda *a: fields.Datetime.now())
    duree_visite  = fields.Float("Durée (HH:MN)", required=True, default=1)
    commercial_id = fields.Many2one('res.users', "Chargé d'affaire", required=True, default=lambda self: self.env.user.id)
    client_id     = fields.Many2one('res.partner', "Client", required=False)
    is_categorie_client_id = fields.Many2one("is.categorie.client", string="Catégorie de client", related="client_id.is_categorie_client_id", readonly=True)
    tag_ids = fields.Many2many('crm.tag', 'is_suivi_commercial_tag_rel', 'suivi_id', 'tag_id', string='Tags')
    salon_id = fields.Many2one('is.salon', "Salon")

    @api.model
    def create(self, vals):
        vals['numero'] = self.env['ir.sequence'].next_by_code('is.suivi.commercial')
        res = super(is_suivi_commercial, self).create(vals)
        return res


