# -*- coding: utf-8 -*-
from copy import copy
from importlib.resources import path
from odoo import models,fields,api
from odoo.http import request
from odoo.exceptions import Warning, ValidationError
import datetime
import base64
import os
import logging
_logger = logging.getLogger(__name__)


class is_societe_commerciale(models.Model):
    _name = "is.societe.commerciale"
    _description = "Société commerciale"

    name    = fields.Char("Nom",required=True)
    logo    = fields.Binary("Logo", help="Logo utilisé dans les documents (ex : AR de commande)")
    made_in = fields.Binary("Logo 'Made in'", help="Logo 'Made in Jura' / 'Made in France' utilisé dans l'entête de l'affaire")
    slogan  = fields.Char("Slogan")
    report_footer = fields.Text("Pied de page de rapport")
    cgv_ids       = fields.Many2many('ir.attachment', 'is_societe_commerciale_cgv_rel', 'societe_id', 'attachment_id', 'CGV')
    arrondi       = fields.Integer("Arrondi devis paramètrable", default=10, help="Arrondi à appliquer dans les devis parametrables (Mettre 1 ou 10)")


class is_sale_order_line_group(models.Model):
    _name = "is.sale.order.line.group"
    _description = "Regroupement des lignes par article pour recalculer le prix par quantité"
    _order = "product_id"

    @api.depends("product_uom_qty","price_unit")
    def _compute_price_subtotal(self):
        for obj in self:
            obj.price_subtotal = obj.product_uom_qty * obj.price_unit

    order_id        = fields.Many2one('sale.order', 'Commande', required=True, ondelete='cascade')
    product_id      = fields.Many2one('product.product', 'Article', required=True)
    product_uom_qty = fields.Float("Quantité", digits='Product Unit of Measure', required=False)
    price_unit      = fields.Float("Prix unitaire", digits='Product Price', required=False)
    currency_id     = fields.Many2one(related='order_id.currency_id')
    price_subtotal  = fields.Monetary(compute='_compute_price_subtotal', string='Montant', readonly=True, store=True)


class sale_order(models.Model):
    _inherit = "sale.order"


    def creation_of(self):
        for obj in self:
            for line in obj.order_line:
                if line.product_id.is_creation_of:
                    line.creation_of_multi_niveaux(line,0, 1, line.product_id)


    def action_confirm(self):
        res = super(sale_order, self).action_confirm()
        for obj in self:
            name = obj.name + " " + obj.partner_id.name
            vals={
                "name": name,
            }
            try:
                self.env["project.task"].sudo().create(vals)
            except KeyError:
                continue
        self.creation_of()
        return res


    @api.depends("amount_untaxed","is_montant_commission", "is_pourcentage_commission")
    def _compute_montant_hors_commission(self):
        for obj in self:
            obj.is_montant_hors_commission=obj.amount_untaxed-(obj.amount_untaxed*obj.is_pourcentage_commission/100 + obj.is_montant_commission)


    @api.depends("state","order_line")
    def _compute_is_total_facture(self):
        for obj in self:
            is_deja_facture = 0
            for invoice in obj.invoice_ids:
                is_deja_facture+=invoice.amount_untaxed_signed
            obj.is_total_facture = is_deja_facture
            obj.is_reste_a_facturer = obj.amount_untaxed - is_deja_facture


    @api.depends('order_line', 'order_line.is_facturable_pourcent')
    def _compute_facturable(self):
        for obj in self:
            is_a_facturer=0
            is_deja_facture=0
            for line in obj.order_line:
                is_a_facturer+=line.is_a_facturer
                is_deja_facture+=line.is_deja_facture
            obj.is_a_facturer=is_a_facturer
            obj.is_deja_facture=is_deja_facture


    @api.depends('order_line', 'order_line.is_date_prevue')
    def _compute_is_date_prevue(self):
        for obj in self:
            date_prevue = False
            for line in obj.order_line:
                if line.is_date_prevue:
                    if not date_prevue:
                        date_prevue=line.is_date_prevue
                    if line.is_date_prevue<date_prevue:
                        date_prevue=line.is_date_prevue
            obj.is_date_prevue = date_prevue


    # renommage de la description
    #date_order                 = fields.Datetime("Date AR")
    is_societe_commerciale_id  = fields.Many2one("is.societe.commerciale", "Société commerciale")
    is_condition_livraison     = fields.Char("Conditions de livraison")
    is_apporteur_affaire_id    = fields.Many2one("res.partner", "Apporteur d'affaire")
    is_montant_commission      = fields.Float("Montant de la commission"    , digits=(14,2))
    is_pourcentage_commission  = fields.Float("Pourcentage de la commission", digits=(14,2))
    is_montant_hors_commission = fields.Float("Montant hors commission"     , digits=(14,2), compute="_compute_montant_hors_commission", readonly=True, store=True)
    is_arc_a_faire             = fields.Boolean("ARC à faire")
    is_date_ar                 = fields.Date("Date AR (champs desactivé))")
    is_notre_ref_devis         = fields.Char("Notre référence de devis")
    is_nom_affaire             = fields.Char("Nom de l'affaire")
    is_group_line_ids          = fields.One2many('is.sale.order.line.group', 'order_id', 'Lignes par article', copy=False, readonly=True)
    is_group_line_print        = fields.Boolean("Imprimer le regroupement par article", default=False)
    is_date_commande_client    = fields.Date("Date cde client")
    is_total_facture           = fields.Float("Total facturé"   , digits=(14,2), store=True, readonly=True, compute='_compute_is_total_facture')
    is_reste_a_facturer        = fields.Float("Reste à facturer", digits=(14,2), store=True, readonly=True, compute='_compute_is_total_facture')
    is_a_facturer              = fields.Float("Lignes à facturer"    , digits=(14,2), store=False, readonly=True, compute='_compute_facturable')
    is_deja_facture            = fields.Float("Lignes déjà facturées", digits=(14,2), store=False, readonly=True, compute='_compute_facturable')
    is_date_prevue             = fields.Date("Date prévue", store=True, readonly=True, compute='_compute_is_date_prevue', help="Date prévue initialement des lignes de la commande la plus proche")
    is_situation               = fields.Char("Situation")
    is_type_facturation        = fields.Selection([
            ('standard'      , 'Standard'),
            ('avec_situation', 'Avec situation'),
        ], "Type de facturation", default="standard")


    @api.depends('order_line.invoice_lines')
    def _get_invoiced(self):
        # The invoice_ids are obtained thanks to the invoice lines of the SO
        # lines, and we also search for possible refunds created directly from
        # existing invoices. This is necessary since such a refund is not
        # directly linked to the SO.
        for order in self:
            invoices1 = order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            filtre=[
                ('state', 'in' , ['draft','posted']),
                ('is_sale_order_id', '=' , order.id)
            ]
            invoices2 = self.env['account.move'].search(filtre)
            invoices = invoices1+invoices2
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)


    def maj_prix_par_quantite_action(self):
        for obj in self:
            lines={}
            for line in obj.order_line:
                if line.product_id not in lines:
                    lines[line.product_id]=0
                lines[line.product_id]+=line.product_uom_qty
            obj.is_group_line_ids.unlink()
            for product in lines:
                qty = lines[product]
                product_context = dict(
                    self.env.context, 
                    partner_id=obj.partner_id.id, 
                    date=obj.date_order, 
                    uom=product.uom_id.id)
                price, rule_id = obj.pricelist_id.with_context(product_context).get_product_price_rule(product, qty or 1.0, obj.partner_id)
                vals={
                    "order_id"       : obj.id,
                    "product_id"     : product.id,
                    "product_uom_qty": qty,
                    "price_unit"     : price,
                }
                self.env['is.sale.order.line.group'].create(vals)
                for line in obj.order_line:
                    if line.product_id==product:
                        line.price_unit = price


    def mouvement_stock_action(self):
        for obj in self:
            ids=[]
            for picking in obj.picking_ids:
                for line in picking.move_lines:
                    ids.append(line.id)
            if not ids:
                raise Warning("Aucune ligne de livraison")
            else:
                return {
                    "name": "Lignes de livraison "+obj.name,
                    "view_mode": "tree,form",
                    "view_type": "form",
                    "res_model": "stock.move",
                    "domain": [
                        ("id","in",ids),
                    ],
                    "type": "ir.actions.act_window",
                }


    def _create_invoices(self, grouped=False, final=False, date=None):
        invoices = super()._create_invoices(grouped=grouped, final=final, date=date)
        for invoice in invoices:
            for line in invoice.line_ids:
                for sale_line in line.sale_line_ids:
                    line.is_sale_line_id = sale_line.id
                    for move in sale_line.move_ids:
                        if not move.is_account_move_line_id and move.state=="done":
                            move.is_account_move_line_id = line.id
                            line.is_stock_move_id = move.id
        return invoices


    def mail_avec_cgv_action(self):
        for obj in self:
            paths=[]
            attachment_obj = self.env['ir.attachment']

            #** Bon de commande ***********************************************
            pdf = request.env.ref('sale.action_report_saleorder').sudo()._render_qweb_pdf([obj.id])[0]
            path="/tmp/sale_order_%s_01.pdf"%(obj.name)
            paths.append(path)
            f = open(path,'wb')
            f.write(pdf)
            f.close()
            #******************************************************************

            #** CGV ***********************************************************
            company = self.env.user.company_id
            for attachment in company.is_cgv_ids:
                pdf=base64.b64decode(attachment.datas)
                path="/tmp/sale_order_%s_02_cgv.pdf"%(obj.name)
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                paths.append(path)
            #******************************************************************

            # ** Merge des PDF *************************************************
            path_merged = "/tmp/sale_order_%s_merged.pdf"%(obj.name)
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
            #name="%s.pdf"%(obj.name)
            name="BSA AR Commande %s.pdf"%(obj.name)
            model=self._name
            attachments = attachment_obj.search([('res_model','=',model),('res_id','=',obj.id),('name','=',name)])
            vals={
                'name'       : name,
                'type'       : 'binary', 
                'res_id'     : obj.id,
                'res_model'  : 'sale.order',
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
            # ******************************************************************


            #** Ajout de la piece jointe marged au modèle de mail **************
            template_id = self._find_mail_template()
            template = self.env['mail.template'].browse(template_id)
            #template.attachment_ids= [(6, 0, [attachment_id])]
            # ******************************************************************


            #** wizard pour envoyer le mail ****************************************
            lang = self.env.context.get('lang')
            if template.lang:
                lang = template._render_lang(self.ids)[self.id]
            ctx = {
                'default_model': 'sale.order',
                'default_res_id': self.ids[0],
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'default_attachment_ids': [(6, 0, [attachment_id])],
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'proforma': self.env.context.get('proforma', False),
                'force_email': True,
                'model_description': self.with_context(lang=lang).type_name,
            }
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(False, 'form')],
                'view_id': False,
                'target': 'new',
                'context': ctx,
            }
            #**********************************************************************


    def act_livraison(self,etiquettes):
        err=""
        for obj in self:
            filtre=[
                ('state'       , 'in' , ['assigned','waiting','confirmed']),
                ('sale_id'        , '=' , obj.id)
            ]
            pickings = self.env['stock.picking'].search(filtre, limit=1)
            for picking in pickings:
                picking.move_line_ids_without_package.unlink()
                lines = self.env['is.tracabilite.livraison'].search([('id', 'in', etiquettes)])
                for line in lines:
                    move_id=False
                    mem=False
                    for move in picking.move_ids_without_package:
                        if move.product_id.product_tmpl_id==line.product_id:
                            date_prevue = move.sale_line_id.is_derniere_date_prevue
                            if not mem:
                                mem=date_prevue
                            if date_prevue<=mem:
                                mem=date_prevue
                                move_id = move.id
                    product = line.product_id
                    vals={
                        "move_id"           : move_id,
                        "picking_id"        : picking.id,
                        "product_id"        : line.product_id.product_variant_id.id,
                        "company_id"        : picking.company_id.id,
                        "product_uom_id"    : line.product_id.uom_id.id,
                        "location_id"       : picking.location_id.id,
                        "location_dest_id"  : picking.location_dest_id.id,
                        "qty_done"          : 1,
                    }
                    res = self.env['stock.move.line'].create(vals)
                    line.sale_id   = obj.id
                    line.move_id   = res.move_id.id
                picking.write({'etiquette_livraison_ids': [(6, 0, etiquettes)]})
                picking.with_context(skip_backorder=True).button_validate()
                for line in lines:
                    line.livraison = line.move_id.date
                #self.env['stock.picking'].browse(picking.id).with_context(skip_backorder=True).button_validate()
                #picking.button_validate()


                # Impression automatique du BL en PDF *****************************
                user    = self.env['res.users'].browse(self._uid)
                imprimante = user.company_id.is_imprimante_bl
                if imprimante:

                    #** Enregistrement du PDF du BL *******************************
                    pdf = request.env.ref('stock.action_report_delivery').sudo().with_context(tz=user.tz)._render_qweb_pdf([picking.id])[0]
                    path="/tmp/%s.pdf"%(picking.name)
                    f = open(path,'wb')
                    f.write(pdf)
                    f.close()
                    #**************************************************************


                    # Impression en recto-verso
                    cmd="lp -o sides=two-sided-long-edge -d "+imprimante+" "+path
                    os.system(cmd)

                    # Impression premiere page uniquement
                    cmd="lp -P 1 -d "+imprimante+" "+path
                    os.system(cmd)
                #******************************************************************


        return {"err":err,"data":""}



    def save_bl_pdf(self, picking_id):
        for obj in self:

            # Impression automatique du BL en PDF *****************************
            user  = self.env['res.users'].browse(self._uid)

            user_tz = user.tz 


            imprimante = user.company_id.is_imprimante_bl
            if imprimante:
                #** Enregistrement du PDF du BL *******************************
                pdf = request.env.ref('stock.action_report_delivery').sudo().with_context(tz=user_tz)._render_qweb_pdf([picking_id])[0]
                path="/tmp/%s.pdf"%(picking_id)
                f = open(path,'wb')
                f.write(pdf)
                f.close()
                #**************************************************************
        return {"err":"","data":""}


    def actualiser_facturable_action(self):
        for obj in self:
            obj.order_line.actualiser_facturable_action()


    def generer_facture_action(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            if obj.is_a_facturer==0:
                raise ValidationError("Il n'y a rien à facturer")

            move_type = 'out_invoice'
            sens = 1
            if obj.is_a_facturer<0:
                move_type = 'out_refund'
                sens=-1


            #** Création des lignes *******************************************
            total_cumul_ht=0
            invoice_line_ids=[]
            sequence=0
            is_a_facturer = 0
            for line in obj.order_line:
                if line.display_type in ["line_section", "line_note"]:
                    vals={
                        'sequence'    : line.sequence,
                        'display_type': line.display_type ,
                        'name'        : line.name,
                    }
                else:
                    quantity=line.product_uom_qty*(line.is_facturable_pourcent-line.is_facture_avant_pourcent-line.is_deja_facture_pourcent)/100
                    taxes = line.product_id.taxes_id
                    taxes = obj.fiscal_position_id.map_tax(taxes)
                    tax_ids=[]
                    for tax in taxes:
                        tax_ids.append(tax.id)
                    vals={
                        'sequence'  : line.sequence,
                        'product_id': line.product_id.id,
                        'name'      : line.name,
                        'quantity'  : sens*quantity,
                        'is_facturable_pourcent': sens*line.is_facturable_pourcent,
                        'price_unit'            : line.price_unit,
                        'is_sale_line_id'       : line.id,
                        'tax_ids'               : tax_ids,
                        "is_a_facturer"         : line.is_a_facturer,
                    }
                    total_cumul_ht+=sens*quantity*line.price_unit
                    is_a_facturer+=line.is_a_facturer
                invoice_line_ids.append(vals)
                sequence=line.sequence
                
            #** Création entête facture ***************************************
            vals={
                'is_situation'       : obj.is_situation,
                'partner_id'         : obj.partner_id.id,
                'is_sale_order_id'   : obj.id,
                'move_type'          : move_type,
                'invoice_line_ids'   : invoice_line_ids,
            }
            move=self.env['account.move'].create(vals)
            move._onchange_partner_id()
            move._onchange_invoice_date()
            #move.action_post()


class sale_order_line(models.Model):
    _name = "sale.order.line"
    _inherit = "sale.order.line"

    is_date_demandee           = fields.Date("Date demandée")
    is_date_prevue             = fields.Date("Date prévue initialement")
    is_derniere_date_prevue    = fields.Date("Dernière date prévue")
    is_fabrication_prevue      = fields.Float("Fabrication prévue"           , compute="_compute_fab", readonly=True, store=False, digits=(14,0))
    is_reste                   = fields.Float("Reste à lancer en fabrication", compute="_compute_fab", readonly=True, store=False, digits=(14,0))
    is_client_order_ref        = fields.Char("Référence Client", store=True, compute="_compute")
    is_remise1                 = fields.Float("Remise 1 (%)", digits='Discount')
    is_remise2                 = fields.Float("Remise 2 (%)", digits='Discount')
    is_production_id           = fields.Many2one("mrp.production", "Ordre de fabrication", copy=False)
    is_num_ligne               = fields.Integer("N°", help="Numéro de ligne automatique", compute="_compute_is_num_ligne", readonly=True, store=False)

    is_facturable_pourcent     = fields.Float("% facturable"                                                                        , digits=(14,2), copy=False, help="% facturable à ce jour permettant de générer une nouvelle facture" )
    is_facture_avant_pourcent  = fields.Float("% facturé avant"                                                                     , digits=(14,2), copy=False, help="% factturé hors situation (ex : Accompte) pour reprendre l'historique")
    is_deja_facture_pourcent   = fields.Float("% déjà facturé"  , store=True, readonly=True, compute='actualiser_facturable_action' , digits=(14,2), copy=False, help="%s déja facturé calculé à partir des factures")
    is_facturable              = fields.Float("Facturable"      , store=True, readonly=True, compute='actualiser_facturable_action' , digits=(14,2), copy=False)
    is_deja_facture            = fields.Float("Déja facturé"    , store=True, readonly=True, compute='actualiser_facturable_action' , digits=(14,2), copy=False)
    is_a_facturer              = fields.Float("A Facturer"      , store=True, readonly=True, compute='actualiser_facturable_action' , digits=(14,2), copy=False)
    is_reste_a_facturer        = fields.Float("Reste à facturer", store=True, readonly=True, compute='_compute_is_reste_a_facturer', digits=(14,2), copy=False)
    is_voir_production_vsb     = fields.Boolean("Voir les productions vsb", compute='_compute_is_voir_production_vsb')


    @api.depends('product_uom_qty','qty_invoiced','price_unit','price_subtotal')
    def _compute_is_reste_a_facturer(self):
        for obj in self:
            reste=0
            if obj.product_uom_qty>0:
                price_avec_reduc = obj.price_subtotal/obj.product_uom_qty
                reste = price_avec_reduc*(obj.product_uom_qty - obj.qty_invoiced)
            obj.is_reste_a_facturer = reste


    @api.depends('is_facture_avant_pourcent','is_facturable_pourcent','price_unit','product_uom_qty')
    def actualiser_facturable_action(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            deja_facture_pourcent = 0 # 100*obj.qty_invoiced
            if not isinstance(obj.id, models.NewId):
                #** Liens directe entre ligne de commande et ligne de facture *********************
                SQL="""
                    SELECT am.move_type,aml.quantity,am.name
                    FROM account_move_line aml join account_move    am on aml.move_id=am.id
                    WHERE aml.is_sale_line_id=%s and am.state!='cancel'
                """
                cr.execute(SQL,[obj.id])
                for row in cr.fetchall():
                    sens=1
                    if row[0]=='out_refund':
                        sens=-1
                    deja_facture_pourcent += 100*sens*(row[1] or 0)
                #**********************************************************************************

                # #** Liens entre ligne de commande, ligne de facture et mouvement de stock *********
                # SQL="""
                #     SELECT am.move_type,sum(aml.quantity)
                #     FROM account_move_line aml join account_move am on aml.move_id=am.id
                #                                join stock_move   sm on aml.is_stock_move_id=sm.id
                #     WHERE sm.sale_line_id=%s and am.state!='cancel'
                #     GROUP BY am.move_type
                # """
                # cr.execute(SQL,[obj.id])
                # for row in cr.fetchall():
                #     sens=1
                #     if row[0]=='out_refund':
                #         sens=-1
                #     deja_facture_pourcent += 100*sens*(row[1] or 0)
                # #**********************************************************************************

            pourcentage_facture = (deja_facture_pourcent+obj.is_facture_avant_pourcent)/100
            if pourcentage_facture>0:
                obj.qty_invoiced = pourcentage_facture

            is_deja_facture=(deja_facture_pourcent+obj.is_facture_avant_pourcent)*obj.price_subtotal/100
            obj.is_deja_facture_pourcent = deja_facture_pourcent
            is_facturable = obj.price_subtotal*obj.is_facturable_pourcent/100 
            is_a_facturer = is_facturable - is_deja_facture
            obj.is_facturable   = is_facturable
            obj.is_deja_facture = is_deja_facture
            obj.is_a_facturer   = is_a_facturer
            obj._compute_is_reste_a_facturer()


    @api.depends("order_id","order_id.order_line")
    def _compute_is_num_ligne(self):
        for obj in self:
            lig = 1
            for line in obj.order_id.order_line:
                if not line.display_type:
                    num = lig
                    lig+=1
                else:
                    num=False
                line.is_num_ligne = num


    @api.depends("order_id","order_id.client_order_ref")
    def _compute(self):
        for obj in self:
            if obj.order_id:
                obj.is_client_order_ref = obj.order_id.client_order_ref


    def _compute_fab(self):
        cr = self._cr
        for obj in self:
            sql="""
                select sum(product_qty)
                from mrp_production
                where is_sale_order_line_id="""+str(obj.id)+"""
            """
            cr.execute(sql)
            fabrication_prevue=0
            for row in cr.fetchall():
                fabrication_prevue=row[0] or 0
            obj.is_fabrication_prevue=fabrication_prevue
            obj.is_reste=obj.product_uom_qty-fabrication_prevue


    @api.onchange('is_remise1','is_remise2')
    def onchange_remise(self):
        remise=100-self.is_remise1
        remise=remise-remise*self.is_remise2/100.0
        remise=100-remise
        self.discount=remise



    def creer_of(self,product_id,quantite):
        for obj in self:
            production=False
            #** Recherche si un OF existe déja pour cette ligne de commande****
            mrp_production_obj = self.env["mrp.production"]
            filtre=[
                ('is_sale_order_line_id', '=', obj.id),
                ('product_id'           ,'=',product_id.id)
            ]
            productions = mrp_production_obj.search(filtre)
            if len(productions)>0:
                production=productions[0]
            #******************************************************************
            if not production:
                vals={
                    "product_id"           : product_id.id,
                    "product_uom_id"       : product_id.uom_id.id,
                    "product_qty"          : quantite,
                    "origin"               : obj.order_id.name,
                    "is_sale_order_line_id": obj.id,
                    "date_planned_start"   : obj.is_date_prevue,
                }
                production=mrp_production_obj.create(vals)
                if production:
                    production.onchange_product_id()
                    production.product_qty = quantite
                    production._onchange_bom_id()
                    production._onchange_move_raw()
                    production.action_confirm()
                    msg="Création OF %s pour la commande %s et l'article %s"%(production.name,obj.order_id.name,product_id.name)
                    _logger.info(msg)



    def creation_of_multi_niveaux(self, sale_order_line, niveau, quantite, product_id, bom_id=False):
        for obj in self:
            if bom_id:
                boms = self.env['mrp.bom'].search([('id','=',bom_id.id)],limit=1)
            else:
                boms = self.env['mrp.bom'].search([('product_tmpl_id','=',product_id.product_tmpl_id.id)],limit=1)
            for bom in boms:
                if bom.product_tmpl_id.is_creation_of:
                    sale_order_line.creer_of(product_id,quantite)
                for line in bom.bom_line_ids:
                    coef = line.product_uom_id._compute_quantity(1,line.product_id.uom_id )
                    boms2 = self.env['mrp.bom'].search([('product_tmpl_id','=',line.product_id.product_tmpl_id.id)],limit=1)
                    type_article="composant"
                    if boms2:
                        type_article="compose"
                    product_qty = line.product_qty*quantite
                    obj.creation_of_multi_niveaux(sale_order_line,niveau+1, product_qty, line.product_id)


    def creer_of_action(self):
        for obj in self:
            if obj.product_id.is_creation_of:
                obj.creation_of_multi_niveaux(obj,0, obj.product_uom_qty, obj.product_id)


    def voir_productions_action(self):
        for obj in self:
            productions = self.env['mrp.production'].search([('is_sale_order_line_id','=',obj.id)])
            ids=[]
            for production in productions:
                ids.append(production.id)
            if len(ids)>0:
                return {
                    "name": 'Productions',
                    "view_mode": "tree,form",
                    "res_model": "mrp.production",
                    "domain": [
                        ("id" ,"in",ids),
                    ],
                    "type": "ir.actions.act_window",
                }


    def _compute_is_voir_production_vsb(self):
        for obj in self:
            vsb=False
            productions = self.env['mrp.production'].search([('is_sale_order_line_id','=',obj.id)])
            if len(productions)>0:
                vsb=True
            obj.is_voir_production_vsb = vsb
