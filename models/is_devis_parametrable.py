# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime


class is_devis_parametrable(models.Model):
    _name='is.devis.parametrable'
    _description = "Devis paramètrable"
    _order='name desc'


    @api.depends('equipement_ids')
    def _compute_montant(self):
        for obj in self:
            montant=0
            for line in obj.equipement_ids:
                montant+=line.montant_total
            obj.total_equipement = montant

    name               = fields.Char("N°", readonly=True)
    createur_id        = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation      = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    partner_id         = fields.Many2one('res.partner', 'Client', required=True)
    commentaire        = fields.Text("Commentaire")
    equipement_ids     = fields.One2many('is.devis.parametrable.equipement', 'devis_id', 'Equipements', copy=True)
    total_equipement   = fields.Float("Total équipement", store=True, readonly=True, compute='_compute_montant')
    variante_ids       = fields.One2many('is.devis.parametrable.variante', 'devis_id', 'Variantes', copy=True)


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.devis.parametrable')
        res = super(is_devis_parametrable, self).create(vals)
        return res


class is_devis_parametrable_equipement(models.Model):
    _name = 'is.devis.parametrable.equipement'
    _description = "Equipements du devis paramètrable"


    @api.depends('product_ids')
    def _compute_montant(self):
        for obj in self:
            montant=0
            for line in obj.product_ids:
                montant+=line.montant
            obj.montant_total = montant


    @api.depends('product_ids')
    def _compute_tps_montage(self):
        for obj in self:
            tps=0
            for line in obj.product_ids:
                tps+=line.tps_montage
            obj.tps_montage = tps


    devis_id           = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    type_equipement_id = fields.Many2one('is.type.equipement', "Type d'équipement")
    product_ids        = fields.One2many('is.devis.parametrable.equipement.product', 'equipement_id', 'Articles', copy=True)
    montant_total      = fields.Float("Total", store=True, readonly=True, compute='_compute_montant')
    tps_montage        = fields.Float("Tps", help="Temps de montatge (mn)", store=True, readonly=True, compute='_compute_tps_montage')


class is_devis_parametrable_equipement_product(models.Model):
    _name = 'is.devis.parametrable.equipement.product'
    _description = "Lignes des équipements du devis paramètrable"


    @api.onchange('product_id')
    def onchange_product_id(self):
        for obj in self:
            obj.prix=123


    @api.depends('product_id','quantite','prix')
    def _compute_montant(self):
        for obj in self:
            montant=0
            if obj.prix and obj.quantite:
                montant = obj.prix*obj.quantite
            obj.montant = montant


    @api.depends('product_id','quantite','prix')
    def _compute_date_achat(self):
        for obj in self:
            obj.date_achat=fields.Date.today()


    @api.depends('product_id','quantite')
    def _compute_tps_montage(self):
        for obj in self:
            tps=0
            if obj.product_id and obj.product_id.is_type_equipement_id:
                tps+=obj.product_id.is_type_equipement_id.tps_montage*obj.quantite
            obj.tps_montage = tps


    equipement_id = fields.Many2one('is.devis.parametrable.equipement', 'Equipement', required=True, ondelete='cascade')
    product_id    = fields.Many2one('product.product', "Article")
    uom_po_id     = fields.Many2one('uom.uom', "Unité", help="Unité de mesure d'achat", related="product_id.uom_po_id", readonly=True)
    quantite      = fields.Float("Quantité")
    prix          = fields.Float("Prix", help="Prix d'achat")
    date_achat    = fields.Date("Date"    , store=True, readonly=True, compute='_compute_date_achat', help="Date du dernier achat")
    montant       = fields.Float("Montant", store=True, readonly=True, compute='_compute_montant')
    tps_montage   = fields.Float("Tps", help="Temps de montatge (mn)", store=True, readonly=True, compute='_compute_tps_montage')


class is_devis_parametrable_variante(models.Model):
    _name = 'is.devis.parametrable.variante'
    _description = "Variantes du devis paramètrable"

    devis_id          = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    quantite          = fields.Integer("Qt prévue")
    marge_matiere     = fields.Float("Marge matière")
    marge_equipement  = fields.Float("Marge équipement")
    marge_montage     = fields.Float("Marge montage")
    tps_be            = fields.Float("Tps BE", help="Le temps BE sera divisé par la quantité prévue dans les calculs")
    marge_be          = fields.Float("Marge BE")
    marge_revendeur   = fields.Float("Marge revendeur")
    gain_productivite = fields.Float("Gain de productivé (%)", help="En fonction de la quantité prévue, vous pouvez ajouter un gain de productivité sur le temps de montage des équipements")


# Note : j’ajouterais une variable, si possible (ou dans un 2ème temps), soit la dégressivité des prix en fonction des quantités en jouant sur :
#     Les NRC (non recurring costs), soit les temps BE (dossier technique et/ ou coûts outillage)
#     Les gains de productivité – temps MO (Main d’œuvre) décroissant en fonction de la quantité (effet proto vs série) (p.ex. dégressivité de 10 à 15% sur temps MO)
#     Les gains de productivité – optimisation des débits matière (idem)
# Enfi
#     Le taux de marge dégressif, soit linéaire sur l’ensemble des taux de marges à appliquer


class is_type_equipement(models.Model):
    _name = 'is.type.equipement'
    _description = "Type d'équipement"
    _order='name'

    name        = fields.Char("Type d'équipement", required=True)
    tps_montage = fields.Float("Temps de montatge (mn)")







