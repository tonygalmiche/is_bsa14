# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.http import request
import codecs
import unicodedata
import base64
from datetime import date,timedelta


class IsRelanceFactureLigne(models.Model):
    _name = 'is.relance.facture.ligne'
    _description = "Lignes des relances de factures"
    _order='sequence,id'


    @api.depends('invoice_id')
    def _compute(self):
        for obj in self:
            obj.amount_residual  = obj.invoice_id.amount_residual
            obj.partner_id       = obj.invoice_id.partner_id.id
            obj.contact_id       = obj.partner_id.is_contact_relance_facture_id.id or obj.partner_id.id
            obj.invoice_date     = obj.invoice_id.invoice_date
            obj.invoice_date_due = obj.invoice_id.invoice_date_due


    relance_id       = fields.Many2one('is.relance.facture', 'Relance facture', required=True, ondelete='cascade')
    sequence         = fields.Integer("Ordre")
    invoice_id       = fields.Many2one('account.move', 'Facture', required=True, domain=[
        ("state","=","posted"),("move_type","=","out_invoice"),('payment_state',"=","not_paid")
    ])

    currency_id      = fields.Many2one('res.currency', related='invoice_id.currency_id')
    amount_residual  = fields.Monetary(string="Montant dû"           , compute='_compute', readonly=True, store=True)
    partner_id       = fields.Many2one('res.partner', string="Client", compute='_compute', readonly=True, store=True)
    contact_id       = fields.Many2one('res.partner', 'Contact'      , compute='_compute', readonly=True, store=True)
    invoice_date     = fields.Date(string="Date facture"             , compute='_compute', readonly=True, store=True)
    invoice_date_due = fields.Date(string="Date d'échéance"          , compute='_compute', readonly=True, store=True)
    
    is_date_relance         = fields.Date(related='invoice_id.is_date_relance')
    is_num_relance          = fields.Integer(related='invoice_id.is_num_relance')
    is_intitule_relance     = fields.Char(related='invoice_id.is_intitule_relance')

    is_date_envoi    = fields.Date(related='invoice_id.is_date_envoi')
    email            = fields.Char(related='contact_id.email')
    payment_state    = fields.Selection(related='invoice_id.payment_state')
    is_remarque_paiement   = fields.Char(related='invoice_id.is_remarque_paiement')


    def voir_facture_action(self):
        for obj in self:
            return {
                "name": obj.relance_id.name,
                "view_mode": "form,tree",
                "res_model": "account.move",
                "res_id"   : obj.invoice_id.id,
                "type": "ir.actions.act_window",
            }


class IsRelanceFacture(models.Model):
    _name = 'is.relance.facture'
    _description = "Relances de factures"
    _order = 'name desc'

    @api.depends('ligne_ids')
    def _compute(self):
        currency=self.env.user.company_id.currency_id
        for obj in self:
            amount_residual=0
            for line in obj.ligne_ids:
                amount_residual+=line.amount_residual
            obj.amount_residual = amount_residual
            obj.currency_id = currency.id

    name          = fields.Char("N°", readonly=True)
    type_document = fields.Selection([
            ('relance_facture', 'Relance de facture'),
            ('releve_facture' , 'Relevé de facture'),
            ('envoi_facture'  , 'Envoi des factures'),
        ], 'Type de document', readonly=True)
    partner_id          = fields.Many2one('res.partner', string="Client")
    nb_jours            = fields.Integer("Nombre de jours de retard mini", default=1)
    nb_jours_relance    = fields.Integer("Nombre de jours depuis la dernière relance", default=14)
    nb_jours_echeance   = fields.Integer("Nombre de jours avant l'échéance", default=7)
    ligne_ids           = fields.One2many('is.relance.facture.ligne', 'relance_id', 'Lignes')
    currency_id         = fields.Many2one('res.currency'     , compute='_compute', readonly=True, store=True)
    amount_residual     = fields.Monetary(string="Montant dû", compute='_compute', readonly=True, store=True)
    state      = fields.Selection([
            ('brouillon', 'Brouillon'),
            ('envoye'   , 'Envoyé'),
        ], 'État', default='brouillon')

    payment_state = fields.Selection([
            ('not_paid', 'Non payé'),
            ('partial'   , 'Partiellement réglé'),
        ], 'État du paiement')


    @api.onchange('type_document','nb_jours','nb_jours_relance','nb_jours_echeance','partner_id','payment_state')
    def cherche_factures(self):
        for obj in self:
            date_maxi          = date.today()-timedelta(days=obj.nb_jours)
            date_maxi_relance  = date.today()-timedelta(days=obj.nb_jours_relance)
            date_maxi_echeance = date.today()+timedelta(days=obj.nb_jours_echeance)
            lines=[]
            filtre=[
                ("state","=","posted"),
                ("move_type","in",('out_invoice','out_refund')),
            ]
            if obj.payment_state:
                filtre.append(("payment_state","=",obj.payment_state))
            else:
                filtre.append(('payment_state',"not in",('paid','reversed')))
            if obj.partner_id:
                filtre.append(("partner_id","=",obj.partner_id.id))
            if obj.type_document=="relance_facture":
                filtre.append(
                    ('invoice_date_due','<=',date_maxi)
                )
            if obj.type_document=="releve_facture":
                filtre.append(
                    ('invoice_date_due','>=',date.today())
                )
                filtre.append(
                    ('invoice_date_due','<=',date_maxi_echeance)
                )
                filtre.append(
                    ('is_date_releve','=',False)
                )
            if obj.type_document=="envoi_facture":
                filtre.append(
                    ('is_date_envoi','=',False)
                )
                filtre.append(
                    ('invoice_date','>=','2024-07-01')
                )
            invoices = self.env['account.move'].search(filtre, order="partner_id,name")
            for invoice in invoices:
                if obj.type_document=="relance_facture":
                    if invoice.is_date_relance==False or invoice.is_date_relance<=date_maxi_relance:
                        vals = {
                            'invoice_id': invoice.id
                        }
                        lines.append([0,0,vals])
                if obj.type_document=="releve_facture":
                    if invoice.is_date_releve==False or invoice.is_date_releve<=date_maxi_echeance:
                        vals = {
                            'invoice_id': invoice.id
                        }
                        lines.append([0,0,vals])
                if obj.type_document=="envoi_facture":
                    if invoice.is_date_envoi==False:
                        vals = {
                            'invoice_id': invoice.id
                        }
                        lines.append([0,0,vals])
            obj.ligne_ids = False
            obj.ligne_ids = lines


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.relance.facture')
        res = super(IsRelanceFacture, self).create(vals)
        return res


    def voir_factures_action(self):
        for obj in self:
            tree_id = self.env.ref('is_bsa14.is_view_invoice_tree').id
            ids=[]
            for line in obj.ligne_ids:
                ids.append(line.invoice_id.id)
            return {
                "name": obj.name,
                "view_mode": "tree,form",
                "res_model": "account.move",
                "type": "ir.actions.act_window",
                "domain": [
                    ('id','in',ids),
                ],
                "views": [[tree_id, "tree"],[False, "form"]],
            }


    def generer_relance_action(self):
        for obj in self:
            mails={}
            for line in obj.ligne_ids:
                if line.email:
                    partner=line.invoice_id.partner_id
                    if partner not in mails:
                        mails[partner]=[]
                    mails[partner].append(line.invoice_id)
            for partner in mails:
                obj.send_mail(partner,mails[partner])
            obj.state="envoye"
        




#            x = "{:,.%sf}"%nb_decimales
#            txt = x.format(val).replace(","," ").replace(".",",")

    def float2str(self,val, nb_decimales=2):
        x = "{:,.%sf}"%nb_decimales
        txt = x.format(val).replace(","," ").replace(".",",")
        return txt


    def send_mail(self, partner, invoices):
        #** Suppression des abonnés à la facture ******************************
        for invoice in invoices:
            invoice.sudo().message_follower_ids.unlink()
        #**********************************************************************

        invoice=invoices[0]
        template = self.env.ref('account.email_template_edi_invoice', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model="account.move",
            default_res_id=invoice.id,
            default_composition_mode='comment',
            custom_layout='mail.mail_notification_light', #Permet de définir la mise en page du mail
        )
         #** Génération de la facture avec le numero de relance **********
        attachment_ids=[]
        for invoice in invoices:
            invoice.is_num_relance+=1
            # filtre=[
            #     ("res_model","=","account.move"),
            #     ("res_id","=",invoice.id),
            # ]
            # self.env['ir.attachment'].search(filtre).unlink()
            attachment=False
            pdf = request.env.ref('account.account_invoices_without_payment').sudo()._render_qweb_pdf([invoice.id])[0]

            # pdfs = base64.b64encode(pdfs)
            print(type(pdf), len(pdf))

            vals={
                'name'       : "%s.pdf"%invoice.name,
                #'type'       : 'binary', 
                'res_id'     : invoice.id,
                'res_model'  : "account.move",
                'datas'      : base64.b64encode(pdf),
                #'mimetype'   : 'application/x-pdf',
            }
            attachment = self.env['ir.attachment'].create(vals)
            print(attachment)
            attachment_ids.append(attachment.id)


            # attachment_id=False
            # if attachments:
            #     for attachment in attachments:
            #         attachment.write(vals)
            #         attachment_id=attachment.id
            # else:
            #     attachment = attachment_obj.create(vals)


            # if pdf:
            #     attachments = self.env['ir.attachment'].search(filtre,limit=1,order="id desc")
            #     if len(attachments)>0:
            #         attachment=attachments[0]
            # if attachment:
            #     print(attachment)
            #     attachment_ids.append(attachment.id)
        #**********************************************************************

        #** body **************************************************************
        if self.type_document=="envoi_facture":
            if len(invoices)>1:
                body="""<p>Bonjour,</p><p>Nous vous prions de trouver ci-joint nos factures:</p>"""
            else:
                body="""<p>Bonjour,</p><p>Nous vous prions de trouver ci-joint notre facture:</p>"""

            total=0
            for invoice in invoices:
                total+=invoice.amount_residual
                body+="- Facture N°%s à l'échéance du %s pour un montant de %s € <br>"%(invoice.name, invoice.invoice_date_due.strftime('%d/%m/%Y'), self.float2str(invoice.amount_residual))
            body+="""
                <p>Total à devoir : %s €</p> 
                <br>
                <p>Vous en souhaitant bonne réception,</p> 
                <p>Cordialement</p> 
            """%(self.float2str(total))

        if self.type_document=="relance_facture":
            if len(invoices)>1:
                body="""<p>Bonjour,</p><p>Sauf erreur de notre part, les factures ci-dessous restent impayées:</p>"""
            else:
                body="""<p>Bonjour,</p><p>Sauf erreur de notre part, la facture ci-dessous reste impayée:</p>"""

            total=0
            for invoice in invoices:
                total+=invoice.amount_residual
                body+="- Facture N°%s à l'échéance du %s pour un montant de %s € <br>"%(invoice.name, invoice.invoice_date_due.strftime('%d/%m/%Y'), self.float2str(invoice.amount_residual))
            body+="""
                <p>Total à devoir : %s €</p> 
                <p>Merci de régulariser votre compte</p> 
            """%(self.float2str(total))
        if self.type_document=="releve_facture":
            if len(invoices)>1:
                body="""<p>Bonjour,</p><p>Veuillez trouver ci-dessous les factures à échéance ces prochains jours:</p>"""
            else:
                body="""<p>Bonjour,</p><p>Veuillez trouver ci-dessous la facture à échéance ces prochains jours:</p>"""
            total=0
            for invoice in invoices:
                total+=invoice.amount_residual
                body+="- Facture N°%s à l'échéance du %s pour un montant de %s € <br>"%(invoice.name, invoice.invoice_date_due.strftime('%d/%m/%Y'), self.float2str(invoice.amount_residual))
            body+="""
                <p>Total à devoir : %s €</p> 
            """%(self.float2str(total))
        #**********************************************************************

        #** Ajout de la signature *********************************************
        body+=(self.env.user.signature or '')

        #** subject ***********************************************************
        invoice_name=[]
        for invoice in invoices:
            invoice_name.append(invoice.name)
            if self.type_document=="envoi_facture":
                invoice.is_date_envoi = date.today()
            if self.type_document=="relance_facture":
                invoice.is_date_relance = date.today()
            if self.type_document=="releve_facture":
                invoice.is_date_releve = date.today()

        if self.type_document=="envoi_facture":
            subject="Facturation %s (%s)"%(partner.parent_id.name or partner.name, ", ".join(invoice_name))
        if self.type_document=="relance_facture":
            subject="Relance de factures %s (%s)"%(partner.parent_id.name or partner.name, ", ".join(invoice_name))
        if self.type_document=="releve_facture":
            subject="Relevé de factures %s (%s)"%(partner.parent_id.name or partner.name, ", ".join(invoice_name))



        #**********************************************************************
        destinataire = invoice.partner_id.is_contact_relance_facture_id or invoice.partner_id
        if destinataire.email:
            vals={
                "model"         : "account.move",
                "subject"       : subject,
                "body"          : body,
                "partner_ids"   : [destinataire.id],
                "attachment_ids": attachment_ids,
            }
            wizard = self.env['mail.compose.message'].with_context(ctx).create(vals)
            wizard.action_send_mail()
 


