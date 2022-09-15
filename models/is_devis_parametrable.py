# -*- coding: utf-8 -*-
from email.policy import default
from odoo import models,fields,api
import datetime
from odoo.http import request
import base64
import os
import re
import openpyxl
from glob import glob
import logging
from math import pi,tan
_logger = logging.getLogger(__name__)


class is_devis_parametrable_affaire(models.Model):
    _name='is.devis.parametrable.affaire'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Affaire - Devis paramètrable"
    _order='name'

    name                 = fields.Char("Affaire", required=True)
    partner_id           = fields.Many2one('res.partner', 'Client', required=True)
    revendeur_id         = fields.Many2one('res.partner', 'Revendeur')
    delais               = fields.Char("Délais")
    duree_validite       = fields.Char("Durée de validité de l'offre")
    conditions_generales = fields.Text("Conditions générales")

    variante_ids = fields.One2many('is.devis.parametrable.affaire.variante', 'affaire_id', 'Variantes', copy=True)

    tax_id      = fields.Many2one('account.tax', 'TVA à appliquer', readonly=True)
    currency_id = fields.Many2one('res.currency', "Devise", readonly=True, compute='_compute_montants')
    montant_ht  = fields.Monetary("Montant HT" , readonly=True, compute='_compute_montants')
    montant_tva = fields.Monetary("TVA"        , readonly=True, compute='_compute_montants')
    montant_ttc = fields.Monetary("Montant TTC", readonly=True, compute='_compute_montants')

    entete_ids   = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_entete_rel', 'affaire_id', 'attachment_id', 'Entête')
    pied_ids     = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_pied_rel'  , 'affaire_id', 'attachment_id', 'Pied')
    devis_ids    = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_devis_rel' , 'affaire_id', 'attachment_id', 'Devis')

    @api.depends('variante_ids')
    def _compute_montants(self):
        company = self.env.user.company_id
        for obj in self:
            obj.currency_id = company.currency_id.id
            ht=tva=ttc=0
            tax_id = False
            for line in obj.variante_ids:
                tax_id = line.variante_id.devis_id.tax_id.id
                qt = line.variante_id.quantite
                prix_vente=line.variante_id.prix_vente_int
                ht+=prix_vente*qt
                tva+=line.variante_id.montant_tva*qt
                ttc+=line.variante_id.prix_vente_ttc*qt
            obj.montant_ht  = ht
            obj.montant_tva = tva
            obj.montant_ttc = ttc
            obj.tax_id      = tax_id


    def generer_pdf_action(self):
        for obj in self:

            ct = 1
            paths = []
            attachment_obj = self.env['ir.attachment']

            # #** delete files ************************************************
            path="/tmp/affaire_%s_*.pdf"%(obj.id)
            for file in glob(path):
                os.remove(file)

            #** Entête ********************************************************
            for attachment in obj.entete_ids:
                pdf=base64.b64decode(attachment.datas)
                path="/tmp/affaire_%s_%02d_entete.pdf"%(obj.id,ct)
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                paths.append(path)
                ct+=1

            #** Variantes *****************************************************
            for line in obj.variante_ids:
                pdf = request.env.ref('is_bsa14.action_report_variante_devis_parametrable').sudo()._render_qweb_pdf([line.variante_id.id])[0]
                path="/tmp/affaire_%s_%02d_variante.pdf"%(obj.id,ct)
                paths.append(path)
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                ct+=1

            #** Récapitulatif *************************************************
            pdf = request.env.ref('is_bsa14.action_report_devis_parametrable_affaire').sudo()._render_qweb_pdf([obj.id])[0]
            path="/tmp/affaire_%s_%02d_recapitulatif.pdf"%(obj.id,ct)
            paths.append(path)
            f = open(path,'wb')
            f.write(pdf)
            f.close()
            ct+=1

            #** Pied ********************************************************
            for attachment in obj.pied_ids:
                pdf=base64.b64decode(attachment.datas)
                path="/tmp/affaire_%s_%02d_pied.pdf"%(obj.id,ct)
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                paths.append(path)
                ct+=1


            # ** Merge des PDF *************************************************
            path_merged="/tmp/affaire_%s.pdf"%(obj.id)
            cmd="export _JAVA_OPTIONS='-Xms16m -Xmx64m' && pdftk "+" ".join(paths)+" cat output "+path_merged+" 2>&1"
            _logger.info(cmd)
            stream = os.popen(cmd)
            res = stream.read()
            _logger.info("res pdftk = %s",res)
            if not os.path.exists(path_merged):
                raise Warning("PDF non généré\ncmd=%s"%(cmd))
            pdfs = open(path_merged,'rb').read()
            pdfs = base64.b64encode(pdfs)
            # ******************************************************************


            #** Ajout de la piece jointe marged ********************************
            name="Devis-%s.pdf"%(obj.id)
            model=self._name
            attachments = attachment_obj.search([('res_model','=',model),('res_id','=',obj.id),('name','=',name)])
            vals={
                'name'       : name,
                'type'       : 'binary', 
                'res_id'     : obj.id,
                'res_model'  : model,
                'datas'      : pdfs,
                'mimetype'   : 'application/x-pdf',
            }
            attachment_id=False
            if attachments:
                for attachment in attachments:
                    attachment.write(vals)
                    attachment_id=attachment.id
            else:
                attachment = attachment_obj.create(vals)
                attachment_id=attachment.id
            obj.devis_ids = [(6, 0, [attachment_id])]


class is_devis_parametrable_affaire_variante(models.Model):
    _name='is.devis.parametrable.affaire.variante'
    _description = "Variantes des affaires"
    _order='variante_id'

    affaire_id  = fields.Many2one('is.devis.parametrable.affaire', 'Affaire', required=True, ondelete='cascade')
    variante_id = fields.Many2one('is.devis.parametrable.variante', 'Variante')


    def acceder_variante_action(self):
        for obj in self:
            res={
                'name': 'Variante',
                'view_mode': 'form',
                'res_model': 'is.devis.parametrable.variante',
                'res_id': obj.variante_id.id,
                'type': 'ir.actions.act_window',
            }
            return res


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


    @api.depends('section_ids',"tps_assemblage","tps_majoration","tps_minoration")
    def _compute_montant(self):
        for obj in self:
            montant=tps_montage=0
            for line in obj.section_ids:
                montant+=line.montant_total
                tps_montage+=line.tps_montage
            obj.total_equipement = montant
            obj.tps_montage      = tps_montage
            obj.tps_total = tps_montage + obj.tps_assemblage + obj.tps_majoration - obj.tps_minoration

    name                       = fields.Char("N°", readonly=True)
    image                      = fields.Binary("Image", related="type_cuve_id.image")
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

    calcul_ids         = fields.One2many('is.type.cuve.calcul', 'devis_parametrable_id', 'Calculs', copy=True)

    createur_id        = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation      = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    date_actualisation = fields.Datetime("Date d'actualisation"                , default=fields.Datetime.now)
    partner_id         = fields.Many2one('res.partner', 'Client', required=True)
    tax_id             = fields.Many2one('account.tax', 'TVA à appliquer')
    tps_montage        = fields.Float("Tps montage (HH:MM)", help="Temps de montatge (HH:MM)", store=False, readonly=True, compute='_compute_montant')
    tps_assemblage     = fields.Float("Tps assemblage (HH:MM)")
    tps_majoration     = fields.Float("Tps majoration (HH:MM)")
    tps_minoration     = fields.Float("Tps minoration (HH:MM)")
    tps_total          = fields.Float("Tps total hors BE (HH:MM)", store=False, readonly=True, compute='_compute_montant')
    tps_be             = fields.Float("Tps BE (HH:MM)", help="Le temps BE sera divisé par la quantité prévue dans les calculs")

    matiere_ids        = fields.One2many('is.devis.parametrable.matiere'  , 'devis_id', 'Matières'  , copy=True)
    dimension_ids      = fields.One2many('is.devis.parametrable.dimension', 'devis_id', 'Dimensions', copy=True)
    section_ids        = fields.One2many('is.devis.parametrable.section'  , 'devis_id', 'Sections'  , copy=True)
    variante_ids       = fields.One2many('is.devis.parametrable.variante' , 'devis_id', 'Variantes' , copy=True)
    total_equipement   = fields.Float("Total équipement"                     , store=False, readonly=True, compute='_compute_montant')
    montant_matiere    = fields.Float("Montant matière", store=False, readonly=True, compute='_compute_montant_matiere')
    commentaire        = fields.Text("Commentaire")


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.devis.parametrable')
        res = super(is_devis_parametrable, self).create(vals)
        return res


    def write(self, vals):
        res = super(is_devis_parametrable, self).write(vals)
        if "capacite" not in vals:
            self.recalculer_action()
        return res


    def recalculer_action(self):
        for obj in self:
            #** Initialiser les données d'entrées *****************************
            for matiere in obj.matiere_ids:
                lien_id = matiere.section_id.epaisseur_matiere_id
                if lien_id:
                    for line in obj.calcul_ids:
                        if line.lien_id==lien_id:
                            line.formule=matiere.epaisseur
            for dimension in obj.dimension_ids:
                lien_id = dimension.dimension_id.lien_id
                if lien_id:
                    if lien_id.type_lien=="entree":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                line.formule=dimension.valeur
            for section in obj.section_ids:
                for product in section.product_ids:
                    lien_id = product.type_equipement_id.quantite_id
                    if lien_id.type_lien=="entree":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                line.formule=product.quantite
            #******************************************************************

            for line in obj.calcul_ids:
                line._compute_resultat(obj)

            #** Récupératon des données de sortie *****************************
            for matiere in obj.matiere_ids:
                lien_id = matiere.section_id.poids_matiere_id
                if lien_id:
                    for line in obj.calcul_ids:
                        if line.lien_id==lien_id:
                            matiere.poids=line.resultat
            for dimension in obj.dimension_ids:
                lien_id = dimension.dimension_id.lien_id
                if lien_id:
                    if lien_id.type_lien=="sortie":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                dimension.valeur= line.resultat
            for section in obj.section_ids:
                for product in section.product_ids:
                    lien_id = product.type_equipement_id.prix_id
                    if lien_id.type_lien=="sortie":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                product.prix=line.resultat
            #******************************************************************

            #** Récupératon capacite ******************************************
            for line in obj.calcul_ids:
                if line.lien_id.name=="capacite":
                    obj.capacite = line.resultat
            #******************************************************************


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


    @api.onchange('type_cuve_id')
    def onchange_type_cuve_id(self):
        for obj in self:
            lines = []
            obj.calcul_ids=False
            if obj.type_cuve_id:
                for line in obj.type_cuve_id.calcul_ids:
                    vals = {
                        'devis_parametrable_id': obj.id,
                        'name'                 : line.name,
                        'description'          : line.description,
                        'formule'              : line.formule,
                        'formule_odoo'         : line.formule_odoo,
                        'resultat'             : line.resultat,
                        'unite'                : line.unite,
                        'lien_id'              : line.lien_id,
                    }
                    lines.append([0,False,vals])
                    commentaire = line.formule
            obj.calcul_ids=lines


class is_lien_odoo_excel(models.Model):
    _name = 'is.lien.odoo.excel'
    _description = "Codes pour déterminer les entrées et les sorties entre le devis et le calculateur"

    name = fields.Char("Code", help="Code du lien entre le devis et le calculateur")
    type_lien = fields.Selection([
            ('entree', "Donnée d'entrée"),
            ('sortie', "Donnée de sortie"),
        ], "Type de lien")
    commentaire = fields.Text("Commentaire")


class is_devis_parametrable_matiere(models.Model):
    _name = 'is.devis.parametrable.matiere'
    _description = "Matieres du devis paramètrable"
    _order='sequence,id'

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
    sequence   = fields.Integer("Sequence")
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
    _order='sequence,id'


    devis_id     = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    sequence     = fields.Integer("Sequence")
    dimension_id = fields.Many2one('is.dimension', 'Dimension')
    description  = fields.Char("Description"   , help="Information pour le client")
    valeur       = fields.Integer("Valeur (mm)", help="Utilisée dans les calculs")





class is_devis_parametrable_section(models.Model):
    _name = 'is.devis.parametrable.section'
    _description = "Sections du devis paramètrable"
    _order='sequence,id'


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

    devis_id      = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    sequence      = fields.Integer("Sequence")
    section_id    = fields.Many2one('is.section.devis', "Section")
    product_ids   = fields.One2many('is.devis.parametrable.section.product', 'section_id', 'Articles', copy=True)
    montant_total = fields.Float("Total", store=True, readonly=True, compute='_compute_montant')
    tps_montage   = fields.Float("Tps (HH:MM)", help="Temps de montatge (HH:MM)", store=True, readonly=True, compute='_compute_tps_montage')



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


    @api.depends('description','quantite')
    def _compute_description_report(self):
        for obj in self:
            description = obj.description or obj.product_id.name
            description = str(int(obj.quantite))+" x "+description
            obj.description_report = description


    section_id         = fields.Many2one('is.devis.parametrable.section', 'Section', required=True, ondelete='cascade')
    type_equipement_id = fields.Many2one('is.type.equipement', "Type d'équipement")
    product_id         = fields.Many2one('product.product', "Article")
    description        = fields.Text("Description")
    description_report = fields.Text("Description pour le rapport PDF", compute='_compute_description_report',)
    uom_po_id          = fields.Many2one('uom.uom', "Unité", help="Unité de mesure d'achat", related="product_id.uom_po_id", readonly=True)
    marge              = fields.Float("Marge (%)", help="Si ce champ n'est pas renseigné, la marge par défaut de la variante sera appliquée")
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
    description       = fields.Text("Description", readonly=True, compute='_compute_description')
    partner_id        = fields.Many2one('res.partner', "Client", related="devis_id.partner_id", readonly=True)

    quantite          = fields.Integer("Qt prévue")

    tps_montage       = fields.Float("Tps montage (HH:MM)"      , related="devis_id.tps_montage"   , readonly=True)
    tps_assemblage    = fields.Float("Tps assemblage (HH:MM)"   , related="devis_id.tps_assemblage", readonly=True)
    tps_majoration    = fields.Float("Tps majoration (HH:MM)"   , related="devis_id.tps_majoration", readonly=True)
    tps_minoration    = fields.Float("Tps minoration (HH:MM)"   , related="devis_id.tps_minoration", readonly=True)
    tps_total         = fields.Float("Tps total hors BE (HH:MM)", related="devis_id.tps_total"     , readonly=True)
    tps_be            = fields.Float("Tps BE (HH:MM)"           , related="devis_id.tps_be"        , readonly=True)

    marge_matiere     = fields.Float("Marge matière (%)")
    marge_equipement  = fields.Float("Marge équipement (%)")
    marge_montage     = fields.Float("Marge MO (%)")
    marge_be          = fields.Float("Marge BE (%)")
    marge_revendeur   = fields.Float("Marge revendeur (%)")
    gain_productivite = fields.Float("Gain de productivé (%)", help="En fonction de la quantité prévue, vous pouvez ajouter un gain de productivité sur le temps de montage des équipements")

    currency_id        = fields.Many2one('res.currency', "Devise", readonly=True, compute='_compute_montants')

    cout_horaire_montage = fields.Float('Coût horaire montage', default=lambda self: self.env.user.company_id.is_cout_horaire_montage)
    cout_horaire_be      = fields.Float('Coût horaire BE'     , default=lambda self: self.env.user.company_id.is_cout_horaire_be)

    montant_matiere    = fields.Monetary("Montant matière" , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_equipement = fields.Monetary("Montant equipements", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_montage    = fields.Monetary("Montant MO sans productivité"    , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_montage_productivite = fields.Monetary("Montant MO", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_be         = fields.Monetary("Montant BE"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_total      = fields.Monetary("Montant Total"       , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_unitaire   = fields.Monetary("Montant Unitaire HT" , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_matiere_pourcent              = fields.Float("% Montant matière"                  , readonly=True, compute='_compute_montants')
    montant_equipement_pourcent           = fields.Float("% Montant equipements"              , readonly=True, compute='_compute_montants')
    montant_montage_productivite_pourcent = fields.Float("% Montant MO avec productivité", readonly=True, compute='_compute_montants')
    montant_be_pourcent                   = fields.Float("% Montant BE"                       , readonly=True, compute='_compute_montants')

    prix_vente_lot              = fields.Monetary("Prix de vente de l'affaire"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    prix_vente_revendeur_lot    = fields.Monetary("Prix de vente revendeur de l'affaire", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_lot           = fields.Monetary("Marge de l'affaire"                  , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_revendeur_lot = fields.Monetary("Marge revendeur de l'affaire"        , readonly=True, compute='_compute_montants', currency_field='currency_id')

    prix_vente               = fields.Monetary("Prix de vente HT"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    prix_vente_int           = fields.Integer("Prix de vente HT (arrondi)" , readonly=True, compute='_compute_montants')
    montant_tva              = fields.Integer("TVA"                        , readonly=True, compute='_compute_montants')
    prix_vente_ttc           = fields.Integer("Prix de vente TTC"          , readonly=True, compute='_compute_montants')

    prix_vente_revendeur     = fields.Monetary("Prix de vente revendeur", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge            = fields.Monetary("Marge"                  , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_revendeur  = fields.Monetary("Marge revendeur"        , readonly=True, compute='_compute_montants', currency_field='currency_id')

    commentaire              = fields.Text("Commentaire")


    @api.depends('name')
    def _compute_description(self):
        for obj in self:
            d = obj.devis_id
            r="%s - %s - %s %s %s"%(d.designation, d.designation_complementaire, d.capacite, d.unite, d.type_cuve_id.name)
            # r+=devis.designation+"\n"
            # r+=devis.designation_complementaire+"\n"
            # r+=str(devis.capacite)+" "+devis.unite+" "+devis.type_cuve_id.name

            obj.description=r


    @api.depends('quantite','marge_matiere','marge_equipement','marge_montage','tps_be','marge_be','marge_revendeur','gain_productivite','cout_horaire_montage','cout_horaire_be')
    def _compute_montants(self):
        company = self.env.user.company_id
        for obj in self:
            obj.currency_id = company.currency_id.id
            quantite = obj.quantite or 1

            tps_montage        = obj.devis_id.tps_total*quantite
            montant_matiere    = obj.devis_id.montant_matiere*quantite
            montant_equipement = obj.devis_id.total_equipement*quantite
            montant_montage    = tps_montage*obj.cout_horaire_montage
            montant_montage_productivite = montant_montage-montant_montage*obj.gain_productivite/100
            montant_be         = obj.tps_be * obj.cout_horaire_be
            montant_total      = montant_matiere + montant_equipement + montant_montage_productivite + montant_be

            montant_matiere_pourcent = 0
            montant_equipement_pourcent = 0
            montant_montage_productivite_pourcent = 0
            montant_be_pourcent = 0
            if montant_total>0:
                montant_matiere_pourcent              = 100 * montant_matiere / montant_total
                montant_equipement_pourcent           = 100 * montant_equipement / montant_total
                montant_montage_productivite_pourcent = 100 * montant_montage_productivite / montant_total
                montant_be_pourcent                   = 100 * montant_be / montant_total
            obj.montant_matiere_pourcent = montant_matiere_pourcent
            obj.montant_equipement_pourcent = montant_equipement_pourcent
            obj.montant_montage_productivite_pourcent = montant_montage_productivite_pourcent
            obj.montant_be_pourcent = montant_be_pourcent

            montant_unitaire = montant_total/quantite

            #** Calcul du montant des équipements avec la marge par équipement **********
            montant_equipement_marge=0
            for section in obj.devis_id.section_ids:
                for product in section.product_ids:
                    marge = obj.marge_equipement
                    if product.marge>0:
                        marge=product.marge
                    montant_equipement_marge+=product.montant*(1+marge/100)
            #****************************************************************************

            prix_vente  = montant_matiere*(1+obj.marge_matiere/100)
            #prix_vente += montant_equipement*(1+obj.marge_equipement/100)
            prix_vente += montant_equipement_marge
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

            obj.prix_vente_revendeur_lot    = prix_vente_revendeur
            obj.montant_marge_lot           = prix_vente - montant_total
            obj.montant_marge_revendeur_lot = prix_vente_revendeur - prix_vente
            obj.prix_vente                  = prix_vente/quantite

            prix_vente_int = round(obj.prix_vente)
            obj.prix_vente_int = prix_vente_int
            obj.prix_vente_lot = prix_vente_int * quantite

            tva = obj.devis_id.tax_id.amount
            obj.montant_tva = obj.prix_vente_int * (tva/100)
            obj.prix_vente_ttc =  obj.prix_vente_int + obj.montant_tva

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

    name           = fields.Char("Type d'équipement", required=True)
    tps_montage    = fields.Float("Temps de montatge (HH:MM)")
    quantite_id    = fields.Many2one('is.lien.odoo.excel', 'Quantité')     # Données d'entrée
    prix_id        = fields.Many2one('is.lien.odoo.excel', 'Prix')         # Donnée de sortie
    description_id = fields.Many2one('is.lien.odoo.excel', 'Description')  # Donnée de sortie


class is_section_devis(models.Model):
    _name = 'is.section.devis'
    _description = "Section devis"
    _order='name'

    name                 = fields.Char("Section devis", required=True)
    epaisseur_matiere_id = fields.Many2one('is.lien.odoo.excel', 'Epaisseur matière')
    poids_matiere_id     = fields.Many2one('is.lien.odoo.excel', 'Poids matière')


class is_type_cuve(models.Model):
    _name='is.type.cuve'
    _description = "Type de cuve"
    _order='name'

    name          = fields.Char("Type de cuve", required=True)
    image         = fields.Binary("Image")
    perte_decoupe = fields.Integer("Perte à la découpe (%)")
    import_ids    = fields.Many2many('ir.attachment', 'is_type_cuve_import_ids_rel', 'type_cuve_id', 'attachment_id', 'Import xlsx')
    calcul_ids    = fields.One2many('is.type.cuve.calcul', 'type_cuve_id', 'Calculs', copy=True)


    def import_fichier_xlsx_action(self):
        for obj in self:
            obj.calcul_ids.unlink()
            for attachment in obj.import_ids:
                #xlsxfile = base64.decodestring(attachment.datas)

                xlsxfile=base64.b64decode(attachment.datas)  #.decode('latin-1') # 'latin-1' cp1252



                path = '/tmp/is_type_cuve-'+str(obj.id)+'.xlsx'
                f = open(path,'wb')
                f.write(xlsxfile)
                f.close()
                #*******************************************************************

                #** Test si fichier est bien du xlsx *******************************
                try:
                    #wb = openpyxl.load_workbook(filename = path)
                    wb_value    = openpyxl.load_workbook(filename = path, data_only=True)
                    ws_value    = wb_value.active
                    cells_value = list(ws_value)

                    wb_formula    = openpyxl.load_workbook(filename = path, data_only=False)
                    ws_formula    = wb_formula.active
                    cells_formula = list(ws_formula)
                except:
                    raise Warning(u"Le fichier "+attachment.name+u" n'est pas un fichier xlsx")
                #*******************************************************************


                #** Recherche de la colonne contenant les reperes des formules *****
                lig=0
                x={}
                for row in ws_value.rows:
                    col=0
                    for column in ws_value.columns:
                        if col not in x:
                            x[col]=0
                        val = cells_value[lig][col].value
                        if re.match(r"[A-Z][0-9]+", str(val)):
                            x[col]+=1
                        col+=1
                    lig+=1
                col=-1
                max=0
                for k in x:
                    if x[k]>max:
                        max=x[k]
                        col=k
                #*******************************************************************

                if col>=0:
                    lig=0
                    for row in ws_value.rows:
                        lien_id=False
                        lien = cells_value[lig][col+4].value
                        liens =  self.env['is.lien.odoo.excel'].search([('name','=',lien)])
                        for l in liens:
                            lien_id = l.id
                        name = cells_value[lig][col].value
                        if re.match(r"[A-Z][0-9]+", str(name)):
                            if cells_formula[lig][col+2].value:
                                vals={
                                    "type_cuve_id": obj.id,
                                    "sequence"    : lig,
                                    "name"        : name,
                                    "description" : cells_value[lig][col+1].value,
                                    "formule"     : cells_formula[lig][col+2].value,
                                    "unite"       : cells_value[lig][col+3].value,
                                    "lien_id"     : lien_id,
                                }
                                res = self.env['is.type.cuve.calcul'].create(vals)
                        lig+=1
            obj.recalculer_action()

    def recalculer_action(self):
        for obj in self:
            for line in obj.calcul_ids:
                line._compute_resultat(obj)


    def write(self, vals):
        res = super(is_type_cuve, self).write(vals)
        self.recalculer_action()
        return res


class is_type_cuve_calcul(models.Model):
    _name='is.type.cuve.calcul'
    _description = "Lignes de calcul du type de cuve"
    _order='sequence,id'

    type_cuve_id = fields.Many2one('is.type.cuve', 'Type de cuve')
    devis_parametrable_id = fields.Many2one('is.devis.parametrable', 'Devis paramètrable')
    sequence     = fields.Integer("Sequence")
    name         = fields.Char("Code")
    description  = fields.Char("Description")
    formule      = fields.Text("Formule")
    formule_odoo = fields.Text("Formule Odoo") #, compute='_compute_resultat', store=True, readonly=True)
    resultat     = fields.Float("Résultat")    #, compute='_compute_resultat', store=True, readonly=True)
    unite        = fields.Char("Unité")
    lien_id      = fields.Many2one('is.lien.odoo.excel', 'Lien Odoo Excel')
    proteger     = fields.Boolean("Protéger", default=True)
    proteger_formule = fields.Boolean("Protéger Formule", compute='_compute_proteger_formule', store=False, readonly=True)


    @api.depends('formule','proteger')
    def _compute_proteger_formule(self):
        for obj in self:
            proteger=False
            formule = obj.formule
            if formule and formule[:1]=="=" and obj.proteger:
                proteger=True
            obj.proteger_formule=proteger


    def str2float(self,x):
        try:
            resultat = float(x)
        except:
            return 0
        return resultat


    def str2eval(self,x):
        try:
            resultat = self.str2float(eval(x))
        except:
            return 0
        return resultat


    @api.depends('formule')
    def _compute_resultat(self, parent):
        for obj in self:
            formule  = obj.formule
            resultat = 0
            resultats={}
            #for line in obj.type_cuve_id.calcul_ids:
            for line in parent.calcul_ids:
                resultats[line.name]=line.resultat
            if formule and formule[:1]=="=":
                # ** Traitement fonction SUM **********************************
                pattern = re.compile(r'(SUM\([A-Z][0-9]+:[A-Z][0-9]+\))')
                res = pattern.findall(obj.formule)
                for line in res:
                    val=0
                    pattern2 = re.compile(r'([A-Z][0-9]+)')
                    res2 = pattern2.findall(line)
                    if len(res2)==2:
                        start=False
                        #for l in obj.type_cuve_id.calcul_ids:
                        for l in parent.calcul_ids:
                            if l.name==res2[0]:
                                start=True
                            if start:
                                val+=obj.str2float(l.resultat)
                            if l.name==res2[1]:
                                start=False
                    formule=formule.replace(line,str(val))
                # *************************************************************

                # ** Traitement fonction MAX **********************************
                pattern = re.compile(r'(MAX\([A-Z][0-9]+:[A-Z][0-9]+\))')
                res = pattern.findall(obj.formule)
                for line in res:
                    max=0
                    pattern2 = re.compile(r'([A-Z][0-9]+)')
                    res2 = pattern2.findall(line)
                    if len(res2)==2:
                        start=False
                        #for l in obj.type_cuve_id.calcul_ids:
                        for l in parent.calcul_ids:
                            val = obj.str2float(l.resultat)
                            if l.name==res2[0]:
                                start=True
                                max=val
                            if start:
                                if val>max:
                                    max=val
                            if l.name==res2[1]:
                                start=False
                    formule=formule.replace(line,str(max))
                # *************************************************************


                # ** Traitement fonction AVERAGE **********************************
                pattern = re.compile(r'(AVERAGE\([A-Z][0-9]+:[A-Z][0-9]+\))')
                res = pattern.findall(obj.formule)
                for line in res:
                    average=0
                    pattern2 = re.compile(r'([A-Z][0-9]+)')
                    res2 = pattern2.findall(line)
                    if len(res2)==2:
                        start=False
                        total=nb=0
                        #for l in obj.type_cuve_id.calcul_ids:
                        for l in parent.calcul_ids:
                            val = obj.str2float(l.resultat)
                            if l.name==res2[0]:
                                start=True
                            if start:
                                total+=val
                                nb+=1
                            if l.name==res2[1]:
                                start=False
                        if nb>0:
                            average=total/nb
                    formule=formule.replace(line,str(average))
                # *************************************************************



                pattern = re.compile(r'([A-Z][0-9]+)')
                res = pattern.findall(obj.formule)
                for line in res:
                    x = "0"
                    if line in resultats:
                        x = str(resultats[line])
                    formule=formule.replace(line,x)


                formule=formule.replace("PI()",str(pi))
                formule=formule.replace("TAN(","tan(")
                formule=formule.replace("^","**")



                formule=formule.replace("ROUNDDOWN(","round(")
                formule=formule.replace("ROUNDUP(","round(")
                formule=formule.replace("ROUND(","round(")




                # ** Traitement fonction IF ***********************************
                pattern = re.compile(r'(IF\(.*\))')
                res = pattern.findall(formule)
                for line in res:
                    pattern2 = re.compile(r'IF\((.*)\)')
                    res2 = pattern2.findall(line)
                    for line2 in res2:
                        t=line2.split(",")
                        if len(t)==3:
                            r1=obj.str2eval(t[0])
                            r2=obj.str2eval(t[1])
                            r3=obj.str2eval(t[2])
                            if r1:
                                resultat=r2
                            else:
                                resultat=r3
                            formule=formule.replace(line,str(resultat))
                # *************************************************************


                resultat = obj.str2eval(formule[1:])
            else:
                resultat=obj.str2float(formule)  
            obj.formule_odoo = formule
            obj.resultat = resultat







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

    name    = fields.Char("Dimension", required=True)
    lien_id = fields.Many2one('is.lien.odoo.excel', 'Lien Odoo Excel')

