# -*- coding: utf-8 -*-
from copy import copy
from importlib.resources import path
from odoo import models,fields,api
from odoo.http import request
from odoo.exceptions import Warning
import datetime
import base64
import os
import logging
_logger = logging.getLogger(__name__)


class is_societe_commerciale(models.Model):
    _name = "is.societe.commerciale"
    _description = "Société commerciale"

    name   = fields.Char("Nom",required=True)
    logo   = fields.Binary("Logo", help="Logo utilisé dans les documents (ex : AR de commande)")
    slogan = fields.Char("Slogan")
    report_footer = fields.Text("Pied de page de rapport")
    cgv_ids       = fields.Many2many('ir.attachment', 'is_societe_commerciale_cgv_rel', 'societe_id', 'attachment_id', 'CGV')


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
                print("## project.task KeyError ##")
                continue
        return res


    @api.depends("amount_untaxed","is_montant_commission", "is_pourcentage_commission")
    def _compute_montant_hors_commission(self):
        for obj in self:
            obj.is_montant_hors_commission=obj.amount_untaxed-(obj.amount_untaxed*obj.is_pourcentage_commission/100 + obj.is_montant_commission)


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
    is_date_commande_client    = fields.Date("Date commande client")


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


    def action_creer_of(self):
        for obj in self:
            mrp_production_obj = self.env["mrp.production"]
            qty = obj.is_reste
            vals={
                "product_id"           : obj.product_id.id,
                "product_uom_id"       : obj.product_id.uom_id.id,
                "product_qty"          : qty,
                #"bom_id"               : bom_id,
                #"routing_id"           : routing_id,
                "origin"               : obj.order_id.name,
                #"is_date_planifiee"    : datetime.date.today().strftime("%Y-%m-%d"),
                "is_sale_order_line_id": obj.id
            }
            production=mrp_production_obj.create(vals)
            if production:
                production.onchange_product_id()
                production.product_qty = qty
                production._onchange_bom_id()
                production._onchange_move_raw()
                production.action_confirm()
                return {
                    "name": "Ordre de fabrication",
                    "view_mode": "form",
                    "view_type": "form",
                    "res_model": "mrp.production",
                    "type": "ir.actions.act_window",
                    "res_id": production.id,
                    "domain": "[]",
                }



            # mrp_production_obj = self.env["mrp.production"]
            # bom_obj = self.env["mrp.bom"]
            # bom_id = bom_obj._bom_find(product_id=obj.product_id.id, properties=[])
            # routing_id = False
            # if bom_id:
            #     bom_point = bom_obj.browse(bom_id)
            #     routing_id = bom_point.routing_id.id or False
            # mrp_id = mrp_production_obj.create({
            #     "product_id"           : obj.product_id.id,
            #     "product_uom"          : obj.product_id.uom_id.id,
            #     "product_qty"          : obj.is_reste,
            #     "bom_id"               : bom_id,
            #     "routing_id"           : routing_id,
            #     "origin"               : obj.order_id.name,
            #     "is_date_planifiee"    : datetime.date.today().strftime("%Y-%m-%d"),
            #     "is_sale_order_line_id": obj.id
            # })
            # try:
            #     workflow.trg_validate(self._uid, "mrp.production", mrp_id.id, "button_confirm", self._cr)
            # except Exception as inst:
            #     msg="Impossible de convertir la "+obj.name+"\n("+str(inst)+")"
            #     raise Warning(msg)
            # if mrp_id:
            #     return {
            #         "name": "Ordre de fabrication",
            #         "view_mode": "form",
            #         "view_type": "form",
            #         "res_model": "mrp.production",
            #         "type": "ir.actions.act_window",
            #         "res_id": mrp_id.id,
            #         "domain": "[]",
            #     }


    # def name_get(self, cr, uid, ids, context=None):
    #     res = []
    #     for obj in self.browse(cr, uid, ids, context=context):
    #         name=obj.order_id.name+" "+obj.name
    #         if obj.is_date_prevue:
    #             name=name+" "+str(obj.is_date_prevue)
    #         res.append((obj.id,name))
    #     return res


    # def name_search(self, cr, user, name="", args=None, operator="ilike", context=None, limit=100):
    #     if not args:
    #         args = []
    #     if name:
    #         ids = self.search(cr, user, ["|",("name","ilike", name),("order_id.name","ilike", name)], limit=limit, context=context)
    #     else:
    #         ids = self.search(cr, user, args, limit=limit, context=context)
    #     result = self.name_get(cr, user, ids, context=context)
    #     return result








