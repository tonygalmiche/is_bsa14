# -*- coding: utf-8 -*-
from pickle import OBJ
from odoo import models,fields,api
import datetime


class is_devis_parametrable_affaire(models.Model):
    _name='is.devis.parametrable.affaire'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Affaire - Devis paramètrable"
    _order='name'

    name         = fields.Char("Affaire", required=True)
    partner_id   = fields.Many2one('res.partner', 'Client', required=True)
    revendeur_id = fields.Many2one('res.partner', 'Revendeur')
    variante_ids = fields.One2many('is.devis.parametrable.affaire.variante', 'affaire_id', 'Variantes', copy=True)


class is_devis_parametrable_affaire_variante(models.Model):
    _name='is.devis.parametrable.affaire.variante'
    _description = "Variantes des affaires"
    _order='variante_id'

    affaire_id  = fields.Many2one('is.devis.parametrable.affaire', 'Affaire', required=True, ondelete='cascade')
    variante_id = fields.Many2one('is.devis.parametrable.variante', 'Variante')



class is_devis_parametrable(models.Model):
    _name='is.devis.parametrable'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Devis paramètrable"
    _order='name desc'


    @api.depends('matiere_ids')
    def _compute_montant_matiere(self):
        for obj in self:
            montant=0
            for line in obj.matiere_ids:
                montant+=line.montant
            obj.montant_matiere = montant


    @api.depends('section_ids')
    def _compute_montant(self):
        for obj in self:
            montant=tps_montage=0
            for line in obj.section_ids:
                montant+=line.montant_total
                tps_montage+=line.tps_montage
            obj.total_equipement = montant
            obj.tps_montage      = tps_montage


    name                       = fields.Char("N°", readonly=True)
    image                      = fields.Binary("Image")
    code_devis                 = fields.Char("Code devis")
    designation                = fields.Char("Désignation")
    designation_complementaire = fields.Char("Désignation complémentaire")
    capacite                   = fields.Integer("Capacité")
    unite                      = fields.Selection([
            ('Litre', 'Litre'),
            ('m3'   , 'm3'),
            ('HL'   , 'HL'),
        ], "Unité")
    type_cuve_id       = fields.Many2one('is.type.cuve', 'Type de cuve', required=True)
    createur_id        = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation      = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    date_actualisation = fields.Datetime("Date d'actualisation"                , default=fields.Datetime.now)
    partner_id         = fields.Many2one('res.partner', 'Client', required=True)
    matiere_ids        = fields.One2many('is.devis.parametrable.matiere'  , 'devis_id', 'Matières'  , copy=True)
    dimension_ids      = fields.One2many('is.devis.parametrable.dimension', 'devis_id', 'Dimensions', copy=True)
    section_ids        = fields.One2many('is.devis.parametrable.section'  , 'devis_id', 'Sections'  , copy=True)
    variante_ids       = fields.One2many('is.devis.parametrable.variante' , 'devis_id', 'Variantes' , copy=True)
    total_equipement   = fields.Float("Total équipement"                     , store=False, readonly=True, compute='_compute_montant')
    tps_montage        = fields.Float("Tps (HH:MM)"    , help="Temps de montatge (HH:MM)", store=False, readonly=True, compute='_compute_montant')
    montant_matiere    = fields.Float("Montant matière", store=False, readonly=True, compute='_compute_montant_matiere')
    commentaire        = fields.Text("Commentaire")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.devis.parametrable')
        res = super(is_devis_parametrable, self).create(vals)
        return res


    def creation_section_action(self):
        for obj in self:
            res= {
                'name': 'Section',
                'view_mode': 'form',
                'res_model': 'is.devis.parametrable.section',
                'type': 'ir.actions.act_window',
                'context': {'default_devis_id': obj.id }
            }
            return res


    def creation_variante_action(self):
        for obj in self:
            res= {
                'name': 'Variante',
                'view_mode': 'form',
                'res_model': 'is.devis.parametrable.variante',
                'type': 'ir.actions.act_window',
                'context': {'default_devis_id': obj.id }
            }
            return res


    def actualiser_prix_action(self):
        for obj in self:
            obj.date_actualisation = datetime.datetime.now()
            for section in obj.section_ids:
                for line in section.product_ids:
                    res = self.get_prix_achat(line.product_id)
                    line.prix       = res[0]
                    line.date_achat = res[1]


    def get_prix_achat(self, product):
        cr = self._cr
        prix=product.standard_price
        date_achat = False
        if product:
            SQL="""
                select 
                    pol.price_unit,
                    po.date_approve
                from purchase_order_line pol join purchase_order po on pol.order_id=po.id
                where pol.product_id=%s and po.state='purchase'
                order by po.date_approve desc, pol.id desc
                limit 1
            """
            cr.execute(SQL,[product.id])
            lines = cr.fetchall()
            for line in lines:
                prix       = line[0]
                date_achat = line[1]
        return[prix, date_achat]


class is_devis_parametrable_matiere(models.Model):
    _name = 'is.devis.parametrable.matiere'
    _description = "Matieres du devis paramètrable"

    @api.depends('prix_achat', 'matiere_id', 'poids')
    def _compute_montant(self):
        for obj in self:
            obj.montant = obj.prix_achat * obj.poids


    @api.onchange('matiere_id')
    def onchange_matiere_id(self):
        for obj in self:
            obj.prix_achat         = obj.matiere_id.prix_achat
            obj.date_actualisation = obj.matiere_id.date_actualisation


    devis_id   = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    section_id = fields.Many2one('is.section.devis', "Section")
    matiere_id = fields.Many2one('is.matiere', "Matière")
    epaisseur  = fields.Float("Épaisseur")
    poids              = fields.Float("Poids (Kg)")
    prix_achat         = fields.Float("Prix d'achat au Kg")
    date_actualisation = fields.Date("Date d'actualisation")
    montant            = fields.Float("Montant", store=True, readonly=True, compute='_compute_montant')


class is_devis_parametrable_dimension(models.Model):
    _name = 'is.devis.parametrable.dimension'
    _description = "Dimensions du devis paramètrable"

    devis_id     = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    dimension_id = fields.Many2one('is.dimension', 'Dimension')
    description  = fields.Char("Description"   , help="Information pour le client")
    valeur       = fields.Integer("Valeur (mm)", help="Utilisée dans les calculs")


class is_devis_parametrable_section(models.Model):
    _name = 'is.devis.parametrable.section'
    _description = "Sections du devis paramètrable"

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
    section_id         = fields.Many2one('is.section.devis', "Section")
    product_ids        = fields.One2many('is.devis.parametrable.section.product', 'section_id', 'Articles', copy=True)
    montant_total      = fields.Float("Total", store=True, readonly=True, compute='_compute_montant')
    tps_montage        = fields.Float("Tps (HH:MM)", help="Temps de montatge (HH:MM)", store=True, readonly=True, compute='_compute_tps_montage')



    def acceder_section_action(self):
        for obj in self:
            res={
                'name': 'Section',
                'view_mode': 'form',
                'res_model': 'is.devis.parametrable.section',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res





class is_devis_parametrable_section_product(models.Model):
    _name = 'is.devis.parametrable.section.product'
    _description = "Lignes des sections du devis paramètrable"


    @api.onchange('product_id')
    def onchange_product_id(self):
        for obj in self:
            res = self.env['is.devis.parametrable'].get_prix_achat(obj.product_id)
            obj.prix        = res[0]
            obj.date_achat  = res[1]
            obj.description = obj.product_id.is_description_devis


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


    @api.depends('type_equipement_id','product_id','quantite')
    def _compute_tps_montage(self):
        for obj in self:
            tps=0
            if obj.product_id and obj.product_id.is_type_equipement_id:
                tps+=obj.product_id.is_type_equipement_id.tps_montage*obj.quantite
            obj.tps_montage = tps


    section_id         = fields.Many2one('is.devis.parametrable.section', 'Section', required=True, ondelete='cascade')
    type_equipement_id = fields.Many2one('is.type.equipement', "Type d'équipement")
    product_id         = fields.Many2one('product.product', "Article")
    description        = fields.Text("Description")
    uom_po_id          = fields.Many2one('uom.uom', "Unité", help="Unité de mesure d'achat", related="product_id.uom_po_id", readonly=True)
    quantite           = fields.Float("Quantité", default=1)
    prix               = fields.Float("Prix", help="Prix d'achat")
    date_achat         = fields.Date("Date"    , store=True, readonly=True, compute='_compute_date_achat', help="Date du dernier achat")
    montant            = fields.Float("Montant", store=True, readonly=True, compute='_compute_montant')
    tps_montage        = fields.Float("Tps (HH:MM)", help="Temps de montatge (HH:MM)", store=True, readonly=True, compute='_compute_tps_montage')


class is_devis_parametrable_variante(models.Model):
    _name = 'is.devis.parametrable.variante'
    _description = "Variantes du devis paramètrable"


    devis_id          = fields.Many2one('is.devis.parametrable', 'Devis paramètrable', required=True, ondelete='cascade')
    name              = fields.Char("Nom", required=True)
    partner_id        = fields.Many2one('res.partner', "Client", related="devis_id.partner_id", readonly=True)



    quantite          = fields.Integer("Qt prévue")
    marge_matiere     = fields.Float("Marge matière (%)")
    marge_equipement  = fields.Float("Marge équipement (%)")
    marge_montage     = fields.Float("Marge MO (%)")
    tps_be            = fields.Float("Tps BE (HH:MM)", help="Le temps BE sera divisé par la quantité prévue dans les calculs")
    marge_be          = fields.Float("Marge BE (%)")
    marge_revendeur   = fields.Float("Marge revendeur (%)")
    gain_productivite = fields.Float("Gain de productivé (%)", help="En fonction de la quantité prévue, vous pouvez ajouter un gain de productivité sur le temps de montage des équipements")

    currency_id        = fields.Many2one('res.currency', "Devise", readonly=True, compute='_compute_montants')

    montant_matiere    = fields.Monetary("Montant matière" , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_equipement = fields.Monetary("Montant equipements", readonly=True, compute='_compute_montants', currency_field='currency_id')
    tps_montage        = fields.Float("Tps montage (HH:MM)"        , readonly=True, compute='_compute_montants')
    montant_montage    = fields.Monetary("Montant MO sans productivité"    , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_montage_productivite = fields.Monetary("Montant MO", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_be         = fields.Monetary("Montant BE"         , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_total      = fields.Monetary("Montant Total"      , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_unitaire   = fields.Monetary("Montant Unitaire"   , readonly=True, compute='_compute_montants', currency_field='currency_id')

    montant_matiere_pourcent              = fields.Float("% Montant matière"                  , readonly=True, compute='_compute_montants')
    montant_equipement_pourcent           = fields.Float("% Montant equipements"              , readonly=True, compute='_compute_montants')
    montant_montage_productivite_pourcent = fields.Float("% Montant MO avec productivité", readonly=True, compute='_compute_montants')
    montant_be_pourcent                   = fields.Float("% Montant BE"                       , readonly=True, compute='_compute_montants')

    prix_vente_lot              = fields.Monetary("Prix de vente de l'affaire"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    prix_vente_revendeur_lot    = fields.Monetary("Prix de vente revendeur de l'affaire", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_lot           = fields.Monetary("Marge de l'affaire"                  , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_revendeur_lot = fields.Monetary("Marge revendeur de l'affaire"        , readonly=True, compute='_compute_montants', currency_field='currency_id')

    prix_vente               = fields.Monetary("Prix de vente"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    prix_vente_revendeur     = fields.Monetary("Prix de vente revendeur", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge            = fields.Monetary("Marge"                  , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_revendeur  = fields.Monetary("Marge revendeur"        , readonly=True, compute='_compute_montants', currency_field='currency_id')

    commentaire              = fields.Text("Commentaire")


    @api.depends('quantite','marge_matiere','marge_equipement','marge_montage','tps_be','marge_be','marge_revendeur','gain_productivite')
    def _compute_montants(self):
        company = self.env.user.company_id
        for obj in self:
            obj.currency_id = company.currency_id.id
            quantite = obj.quantite or 1

            tps_montage        = obj.devis_id.tps_montage*quantite
            montant_matiere    = obj.devis_id.montant_matiere*quantite
            montant_equipement = obj.devis_id.total_equipement*quantite
            montant_montage    = tps_montage*company.is_cout_horaire_montage
            montant_montage_productivite = montant_montage-montant_montage*obj.gain_productivite/100
            montant_be         = obj.tps_be * company.is_cout_horaire_be
            montant_total      = montant_matiere + montant_equipement + montant_montage_productivite + montant_be

            if montant_total>0:
                obj.montant_matiere_pourcent              = 100 * montant_matiere / montant_total
                obj.montant_equipement_pourcent           = 100 * montant_equipement / montant_total
                obj.montant_montage_productivite_pourcent = 100 * montant_montage_productivite / montant_total
                obj.montant_be_pourcent                   = 100 * montant_be / montant_total

            montant_unitaire = montant_total/quantite

            prix_vente  = montant_matiere*(1+obj.marge_matiere/100)
            prix_vente += montant_equipement*(1+obj.marge_equipement/100)
            prix_vente += montant_montage_productivite*(1+obj.marge_montage/100)
            prix_vente += montant_be*(1+obj.marge_be/100)

            prix_vente_revendeur = prix_vente*(1+obj.marge_revendeur/100)

            obj.montant_matiere    = montant_matiere
            obj.montant_equipement = montant_equipement
            obj.tps_montage        = tps_montage
            obj.montant_montage    = montant_montage
            obj.montant_montage_productivite = montant_montage_productivite
            obj.montant_be         = montant_be
            obj.montant_total      = montant_total
            obj.montant_unitaire   = montant_unitaire

            obj.prix_vente_lot              = prix_vente
            obj.prix_vente_revendeur_lot    = prix_vente_revendeur
            obj.montant_marge_lot           = prix_vente - montant_total
            obj.montant_marge_revendeur_lot = prix_vente_revendeur - prix_vente

            obj.prix_vente              = prix_vente/quantite
            obj.prix_vente_revendeur    = prix_vente_revendeur/quantite
            obj.montant_marge           = (prix_vente - montant_total)/quantite
            obj.montant_marge_revendeur = (prix_vente_revendeur - prix_vente)/quantite


    def acceder_variante_action(self):
        for obj in self:
            res={
                'name': 'Variante',
                'view_mode': 'form',
                'res_model': 'is.devis.parametrable.variante',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res


class is_type_equipement(models.Model):
    _name = 'is.type.equipement'
    _description = "Type d'équipement"
    _order='name'

    name        = fields.Char("Type d'équipement", required=True)
    tps_montage = fields.Float("Temps de montatge (HH:MM)")


class is_section_devis(models.Model):
    _name = 'is.section.devis'
    _description = "Section devis"
    _order='name'

    name        = fields.Char("Section devis", required=True)


class is_type_cuve(models.Model):
    _name='is.type.cuve'
    _description = "Type de cuve"
    _order='name'

    name          = fields.Char("Type de cuve", required=True)
    perte_decoupe = fields.Integer("Perte à la découpe (%)")


class is_matiere(models.Model):
    _name='is.matiere'
    _description = "Matière"
    _order='name'

    name               = fields.Char("Matière", required=True)
    prix_achat         = fields.Float("Prix d'achat au Kg")
    date_actualisation = fields.Date("Date d'actualisation")
    type_matiere       = fields.Char("Type")
    finition_interieur = fields.Char("Finition intérieure")
    finition           = fields.Char("Finition extérieure")


class is_dimension(models.Model):
    _name='is.dimension'
    _description = "Dimension"
    _order='name'

    name = fields.Char("Dimension", required=True)













    # def creer_devis_action(self):
    #     for obj in self:
    #         print(obj)

    #         if obj.order_id:
    #             order = obj.order_id
    #             order.order_line.unlink()
    #         else:
    #             vals={
    #                 "partner_id": obj.devis_id.partner_id.id,
    #             }
    #             order = self.env['sale.order'].create(vals)
    #             obj.order_id = order.id

    #         lig=1
    #         vals={
    #             "order_id"    : order.id,
    #             "sequence"    : lig,
    #             "name"        : "Matière",
    #             "display_type": "line_section",
    #             "product_uom_qty" : 0,
    #         }
    #         line = self.env['sale.order.line'].create(vals)

    #         lig+=1
    #         vals={
    #             "order_id"   : order.id,
    #             "sequence"   : lig,
    #             "product_id" : obj.devis_id.matiere_id.id,
    #             "product_uom_qty": obj.devis_id.poids_matiere,
    #             "price_unit" : obj.devis_id.prix_matiere,
    #         }
    #         line = self.env['sale.order.line'].create(vals)

    #         for section in obj.devis_id.section_ids:
    #             lig+=1
    #             vals={
    #                 "order_id"    : order.id,
    #                 "sequence"    : lig,
    #                 "name"        : section.section_id.name,
    #                 "display_type": "line_section",
    #                 "product_uom_qty" : 0,
    #             }
    #             line = self.env['sale.order.line'].create(vals)


    #             for line in section.product_ids:
    #                 lig+=1
    #                 vals={
    #                     "order_id"   : order.id,
    #                     "sequence"   : lig,
    #                     "product_id" : line.product_id.id,
    #                     "product_uom_qty": line.quantite,
    #                     "price_unit" : line.prix,
    #                 }
    #                 if line.description:
    #                     vals["name"] = line.description
    #                 line = self.env['sale.order.line'].create(vals)
    #                 print(line)

