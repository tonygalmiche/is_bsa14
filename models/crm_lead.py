# -*- coding: utf-8 -*-
from odoo import models,fields,api

class is_crm_lead_stage(models.Model):
    _name = 'is.crm.lead.stage'
    _description = "Etapes des opportunité"

    lead_id       = fields.Many2one('crm.lead', 'Opportunité', required=True, ondelete='cascade')
    date_creation = fields.Datetime("Date", readonly=True, default=fields.Datetime.now)
    stage_id      = fields.Many2one('crm.stage', 'Etapes', required=True)
    commentaire   = fields.Char("Commentaire")


class is_crm_lead_entree(models.Model):
    _name = 'is.crm.lead.entree'
    _description = "Données d'entrée des opportunité"

    lead_id        = fields.Many2one('crm.lead', 'Opportunité', required=True, ondelete='cascade')
    date_creation  = fields.Datetime("Date", readonly=True, default=fields.Datetime.now)
    attachment_ids = fields.Many2many('ir.attachment', 'is_crm_lead_entree_attachment_rel', 'entree_id', 'attachment_id', u'Pièces jointes')
    commentaire    = fields.Char("Commentaire")


class is_crm_lead_sortie(models.Model):
    _name = 'is.crm.lead.sortie'
    _description = "Données de sortie des opportunité"

    lead_id        = fields.Many2one('crm.lead', 'Opportunité', required=True, ondelete='cascade')
    date_creation  = fields.Datetime("Date", readonly=True, default=fields.Datetime.now)
    attachment_ids = fields.Many2many('ir.attachment', 'is_crm_lead_sortie_attachment_rel', 'sortie_id', 'attachment_id', u'Pièces jointes')
    commentaire    = fields.Char("Commentaire")


class crm_lead(models.Model):
    _inherit  = "crm.lead"

    @api.depends('is_description')
    def _compute_is_description_html(self):
        for obj in self:
            obj.is_description_html = (obj.is_description or '').replace('\n','<br />')

    is_affaire_id          = fields.Many2one('is.devis.parametrable.affaire', 'Affaire')
    is_order_id            = fields.Many2one('sale.order', 'Commande client')
    is_description         = fields.Text('Description longue')
    is_description_html    = fields.Text('Description HTML', compute='_compute_is_description_html', readonly=True, store=False)
    is_categorie_client_id = fields.Many2one("is.categorie.client", string="Catégorie de client", related="partner_id.is_categorie_client_id", readonly=True)
    is_implantation = fields.Selection([
            ('Oui', 'Oui'),
            ('Non', 'Non'),
        ], "Implantation")
    is_stage_ids  = fields.One2many('is.crm.lead.stage' , 'lead_id', "Etapes")
    is_entree_ids = fields.One2many('is.crm.lead.entree', 'lead_id', "Données d'entrée")
    is_sortie_ids = fields.One2many('is.crm.lead.sortie', 'lead_id', "Données de sortie")

    @api.model
    def create(self, vals):
        res = super(crm_lead, self).create(vals)
        v={
            "lead_id" : res.id,
            "stage_id": res.stage_id.id,
        }
        self.env['is.crm.lead.stage'].create(v)
        return res

    def write(self, vals):
        if "stage_id" in vals:
            v={
                "lead_id" : self.id,
                "stage_id": vals["stage_id"],
            }
            self.env['is.crm.lead.stage'].create(v)
        res = super(crm_lead, self).write(vals)
        return res
