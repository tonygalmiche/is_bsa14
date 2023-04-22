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
from math import pi,sin,cos,tan,sqrt, floor, ceil

_logger = logging.getLogger(__name__)


class is_devis_parametrable_affaire(models.Model):
    _name='is.devis.parametrable.affaire'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Affaire - Devis paramètrable"
    _order='write_date desc'

    name                 = fields.Char("Nom de l'affaire", required=True)
    code_affare          = fields.Char("Code de l'affaire", compute='_compute_code_affare', store=True, readonly=True, index=True)
    code_affare_force    = fields.Char("Code de l'affaire forcé")
    version              = fields.Char("Version")
    attention_de         = fields.Char("A l'attention de")
    image_affaire        = fields.Binary("Image affaire")
    is_societe_commerciale_id = fields.Many2one("is.societe.commerciale", "Société commerciale", readonly=True)
    partner_id           = fields.Many2one('res.partner', 'Revendeur / Client', required=True)
    date_affaire         = fields.Date("Date affaire")
    date_modification    = fields.Date("Date", help="Date de dernière modification utilisée dans les PDF", readonly=True)
    conditions_particulieres   = fields.Text("Conditions particulières")
    information_technique      = fields.Text("Informations techniques")
    information_complementaire = fields.Text("Informations complémentaires")
    conditions_reglement       = fields.Text("Conditions de règlement")
    delais                     = fields.Char("Délais")
    duree_validite             = fields.Char("Durée de validité de l'offre")
    transport                  = fields.Text("Transport")
    conditions_generales       = fields.Text("Conditions générales")
    vendeur_id                 = fields.Many2one('res.users', "Chargé d'affaire")

    variante_ids = fields.One2many('is.devis.parametrable.affaire.variante', 'affaire_id', 'Variantes', copy=True)

    tax_id      = fields.Many2one('account.tax', 'TVA à appliquer', readonly=True, compute='_compute_montants')
    currency_id = fields.Many2one('res.currency', "Devise"        , readonly=True, compute='_compute_montants')
    montant_ht  = fields.Monetary("Montant HT"                    , readonly=True, compute='_compute_montants', currency_field='devise_client_id')

    capacite          = fields.Integer("Capacité totale (HL)", compute='_compute_capacite', store=False, readonly=True)
    prix_par_hl       = fields.Integer("Prix par HL"         , compute='_compute_capacite', store=False, readonly=True)

    montant_tva = fields.Monetary("TVA"        , readonly=True, compute='_compute_montants', currency_field='devise_client_id')
    montant_ttc = fields.Monetary("Montant TTC", readonly=True, compute='_compute_montants', currency_field='devise_client_id')

    entete_ids        = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_entete_rel'       , 'affaire_id', 'attachment_id', 'Entête')
    recapitulatif_ids = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_recapitulatif_rel', 'affaire_id', 'attachment_id', 'Récapitulatif')
    pied_ids          = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_pied_rel'         , 'affaire_id', 'attachment_id', 'Pied')
    devis_ids         = fields.Many2many('ir.attachment', 'is_devis_parametrable_affaire_devis_rel'        , 'affaire_id', 'attachment_id', 'Devis')
    lead_id           = fields.Many2one('crm.lead', "Lien CRM", readonly=True)

    devise_client_id  = fields.Many2one('res.currency', "Devise Client", readonly=True, compute='_compute_montants')

    test_html = fields.Html(string="Test HTML", default="")




    def write(self, vals):
        vals["date_modification"] = fields.Date.today()
        res = super(is_devis_parametrable_affaire, self).write(vals)
        return res


    def name_get(self):
        result = []
        for obj in self:
            t=[]
            if obj.name:
                t.append(obj.name)
            if obj.code_affare:
                t.append(obj.code_affare)
            if obj.version:
                t.append(obj.version)
            if obj.montant_ht>0:
                #t.append("%.0f€"%(obj.montant_ht))
                x="{:,.0f} €".format(obj.montant_ht).replace(",", " ")
                t.append(x)
            name=" / ".join(t)
            result.append((obj.id, name))
        return result


    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        if args is None:
            args = []
        ids = []
        if len(name) >= 1:
            filtre=[
                '|',
                ('name'       , 'ilike', name),
                ('code_affare', 'ilike', name),

            ]
            ids = list(self._search(filtre + args, limit=limit))
        search_domain = [('name', operator, name)]
        if ids:
            search_domain.append(('id', 'not in', ids))
        ids += list(self._search(search_domain + args, limit=limit))
        return ids


    @api.depends('variante_ids')
    def _compute_capacite(self):
        for obj in self:
            capacite=0
            for line in obj.variante_ids:
                if line.unite!="HL":
                    capacite=0
                    break
                else:
                    capacite+=line.capacite*line.variante_id.quantite
            prix_par_hl=0
            if capacite>0:
                prix_par_hl = obj.montant_ht/capacite
            obj.capacite    = capacite
            obj.prix_par_hl = prix_par_hl


    # @api.depends('variante_ids')
    # def _compute_is_societe_commerciale_id(self):
    #     for obj in self:
    #         societe_id=False
    #         for line in obj.variante_ids:
    #             if line.variante_id.is_societe_commerciale_id:
    #                 societe_id = line.variante_id.is_societe_commerciale_id
    #                 break
    #         obj.is_societe_commerciale_id = societe_id
 

    @api.depends('create_date', 'partner_id', 'partner_id.is_code_client_affare','code_affare_force')
    def _compute_code_affare(self):
        for obj in self:
            code=False
            if obj.code_affare_force:
                code = obj.code_affare_force
            else:
                if obj.create_date and obj.partner_id:
                    code="%s-%s"%((obj.partner_id.is_code_client_affare or '????'), obj.create_date.strftime("%Y%m%d"))
                    affaires = self.env['is.devis.parametrable.affaire'].search([('code_affare','like',code)], order="code_affare desc", limit=1)
                    sequence=1
                    for affaire in affaires:
                        sequence=int(affaire.code_affare[-1:])+1
                    code="%s-%s"%(code,sequence)
            obj.code_affare = code


    @api.depends('variante_ids')
    def _compute_montants(self):
        company = self.env.user.company_id
        for obj in self:
            obj.currency_id = company.currency_id.id
            ht=tva=ttc=0
            tax_id = False
            devise_client_id = False
            for line in obj.variante_ids:
                tax_id = line.variante_id.devis_id.tax_id.id
                devise_client_id = line.variante_id.devise_client_id.id
                qt = line.quantite
                #prix_vente=line.variante_id.prix_vente_remise
                #ht+=prix_vente*qt
                ht+=line.montant
                tva+=line.variante_id.montant_tva*qt
                ttc+=line.variante_id.prix_vente_ttc*qt
            obj.montant_ht  = ht
            obj.montant_tva = tva
            obj.montant_ttc = ttc
            obj.tax_id      = tax_id
            obj.devise_client_id = devise_client_id


    def acceder_affaire_action(self):
        for obj in self:
            res={
                'name': 'Affaire',
                'view_mode': 'form',
                'res_model': 'is.devis.parametrable.affaire',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res


    def generer_pdf_action(self):
        for obj in self:
            #** Mise à jour société commerciale *******************************
            societe_id=False
            for line in obj.variante_ids:
                if line.variante_id.is_societe_commerciale_id:
                    societe_id = line.variante_id.is_societe_commerciale_id
                    break
            obj.is_societe_commerciale_id = societe_id

           #** Mise à jour lien CRM *******************************************
            lead_id=False
            leads = self.env['crm.lead'].search([('is_affaire_id','=',obj.id)],limit=1)
            for lead in leads:
                lead.expected_revenue = obj.montant_ht
                lead_id = lead.id
            obj.lead_id = lead_id

            ct = 1
            paths = []
            attachment_obj = self.env['ir.attachment']

            # #** delete files ************************************************
            path="/tmp/affaire_%s_*.pdf"%(obj.id)
            for file in glob(path):
                os.remove(file)

            #** Entête ajouté *************************************************
            if obj.entete_ids:
                for attachment in obj.entete_ids:
                    pdf=base64.b64decode(attachment.datas)
                    path="/tmp/affaire_%s_%02d_entete.pdf"%(obj.id,ct)
                    f = open(path,'wb')
                    f.write(pdf)
                    f.close()
                    paths.append(path)
                    ct+=1

            #** Entête généré *************************************************
            if not obj.entete_ids:
                pdf = request.env.ref('is_bsa14.action_report_devis_parametrable_affaire_entete').sudo()._render_qweb_pdf([obj.id])[0]
                path="/tmp/affaire_%s_%02d_entete.pdf"%(obj.id,ct)
                paths.append(path)
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                ct+=1

            #** Variantes *****************************************************
            for line in obj.variante_ids:
                if line.variante_id:
                    pdf = request.env.ref('is_bsa14.action_report_variante_devis_parametrable').sudo()._render_qweb_pdf([line.variante_id.id])[0]
                    path="/tmp/affaire_%s_%02d_variante.pdf"%(obj.id,ct)
                    paths.append(path)
                    f = open(path,'wb')
                    f.write(pdf)
                    f.close()
                    ct+=1

            #** Récapitulatif ajouté ******************************************
            if obj.recapitulatif_ids:
                for attachment in obj.recapitulatif_ids:
                    pdf=base64.b64decode(attachment.datas)
                    path="/tmp/affaire_%s_%02d_recapitulatif.pdf"%(obj.id,ct)
                    f = open(path,'wb')
                    f.write(pdf)
                    f.close()
                    paths.append(path)
                    ct+=1

            #** Récapitulatif généré ******************************************
            if not obj.recapitulatif_ids:
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


            #** CGV ***********************************************************
            if len(obj.is_societe_commerciale_id.cgv_ids)>0:
                company = self.env.user.company_id
                for attachment in obj.is_societe_commerciale_id.cgv_ids:
                    pdf=base64.b64decode(attachment.datas)
                    path="/tmp/affaire_%s_%02d_pied.pdf"%(obj.id,ct)
                    f = open(path,'wb')
                    f.write(pdf)
                    f.close()
                    paths.append(path)
                    ct+=1
            else:
                company = self.env.user.company_id
                for attachment in company.is_cgv_ids:
                    pdf=base64.b64decode(attachment.datas)
                    path="/tmp/affaire_%s_%02d_pied.pdf"%(obj.id,ct)
                    f = open(path,'wb')
                    f.write(pdf)
                    f.close()
                    paths.append(path)
                    ct+=1
            #******************************************************************




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
            if obj.version:
                name="BSA_OFFRE_%s_VERSION_%s.pdf"%(obj.code_affare,obj.version)
            else:
                name="BSA_OFFRE_%s.pdf"%(obj.code_affare)
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
    _order='sequence,variante_id'

    affaire_id  = fields.Many2one('is.devis.parametrable.affaire', 'Affaire', required=True, ondelete='cascade')
    sequence    = fields.Integer("Sequence")
    variante_id = fields.Many2one('is.devis.parametrable.variante', 'Variante')
    capacite    = fields.Integer("Capacité", related="variante_id.capacite", readonly=True)
    unite       = fields.Selection(related="variante_id.unite", readonly=True)
    quantite    = fields.Integer(related="variante_id.quantite", readonly=True)
    devise_client_id         = fields.Many2one(related="variante_id.devise_client_id")
    prix_vente_remise_devise = fields.Integer(related="variante_id.prix_vente_remise_devise")
    montant                  = fields.Integer("Montant", compute='_compute_montant', store=False, readonly=True)


    @api.depends('quantite',"prix_vente_remise_devise")
    def _compute_montant(self):
        for obj in self:
            obj.montant = obj.prix_vente_remise_devise * obj.quantite


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


    @api.depends('options_ids')
    def _compute_montant_option(self):
        for obj in self:
            montant=option_active=option_comprise=option_thermo=0
            for line in obj.options_ids:
                montant+=line.montant
                if line.option_active:
                    option_active+=line.montant
                if line.option_comprise:
                    option_comprise+=line.montant
                if line.option_active and line.thermoregulation:
                    option_thermo+=line.montant
            obj.montant_option = montant
            obj.montant_option_active   = option_active
            obj.montant_option_comprise = option_comprise
            obj.montant_option_thermo   = option_thermo


    @api.depends('capacite','unite')
    def _compute_capacite_txt(self):
        for obj in self:
            x = "%s %s"%(obj.capacite,obj.unite)
            obj.capacite_txt = x


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


    def _compute_affaire_ids(self):
        for obj in self:
            affaire_ids=[]
            for variante in obj.variante_ids:
                variantes = self.env['is.devis.parametrable.affaire.variante'].search([("variante_id","=",variante.id)])
                for v in variantes:
                    affaire_ids.append(v.affaire_id.id)
            obj.affaire_ids= [(6, 0, affaire_ids)]


    name                       = fields.Char("N°", readonly=True)
    nom_affaire                = fields.Char("Nom affaire")
    image                      = fields.Binary("Image", related="type_cuve_id.image")
    code_devis                 = fields.Char("Code devis")
    version                    = fields.Char("Version")
    designation                = fields.Char("Désignation")
    designation_complementaire = fields.Char("Désignation complémentaire")
    is_societe_commerciale_id  = fields.Many2one("is.societe.commerciale", "Société commerciale")
    capacite                   = fields.Integer("Capacité")
    unite                      = fields.Selection([
            ('Litre', 'Litre'),
            ('m3'   , 'm3'),
            ('HL'   , 'HL'),
        ], "Unité")

    capacite_txt       = fields.Char("Capacité ", compute='_compute_capacite_txt')
    type_cuve_id       = fields.Many2one('is.type.cuve', 'Type de cuve', required=True)
    calcul_ids         = fields.One2many('is.type.cuve.calcul', 'devis_parametrable_id', 'Calculs', copy=True)
    createur_id        = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation      = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    date_actualisation = fields.Datetime("Date d'actualisation"                , default=fields.Datetime.now)
    partner_id         = fields.Many2one('res.partner', 'Revendeur / Client', required=True)

    devise_client_id   = fields.Many2one('res.currency', "Devise Client", default=lambda self: self.env.user.company_id.currency_id.id)
    taux_devise        = fields.Float("Taux devise", default=1, digits=(12, 6), help="Nombre d'Euro pour une devise")

    tax_id             = fields.Many2one('account.tax', 'TVA à appliquer')
    tps_montage        = fields.Float("Tps montage (HH:MM)", help="Temps de montage (HH:MM)", store=False, readonly=True, compute='_compute_montant')
    tps_assemblage     = fields.Float("Tps assemblage (HH:MM)", readonly=True)
    tps_majoration     = fields.Float("Tps majoration (HH:MM)")
    tps_minoration     = fields.Float("Tps minoration (HH:MM)")
    tps_total          = fields.Float("Tps total hors BE (HH:MM)", store=False, readonly=True, compute='_compute_montant')
    tps_be             = fields.Float("Tps BE (HH:MM)", help="Le temps BE sera divisé par la quantité prévue dans les calculs")

    matiere_ids        = fields.One2many('is.devis.parametrable.matiere'  , 'devis_id', 'Matières'  , copy=True)
    dimension_ids      = fields.One2many('is.devis.parametrable.dimension', 'devis_id', 'Dimensions', copy=True)
    options_ids        = fields.One2many('is.devis.parametrable.option'   , 'devis_id', 'Options', copy=True)
    section_ids        = fields.One2many('is.devis.parametrable.section'  , 'devis_id', 'Sections'  , copy=True)
    variante_ids       = fields.One2many('is.devis.parametrable.variante' , 'devis_id', 'Variantes' , copy=True)
    affaire_ids        = fields.Many2many('is.devis.parametrable.affaire', 'is_devis_parametrable_affaire_rel', 'devis_id', 'affaire_id', compute='_compute_affaire_ids')
    total_equipement   = fields.Float("Total équipement"                     , store=False, readonly=True, compute='_compute_montant')
    montant_matiere    = fields.Float("Montant matière", store=False, readonly=True, compute='_compute_montant_matiere')
    montant_option     = fields.Float("Montant options", store=False, readonly=True, compute='_compute_montant_option')
    montant_option_active   = fields.Float("Montant options actives"  , store=False, readonly=True, compute='_compute_montant_option')
    montant_option_comprise = fields.Float("Montant options comprises", store=False, readonly=True, compute='_compute_montant_option')
    montant_option_thermo   = fields.Float("Montant options Thermorégulation", store=False, readonly=True, compute='_compute_montant_option')
    commentaire        = fields.Text("Commentaire")




    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.devis.parametrable')
        res = super(is_devis_parametrable, self).create(vals)
        return res


    def write(self, vals):
        res = super(is_devis_parametrable, self).write(vals)
        if "capacite" not in vals and "tps_assemblage" not in vals:
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

            for option in obj.options_ids:
                lien_id = option.option_id.lien_valeur_id
                if lien_id:
                    if lien_id.type_lien=="entree":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                line.formule=option.valeur

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
            for option in obj.options_ids:
                lien_id = option.option_id.lien_quantite_id
                if lien_id:
                    if lien_id.type_lien=="sortie":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                option.quantite= line.resultat
            for option in obj.options_ids:
                lien_id = option.option_id.lien_sortie2_id
                if lien_id:
                    if lien_id.type_lien=="sortie":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                option.sortie2= line.resultat
            for section in obj.section_ids:
                for product in section.product_ids:
                    lien_id = product.type_equipement_id.prix_id
                    if lien_id.type_lien=="sortie":
                        for line in obj.calcul_ids:
                            if line.lien_id==lien_id:
                                product.prix=line.resultat

            liens =  self.env['is.lien.odoo.excel'].search([('name','=',"tps_assemblage")])
            for lien in liens:
                for line in obj.calcul_ids:
                    if line.lien_id==lien:
                        obj.tps_assemblage=line.resultat

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
                    if res[0]>0:
                        line.prix       = res[0]
                        line.date_achat = res[1]
                section._compute_montant()




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
    imprimer           = fields.Boolean("Imprimer", help="Afficher cette ligne sur le PDF", default=True)


class is_devis_parametrable_unite(models.Model):
    _name = 'is.devis.parametrable.unite'
    _description = "Unités des dimensions du devis paramètrable"

    name = fields.Char("Unité", required=True)


class is_devis_parametrable_dimension(models.Model):
    _name = 'is.devis.parametrable.dimension'
    _description = "Dimensions du devis paramètrable"
    _order='sequence,id'

    def _get_unite_id(self):
        unite_id = False
        unites =  self.env['is.devis.parametrable.unite'].search([('name','=','mm')])
        for unite in unites:
            unite_id = unite.id
        return unite_id

    devis_id     = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    sequence     = fields.Integer("Sequence")
    dimension_id = fields.Many2one('is.dimension', 'Dimension')
    valeur       = fields.Integer("Valeur", help="Utilisée dans les calculs")
    unite_id     = fields.Many2one('is.devis.parametrable.unite', 'Unité', default=lambda self: self._get_unite_id())
    description  = fields.Char("Description"   , help="Information pour le client")
    imprimer     = fields.Boolean("Imprimer"   , help="Afficher cette ligne sur le PDF", default=True)


class is_devis_parametrable_option(models.Model):
    _name = 'is.devis.parametrable.option'
    _description = "Options du devis paramètrable"
    _order='sequence,id'

    devis_id           = fields.Many2one('is.devis.parametrable', 'Devis', required=True, ondelete='cascade')
    sequence           = fields.Integer("Sequence")
    option_id          = fields.Many2one('is.option', 'Option')
    description        = fields.Text("Description BSA" , help="Information pour le client (mettre [quantite] pour récupérer la quantité dans le PDF")
    description_client = fields.Text("Description Client", store=True, readonly=True, compute='_compute_description_client')
    valeur             = fields.Float("Valeur"     , help="Donnée d'entrée du calculateur")
    quantite           = fields.Float("Quantitée"  , help="Donnée de sortie du calculateur")
    prix               = fields.Float("Prix"       , help="Prix unitaire de l'option")
    montant            = fields.Float("Montant"            , store=True, readonly=True, compute='_compute_montant')
    montant_int        = fields.Integer("Montant (arrondi)", store=True, readonly=True, compute='_compute_montant')
    entree2            = fields.Float("Entrée 2")
    sortie2            = fields.Float("Sortie 2")
    option_active      = fields.Boolean("Active"  , default=True)
    option_comprise    = fields.Boolean("Comprise", default=True)
    thermoregulation   = fields.Boolean("Thermo.", help="Thermorégulation", related="option_id.thermoregulation")


    @api.onchange('option_id')
    def onchange_product_id(self):
        for obj in self:
            obj.description = obj.option_id.name
            obj.prix        = obj.option_id.prix


    @api.depends('option_id','quantite','prix')
    def _compute_montant(self):
        for obj in self:
            montant=0
            if obj.prix and obj.quantite:
                montant = obj.prix*obj.quantite
            montant_int = 10*ceil(montant/10)
            obj.montant     = montant
            obj.montant_int = montant_int


    @api.depends('description','valeur','quantite','prix','montant','entree2','sortie2')
    def _compute_description_client(self):
        for obj in self:
            val=""
            if obj.description:
                val=obj.description
                val = val.replace("[valeur]", str(round(obj.valeur,1)))
                val = val.replace("[quantite]", str(round(obj.quantite,1)))
                val = val.replace("[prix]", str(obj.prix))
                val = val.replace("[montant]", str(obj.montant))
                val = val.replace("[entree2]", str(obj.entree2))
                val = val.replace("[sortie2]", str(obj.sortie2))
            obj.description_client = val


class is_devis_parametrable_section(models.Model):
    _name = 'is.devis.parametrable.section'
    _description = "Sections du devis paramètrable"
    _order='sequence,id'


    @api.depends('product_ids')
    def _compute_montant(self):
        for obj in self:
            montant=montant_avec_marge=0
            for line in obj.product_ids:
                montant+=line.montant
                montant_avec_marge+=line.montant_avec_marge
            obj.montant_total = montant
            obj.montant_total_avec_marge = montant_avec_marge

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
    montant_total_avec_marge = fields.Float("Total avec marge", store=True, readonly=True, compute='_compute_montant')
    tps_montage   = fields.Float("Tps (HH:MM)", help="Temps de montage (HH:MM)", store=True, readonly=True, compute='_compute_tps_montage')



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
    _order='sequence,id'


    @api.onchange('product_id')
    def onchange_product_id(self):
        for obj in self:
            res = self.env['is.devis.parametrable'].get_prix_achat(obj.product_id)
            obj.prix        = res[0]
            obj.date_achat  = res[1]
            obj.description = obj.product_id.is_description_devis


    @api.depends('product_id','quantite','prix','marge')
    def _compute_montant(self):
        for obj in self:
            montant=montant_avec_marge=0
            if obj.prix and obj.quantite:
                montant = obj.prix*obj.quantite
            if montant:
                montant_avec_marge = montant+montant*obj.marge/100
            obj.montant = montant
            obj.montant_avec_marge = montant_avec_marge


    @api.depends('product_id','quantite','prix')
    def _compute_date_achat(self):
        for obj in self:
            res = self.env['is.devis.parametrable'].get_prix_achat(obj.product_id)
            obj.date_achat=res[1]


    @api.depends('type_equipement_id','product_id','quantite','tps_montage_force')
    def _compute_tps_montage(self):
        for obj in self:
            tps=0
            if obj.tps_montage_force>0:
                tps = obj.tps_montage_force
            else:
                if obj.product_id and obj.product_id.is_type_equipement_id:
                    tps+=obj.product_id.is_type_equipement_id.tps_montage*obj.quantite
            obj.tps_montage = tps


    @api.depends('description','quantite')
    def _compute_description_report(self):
        for obj in self:
            description = obj.description or obj.product_id.name or ''
            description = str(int(obj.quantite))+" x "+description
            obj.description_report = description

    
    sequence           = fields.Integer("Sequence")
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
    montant_avec_marge = fields.Float("Montant avec marge", store=True, readonly=True, compute='_compute_montant')
    tps_montage        = fields.Float("Tps (HH:MM)"      , help="Temps de montage (HH:MM)", store=True, readonly=True, compute='_compute_tps_montage')
    tps_montage_force  = fields.Float("Tps forcé (HH:MM)", help="Si ce temps est renseigné, il remplacera le champ 'Tps (HH:MM)'")


class is_devis_parametrable_variante(models.Model):
    _name = 'is.devis.parametrable.variante'
    _description = "Variantes du devis paramètrable"


    devis_id          = fields.Many2one('is.devis.parametrable', 'Devis paramètrable', required=True, ondelete='cascade')
    name              = fields.Char("Nom", required=True)
    description       = fields.Text("Description", readonly=True, compute='_compute_description')
    partner_id        = fields.Many2one('res.partner', "Client"        , related="devis_id.partner_id"      , readonly=True)
    capacite          = fields.Integer("Capacité", related="devis_id.capacite", readonly=True)
    unite             = fields.Selection(related="devis_id.unite", readonly=True)

    is_societe_commerciale_id = fields.Many2one("is.societe.commerciale", "Société commerciale", related="devis_id.is_societe_commerciale_id", readonly=True)
    quantite          = fields.Integer("Qt prévue")
    currency_id       = fields.Many2one('res.currency', "Devise", readonly=True, compute='_compute_montants')

    tps_montage       = fields.Float("Tps montage (HH:MM)"      , related="devis_id.tps_montage"   , readonly=True)
    tps_assemblage    = fields.Float("Tps assemblage (HH:MM)"   , related="devis_id.tps_assemblage", readonly=True)
    tps_majoration    = fields.Float("Tps majoration (HH:MM)"   , related="devis_id.tps_majoration", readonly=True)
    tps_minoration    = fields.Float("Tps minoration (HH:MM)"   , related="devis_id.tps_minoration", readonly=True)
    tps_total         = fields.Float("Tps total hors BE (HH:MM)", related="devis_id.tps_total"     , readonly=True)
    tps_be            = fields.Float("Tps BE (HH:MM)"           , related="devis_id.tps_be"        , readonly=True)

    cout_horaire_montage = fields.Monetary('Coût horaire montage', default=lambda self: self.env.user.company_id.is_cout_horaire_montage, currency_field='currency_id')
    cout_horaire_be      = fields.Monetary('Coût horaire BE'     , default=lambda self: self.env.user.company_id.is_cout_horaire_be     , currency_field='currency_id')
    cout_transport    = fields.Monetary("Coût du transport", currency_field='currency_id')

    marge_matiere     = fields.Float("Marge matière (%)")
    marge_equipement  = fields.Float("Marge équipements (%)")
    marge_option      = fields.Float("Marge options (%)")
    marge_montage     = fields.Float("Marge MO (%)")
    marge_be          = fields.Float("Marge BE (%)")
    marge_revendeur   = fields.Float("Marge revendeur (%)")
    gain_productivite = fields.Float("Gain de productivé (%)", help="En fonction de la quantité prévue, vous pouvez ajouter un gain de productivité sur le temps de montage des équipements")
    remise            = fields.Monetary("Remise")
    remise_pourcent   = fields.Float("Remise (%)")

    montant_matiere    = fields.Monetary("Montant matière"     , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_equipement = fields.Monetary("Montant equipements" , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_option     = fields.Monetary("Montant options"     , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_montage    = fields.Monetary("Montant MO sans productivité"    , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_montage_productivite = fields.Monetary("Montant MO", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_be         = fields.Monetary("Montant BE"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_transport  = fields.Monetary("Montant transport"   , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_total      = fields.Monetary("Montant Total"       , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_unitaire   = fields.Monetary("Montant Unitaire HT" , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_matiere_pourcent              = fields.Float("% Montant matière"                  , readonly=True, compute='_compute_montants')
    montant_equipement_pourcent           = fields.Float("% Montant equipements"              , readonly=True, compute='_compute_montants')
    montant_option_pourcent               = fields.Float("% Montant options"                  , readonly=True, compute='_compute_montants')
    montant_montage_productivite_pourcent = fields.Float("% Montant MO avec productivité"     , readonly=True, compute='_compute_montants')
    montant_be_pourcent                   = fields.Float("% Montant BE"                       , readonly=True, compute='_compute_montants')
    montant_transport_pourcent            = fields.Float("% Montant transport"                , readonly=True, compute='_compute_montants')
    montant_remise                        = fields.Integer("Montant remise"                   , readonly=True, compute='_compute_montants')
    intitule_remise                       = fields.Char("Intitulé remise"                     , readonly=True, compute='_compute_montants')

    prix_vente_lot              = fields.Monetary("Prix de vente de l'affaire"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    prix_vente_revendeur_lot    = fields.Monetary("Prix de vente revendeur de l'affaire", readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_lot           = fields.Monetary("Marge de l'affaire"                  , readonly=True, compute='_compute_montants', currency_field='currency_id')
    montant_marge_revendeur_lot = fields.Monetary("Marge revendeur de l'affaire"        , readonly=True, compute='_compute_montants', currency_field='currency_id')

    prix_vente               = fields.Monetary("Prix de vente HT"          , readonly=True, compute='_compute_montants', currency_field='currency_id')
    prix_vente_int           = fields.Integer("Prix de vente HT (arrondi)" , readonly=True, compute='_compute_montants')
    prix_vente_remise        = fields.Integer("Prix de vente remisé"       , readonly=True, compute='_compute_montants')
    prix_par_hl              = fields.Integer("Prix par HL"                , readonly=True, compute='_compute_montants')
    afficher_prix_par_hl     = fields.Boolean("Afficher prix par HL", default=False)
    montant_tva              = fields.Integer("TVA"                        , readonly=True, compute='_compute_montants')
    prix_vente_ttc           = fields.Integer("Prix de vente TTC"          , readonly=True, compute='_compute_montants')

    prix_vente_revendeur     = fields.Monetary("Prix de vente revendeur"   , readonly=True, compute='_compute_montants', currency_field='currency_id')
    #prix_vente_revendeur_int = fields.Integer("Prix de vente revendeur (arrondi)", readonly=True, compute='_compute_montants')

    montant_marge            = fields.Monetary("Marge"                     , readonly=True, compute='_compute_montants', currency_field='currency_id')
    taux_marge_brute         = fields.Float("Taux de marge brute (%)"      , readonly=True, compute='_compute_montants')
    taux_marge_commerciale   = fields.Float("Taux de marge commerciale (%)", readonly=True, compute='_compute_montants')
    montant_marge_revendeur  = fields.Monetary("Marge revendeur"           , readonly=True, compute='_compute_montants', currency_field='currency_id')

    commentaire              = fields.Text("Commentaire")

    #Montants en devises 
    devise_client_id         = fields.Many2one('res.currency', "Devise Client", related="devis_id.devise_client_id", readonly=True)
    taux_devise              = fields.Float("Taux devise"                     , related="devis_id.taux_devise"     , readonly=True)
    prix_vente_devise        = fields.Monetary("Prix de vente HT (Devise)"        , readonly=True, compute='_compute_montants', currency_field='devise_client_id')
    prix_vente_int_devise    = fields.Integer("Prix de vente HT (arrondi)(Devise)", readonly=True, compute='_compute_montants')
    montant_remise_devise    = fields.Integer("Montant remise (Devise)"           , readonly=True, compute='_compute_montants')
    intitule_remise_devise   = fields.Char("Intitulé remise (Devise)"             , readonly=True, compute='_compute_montants')
    prix_vente_remise_devise = fields.Integer("Prix de vente remisé (Devise)"     , readonly=True, compute='_compute_montants')
    prix_par_hl_devise       = fields.Integer("Prix par HL (Devise)"              , readonly=True, compute='_compute_montants')


    @api.depends('name','quantite')
    def _compute_description(self):
        for obj in self:
            d = obj.devis_id
            r="%s x %s - %s - %s %s %s"%(obj.quantite, (d.designation or ''), (d.designation_complementaire or ''), d.capacite, d.unite, d.type_cuve_id.name)
            # r+=devis.designation+"\n"
            # r+=devis.designation_complementaire+"\n"
            # r+=str(devis.capacite)+" "+devis.unite+" "+devis.type_cuve_id.name

            obj.description=r


    @api.depends('remise','remise_pourcent','quantite','marge_matiere','marge_equipement','marge_option','marge_montage','tps_be','marge_be','marge_revendeur','gain_productivite','cout_horaire_montage','cout_horaire_be')
    def _compute_montants(self):
        company = self.env.user.company_id
        for obj in self:
            obj.currency_id = company.currency_id.id
            quantite = obj.quantite or 1

            tps_montage        = obj.devis_id.tps_total*quantite
            montant_matiere    = obj.devis_id.montant_matiere*quantite
            montant_equipement = obj.devis_id.total_equipement*quantite
            montant_option     = obj.devis_id.montant_option_comprise*quantite
            montant_montage    = tps_montage*obj.cout_horaire_montage
            montant_montage_productivite = montant_montage-montant_montage*obj.gain_productivite/100
            montant_be         = obj.tps_be * obj.cout_horaire_be
            montant_transport  = obj.cout_transport*quantite

            montant_total      = montant_matiere + montant_equipement + montant_option + montant_montage_productivite + montant_be + montant_transport

            montant_matiere_pourcent = 0
            montant_equipement_pourcent = 0
            montant_option_pourcent = 0
            montant_montage_productivite_pourcent = 0
            montant_be_pourcent = 0
            montant_transport_pourcent = 0
            if montant_total>0:
                montant_matiere_pourcent              = 100 * montant_matiere / montant_total
                montant_equipement_pourcent           = 100 * montant_equipement / montant_total
                montant_option_pourcent               = 100 * montant_option / montant_total
                montant_montage_productivite_pourcent = 100 * montant_montage_productivite / montant_total
                montant_be_pourcent                   = 100 * montant_be / montant_total
                montant_transport_pourcent            = 100 * montant_transport / montant_total
            obj.montant_matiere_pourcent    = montant_matiere_pourcent
            obj.montant_equipement_pourcent = montant_equipement_pourcent
            obj.montant_option_pourcent     = montant_option_pourcent
            obj.montant_montage_productivite_pourcent = montant_montage_productivite_pourcent
            obj.montant_be_pourcent = montant_be_pourcent
            obj.montant_transport_pourcent = montant_transport_pourcent

            montant_unitaire = montant_total/quantite

            #** Calcul du montant des équipements avec la marge par équipement **********
            montant_equipement_marge=0
            for section in obj.devis_id.section_ids:
                for product in section.product_ids:
                    marge = obj.marge_equipement
                    if product.marge>0:
                        marge=product.marge
                    montant_equipement_marge+=product.montant*(1+marge/100)*quantite
            #****************************************************************************

            prix_vente  = montant_matiere*(1+obj.marge_matiere/100)
            prix_vente += montant_equipement_marge
            prix_vente += montant_option*(1+obj.marge_option/100)
            prix_vente += montant_montage_productivite*(1+obj.marge_montage/100)
            prix_vente += montant_be*(1+obj.marge_be/100)
            prix_vente += montant_transport


            obj.montant_matiere    = montant_matiere
            obj.montant_equipement = montant_equipement
            obj.montant_option     = montant_option
            obj.tps_montage        = tps_montage
            obj.montant_montage    = montant_montage
            obj.montant_montage_productivite = montant_montage_productivite
            obj.montant_be         = montant_be
            obj.montant_transport  = montant_transport
            obj.montant_total      = montant_total
            obj.montant_unitaire   = montant_unitaire


            prix_vente_int = 10*ceil(prix_vente/quantite/10)
            obj.prix_vente_int = prix_vente_int

            montant_remise=0
            if obj.remise>0:
                montant_remise = obj.remise
            else:
                if obj.remise_pourcent>0:
                    montant_remise = prix_vente_int*obj.remise_pourcent/100
            obj.montant_remise = montant_remise

            intitule_remise=False
            if obj.remise_pourcent>0:
                intitule_remise="Remise de %s%% soit %s €"%(obj.remise_pourcent, obj.montant_remise)
            if obj.remise>0:
                intitule_remise="Remise de %s €"%(obj.montant_remise)
            obj.intitule_remise = intitule_remise
            obj.prix_vente_remise = prix_vente_int - montant_remise

            prix_par_hl=False
            if obj.devis_id.capacite>0:
                prix_par_hl=obj.prix_vente_remise/obj.devis_id.capacite
            obj.prix_par_hl = prix_par_hl

            obj.prix_vente_lot = obj.prix_vente_remise * quantite

            prix_vente_revendeur = obj.prix_vente_remise*(1+obj.marge_revendeur/100)
            obj.prix_vente_revendeur_lot    = prix_vente_revendeur*quantite
            obj.montant_marge_lot           = obj.prix_vente_lot - montant_total
            obj.montant_marge_revendeur_lot = obj.prix_vente_revendeur_lot  - obj.prix_vente_lot
            obj.prix_vente                  = prix_vente/quantite


            obj.prix_vente_revendeur    = prix_vente_revendeur

            #prix_vente_revendeur_int = 10*ceil(prix_vente_revendeur/10)
            #obj.prix_vente_revendeur_int = prix_vente_revendeur_int

            obj.montant_marge           = obj.prix_vente_remise - montant_unitaire


            taux_marge_brute = 0
            if obj.prix_vente>0:
                taux_marge_brute = 100*(obj.prix_vente-obj.montant_equipement/quantite-obj.montant_matiere/quantite)/obj.prix_vente
            obj.taux_marge_brute = taux_marge_brute

            taux_marge_commerciale = 0
            if obj.prix_vente_remise>0:
                taux_marge_commerciale  = 100*obj.montant_marge / obj.prix_vente_remise
            obj.taux_marge_commerciale = taux_marge_commerciale

            obj.montant_marge_revendeur = prix_vente_revendeur - obj.prix_vente_remise


            #** Montants en devise ********************************************
            taux = obj.taux_devise or 1
            obj.prix_vente_devise     = obj.prix_vente     / taux
            obj.prix_par_hl_devise    = obj.prix_par_hl    / taux
            obj.prix_vente_int_devise = 10*ceil(obj.prix_vente_devise/10)
            montant_remise=0
            if obj.remise>0:
                montant_remise = obj.remise
            else:
                if obj.remise_pourcent>0:
                    montant_remise = obj.prix_vente_int_devise*obj.remise_pourcent/100
            obj.montant_remise_devise = montant_remise
            intitule_remise=False
            if obj.remise_pourcent>0:
                intitule_remise="Remise de %s%% soit %s %s"%(obj.remise_pourcent, obj.montant_remise_devise, obj.devise_client_id.symbol)
            if obj.remise>0:
                intitule_remise="Remise de %s €"%(obj.montant_remise_devise)
            obj.intitule_remise_devise = intitule_remise
            obj.prix_vente_remise_devise = obj.prix_vente_int_devise - obj.montant_remise_devise

            tva = obj.devis_id.tax_id.amount
            obj.montant_tva = obj.prix_vente_remise_devise * (tva/100)
            obj.prix_vente_ttc =  obj.prix_vente_remise_devise + obj.montant_tva
            #******************************************************************





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


    def get_montant_option(self,option):
        montant=0
        for obj in self:
            montant = option.montant*(1+obj.marge_option/100)
            montant = 10*ceil(montant/10)
        return montant


class is_type_equipement(models.Model):
    _name = 'is.type.equipement'
    _description = "Type d'équipement"
    _order='name'

    name           = fields.Char("Type d'équipement", required=True)
    tps_montage    = fields.Float("Temps de montage (HH:MM)")
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
                            #if cells_formula[lig][col+2].value:
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
    formule_odoo = fields.Text("Formule Odoo") 
    resultat     = fields.Float("Résultat", digits=(14,4))
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
                formule=formule.replace("SIN(","sin(")
                formule=formule.replace("COS(","cos(")
                formule=formule.replace("TAN(","tan(")
                formule=formule.replace("^","**")



                formule=formule.replace("ROUNDDOWN(","round(")
                formule=formule.replace("ROUNDUP(","round(")
                formule=formule.replace("ROUND(","round(")
                formule=formule.replace("SQRT(","sqrt(")
                formule=formule.replace("INT(","floor(")





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



class is_option(models.Model):
    _name='is.option'
    _description = "Option"
    _order='name'

    name             = fields.Char("Option", required=True)
    prix             = fields.Float("Prix uniaire", help="ex: Mettre le prix en m2 pour la régulation thermique")
    lien_valeur_id   = fields.Many2one('is.lien.odoo.excel', 'Lien Odoo Excel Valeur (Entrée)')
    lien_quantite_id = fields.Many2one('is.lien.odoo.excel', 'Lien Odoo Excel Quantité (Sortie)')
    lien_entree2_id  = fields.Many2one('is.lien.odoo.excel', 'Lien Odoo Excel Entrée 2')
    lien_sortie2_id  = fields.Many2one('is.lien.odoo.excel', 'Lien Odoo Excel Sortie 2')
    thermoregulation = fields.Boolean("Thermorégulation", default=False)

