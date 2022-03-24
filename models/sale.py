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

    name = fields.Char("Nom",required=True)
    logo = fields.Binary("Logo", help="Logo utilisé dans les documents (ex : AR de commande)")


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


    is_societe_commerciale_id  = fields.Many2one("is.societe.commerciale", "Société commerciale")
    is_condition_livraison     = fields.Char("Conditions de livraison")
    is_apporteur_affaire_id    = fields.Many2one("res.partner", "Apporteur d'affaire")
    is_montant_commission      = fields.Float("Montant de la commission"    , digits=(14,2))
    is_pourcentage_commission  = fields.Float("Pourcentage de la commission", digits=(14,2))
    is_montant_hors_commission = fields.Float("Montant hors commission"     , digits=(14,2), compute="_compute_montant_hors_commission", readonly=True, store=True)
    is_arc_a_faire             = fields.Boolean("ARC à faire")
    is_date_ar                 = fields.Date("Date AR")

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
            name="%s.pdf"%(obj.name)
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
            template.attachment_ids= [(6, 0, [attachment_id])]
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



class sale_order_line(models.Model):
    _name = "sale.order.line"
    _inherit = "sale.order.line"

    is_date_demandee           = fields.Date("Date demandée")
    is_date_prevue             = fields.Date("Date prévue initialement")
    is_derniere_date_prevue    = fields.Date("Dernière date prévue")
    is_fabrication_prevue      = fields.Float("Fabrication prévue"           , compute="_compute_fab", readonly=True, store=False, digits=(14,0))
    is_reste                   = fields.Float("Reste à lancer en fabrication", compute="_compute_fab", readonly=True, store=False, digits=(14,0))
    is_client_order_ref        = fields.Char("Référence Client", store=True, compute="_compute")
    is_remise1                 = fields.Integer("Remise 1 (%)")
    is_remise2                 = fields.Integer("Remise 2 (%)")
    is_production_id           = fields.Many2one("mrp.production", "Ordre de fabrication", copy=False)


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








