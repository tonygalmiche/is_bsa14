# -*- coding: utf-8 -*-
from odoo import models,fields,api

class is_crm_lead_stage(models.Model):
    _name = 'is.crm.lead.stage'
    _description = "Etapes des opportunité"

    lead_id       = fields.Many2one('crm.lead', 'Opportunité', required=True, ondelete='cascade')
    date_creation = fields.Datetime("Date", readonly=False, default=fields.Datetime.now)
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


class crm_stage(models.Model):
    _inherit  = "crm.stage"

    is_devis_envoye = fields.Boolean('Devis envoyé', default=False, help="Utilisé pour connaitre la durée de réponse aux demandes")


class crm_lead(models.Model):
    _inherit  = "crm.lead"

    @api.depends('is_description')
    def _compute_is_description_html(self):
        for obj in self:
            obj.is_description_html = (obj.is_description or '').replace('\n','<br />')

    @api.depends('is_stage_ids')
    def _compute_statistiques(self):
        for obj in self:
            is_date_premier_devis_envoye = False
            is_duree_envoi_premier_devis = 0
            is_date_dernier_traitement = False
            is_duree_gagner = 0
            is_duree_totale = 0
            is_nombre_modifications = 0
            date_start = False
            for line in obj.is_stage_ids:
                if not date_start:
                    date_start = line.date_creation
                if line.stage_id.is_devis_envoye and not is_date_premier_devis_envoye:
                    is_date_premier_devis_envoye = line.date_creation
                    is_duree_envoi_premier_devis = (line.date_creation.date() - date_start.date()).days
                is_date_dernier_traitement = line.date_creation
                if line.stage_id.is_won:
                    is_duree_gagner = (line.date_creation.date() - date_start.date()).days
                is_duree_totale = (line.date_creation.date() - date_start.date()).days
                if line.stage_id.is_devis_envoye:
                    is_nombre_modifications+=1
            if is_nombre_modifications>0:
                is_nombre_modifications-=1
            obj.is_date_premier_devis_envoye = is_date_premier_devis_envoye
            obj.is_duree_envoi_premier_devis = is_duree_envoi_premier_devis
            obj.is_date_dernier_traitement = is_date_dernier_traitement
            obj.is_duree_gagner = is_duree_gagner
            obj.is_duree_totale = is_duree_totale
            obj.is_nombre_modifications = is_nombre_modifications


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

    is_date_premier_devis_envoye = fields.Date('Date premier devis envoyé'            , store=True, readonly=True, compute='_compute_statistiques')
    is_duree_envoi_premier_devis = fields.Integer('Durée envoi premier devis (Jours)' , store=True, readonly=True, compute='_compute_statistiques')
    is_date_dernier_traitement   = fields.Date('Date du dernier traitement'           , store=True, readonly=True, compute='_compute_statistiques')
    is_duree_gagner              = fields.Integer('Durée pour gagner le devis (Jours)', store=True, readonly=True, compute='_compute_statistiques')
    is_duree_totale              = fields.Integer('Durée totale de traitement (Jours)', store=True, readonly=True, compute='_compute_statistiques')
    is_nombre_modifications      = fields.Integer('Nombre de modifications du devis'  , store=True, readonly=True, compute='_compute_statistiques', help="Nombre de fois ou le devis a été envoyé - 1")


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
