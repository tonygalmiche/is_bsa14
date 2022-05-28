# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import AccessError, UserError, ValidationError
import datetime


class purchase_order_line(models.Model):
    _inherit = "purchase.order.line"
    #_order = "is_sequence,id"

    is_sequence   = fields.Integer("Séquence")
    is_date_ar    = fields.Date("Date AR")
    is_masse_tole = fields.Float("Masse tôle", related="product_id.is_masse_tole", readonly=True)
    is_num_ligne  = fields.Integer("N°", help="Numéro de ligne automatique", compute="_compute_is_num_ligne", readonly=True, store=False)
    is_contrat_id = fields.Many2one('is.contrat.fournisseur', 'Contrat')
    is_qt_cde     = fields.Float("Qt cde"       , compute='_compute_qt', readonly=True)
    is_qt_contrat = fields.Float("Qt contrat"   , compute='_compute_qt', readonly=True)
    is_qt_reste   = fields.Float("Reste contrat", compute='_compute_qt', readonly=True)



    def get_qt_cde(self, partner_id, product_id, contrat_id):
        cr,uid,context,su = self.env.args
        qt_cde = 0
        if product_id and contrat_id and partner_id:
            SQL="""
                SELECT sum(pol.product_qty)
                FROM purchase_order_line pol join purchase_order po on pol.order_id=po.id
                WHERE 
                    pol.product_id=%s and 
                    pol.is_contrat_id=%s and
                    po.partner_id=%s and
                    po.state='purchase'
                limit 1
            """
            cr.execute(SQL,[product_id,contrat_id,partner_id])
            for row in cr.fetchall():
                qt_cde = row[0] or 0
        return qt_cde


    @api.depends('product_id','product_qty','is_contrat_id')
    def _compute_qt(self):
        cr,uid,context,su = self.env.args
        for obj in self:
            qt_cde = qt_contrat = 0
            partner_id = obj.order_id.partner_id.id
            product_id = obj.product_id.id
            contrat_id = obj.is_contrat_id.id
            if product_id and contrat_id and partner_id:
                qt_cde = self.get_qt_cde(partner_id, product_id, contrat_id)
                # SQL="""
                #     SELECT sum(pol.product_qty)
                #     FROM purchase_order_line pol join purchase_order po on pol.order_id=po.id
                #     WHERE 
                #         pol.product_id=%s and 
                #         pol.is_contrat_id=%s and
                #         po.partner_id=%s and
                #         po.state='purchase'
                #     limit 1
                # """
                # cr.execute(SQL,[product_id,contrat_id,partner_id])
                # for row in cr.fetchall():
                #     qt_cde = row[0]
            if obj.is_contrat_id:
                for line in obj.is_contrat_id.ligne_ids:
                    if line.product_id.id==product_id:
                        qt_contrat = line.qt_contrat
            qt_reste = qt_contrat - qt_cde
            obj.is_qt_cde     = qt_cde
            obj.is_qt_contrat = qt_contrat
            obj.is_qt_reste   = qt_reste


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


    @api.onchange('product_id')
    def onchange_is_contrat_id(self):
        cr,uid,context,su = self.env.args
        contrat_id = False
        product_id = self.product_id.id
        partner_id = self.order_id.partner_id.id
        if product_id and partner_id:
            SQL="""
                SELECT l.contrat_id
                FROM is_contrat_fournisseur_ligne l join is_contrat_fournisseur c on l.contrat_id=c.id
                WHERE 
                    l.product_id=%s and 
                    c.partner_id=%s and
                    c.date_debut<=now() and
                    c.date_fin>=now()
                limit 1
            """
            cr.execute(SQL,[product_id,partner_id])
            for row in cr.fetchall():
                contrat_id = row[0]
        self.is_contrat_id=contrat_id


class is_purchase_order_nomenclature(models.Model):
    _name        = "is.purchase.order.nomenclature"
    _description = "Import nomenclature dans commande fournisseur"

    order_id         = fields.Many2one("purchase.order", "Commande")
    product_id       = fields.Many2one("product.template", "Article vendu", help="Utilsé pour l'importation de la nomenclature")
    quantite_vendue  = fields.Integer("Qt article vendu")


class purchase_order(models.Model):
    _inherit = "purchase.order"


    def _compute_is_alerte(self):
        for obj in self:
            alerte1=alerte2=False
            seuil1 = self.env.user.company_id.is_seuil_validation_rsp_achat
            seuil2 = self.env.user.company_id.is_seuil_validation_dir_finance
            montant = obj.amount_untaxed
            if montant>=seuil1 and montant<seuil2:
                alerte1="Cette commande de %.2f € dépasse le montant limite de %.0f €.\nLa validation par le responsable des achats est nécessaire."%(obj.amount_untaxed, seuil1)
                if obj.is_montant_valide==montant:
                    alerte1=False
                else:
                    if obj.is_montant_valide>0:
                        alerte1="Le montant validé de %.2f € ne correspond plus au montant actuel de %.2f €.\nLa validation par le responsable des achats est nécessaire."%(obj.is_montant_valide, obj.amount_untaxed)
            if montant>=seuil2:
                alerte2="Cette commande de %.2f € dépasse le montant limite de %.0f €.\nLa validation par la direction financière est nécessaire."%(obj.amount_untaxed, seuil2)
                if obj.is_montant_valide==montant:
                    alerte2=False
                else:
                    if obj.is_montant_valide>0:
                        alerte2="Le montant validé de %.2f € ne correspond plus au montant actuel de %.2f €.\nLa validation par la direction financière est nécessaire."%(obj.is_montant_valide, obj.amount_untaxed)
            obj.is_alerte_rsp_achat   = alerte1
            obj.is_alerte_dir_finance = alerte2

    def _compute_is_alerte_dir_finance(self):
        for obj in self:
            alerte=''
            alerte="Montant HT x 2 : %s"%(obj.amount_untaxed*2)
            obj.is_alerte_dir_finance=alerte


    is_a_commander        = fields.Boolean("A commander", default=False)
    is_arc                = fields.Boolean("ARC reçu"   , default=False)
    is_article_vendu_id   = fields.Many2one("product.template", "Article vendu", help="Utilsé pour l'importation de la nomenclature")
    is_quantite_vendue    = fields.Integer("Qt article vendu")
    is_nomenclature_ids   = fields.One2many("is.purchase.order.nomenclature", "order_id", "Importation nomenclature")
    is_alerte_rsp_achat   = fields.Text('Alerte responsable des achats', compute=_compute_is_alerte)
    is_alerte_dir_finance = fields.Text('Alerte direction financière'  , compute=_compute_is_alerte)
    is_montant_valide     = fields.Float("Montant validé")
    is_valideur_id        = fields.Many2one('res.users', 'Valideur')


    def validation_action(self):
        for obj in self:
            obj.is_montant_valide = obj.amount_untaxed
            obj.is_valideur_id    = self.env.user.id


    def button_confirm(self):
        for order in self:
            if order.is_alerte_rsp_achat or order.is_alerte_dir_finance:
                raise ValidationError("Cette commande doit-être validée")
            #else:
            #    self.write({'state': 'approved', 'date_approve': datetime.date.today()})
        res = super(purchase_order, self).button_confirm()
        return res


    def action_create_invoice(self):
        """Permet de faire le lien entre la ligne de facture et la ligne de réception ce qui n'existe pas par défaut"""
        res = super().action_create_invoice()
        if res and "domain" in res:
            ids=[]
            domain = res["domain"][0]
            if domain[0] == "id":
                ids = domain[2]
            else:
                if "res_id" in res:
                    if res["res_id"]>0:
                        ids=[res["res_id"]]
            invoices = self.env["account.move"].search([("id","in", ids)])
            for invoice in invoices:
                for line in invoice.line_ids:
                    if line.purchase_line_id:
                        for move in line.purchase_line_id.move_ids:
                            if not move.is_account_move_line_id and move.state=="done":
                                move.is_account_move_line_id = line.id
                                line.is_stock_move_id = move.id
        return res


    def import_nomenclature_action(self):
        for obj in self:
            obj.order_line.unlink()
            lines={}
            for l in obj.is_nomenclature_ids:
                if l.product_id and l.quantite_vendue:
                    boms = self.env["mrp.bom"].search([("product_tmpl_id","=",l.product_id.id)], limit=1)
                    for bom in boms:
                        for line in bom.bom_line_ids:
                            for seller in line.product_id.seller_ids:
                                if seller.name.id == obj.partner_id.id:
                                    qty        = line.product_qty*l.quantite_vendue
                                    product_id = line.product_id
                                    if product_id not in lines:
                                        lines[product_id]=0
                                    lines[product_id]+=qty
            sequence=0
            for product_id in lines:
                sequence+=10
                uom_id = product_id.uom_po_id.id
                qty = lines[product_id]
                #res = self.env["purchase.order.line"].onchange_product_id(obj.pricelist_id.id,product_id.id,qty,uom_id,obj.partner_id.id,fiscal_position_id=obj.fiscal_position.id)
                #vals=res["value"]
                #taxes_id = vals["taxes_id"]
                vals={
                    "order_id"   : obj.id,
                    "is_sequence": sequence,
                    "product_id" : product_id.id,
                    "product_qty": qty,
                    #"taxes_id"   : [(6,0,taxes_id)],
                }
                res = self.env["purchase.order.line"].create(vals)


    def mouvement_stock_action(self):
        for obj in self:
            ids=[]
            for picking in obj.picking_ids:
                for line in picking.move_lines:
                    ids.append(line.id)
            if not ids:
                raise Warning("Aucune ligne de réception")
            else:
                return {
                    "name": "Lignes de réception "+obj.name,
                    "view_mode": "tree,form",
                    "view_type": "form",
                    "res_model": "stock.move",
                    "domain": [
                        ("id","in",ids),
                    ],
                    "type": "ir.actions.act_window",
                }









    # #TODO : J"ai surchargé cette fonction le 28/11/19, car le modèle de mail de la demande de prix a été supprimée
    # def wkf_send_rfq(self, cr, uid, ids, context=None):
    #     """
    #     This function opens a window to compose an email, with the edi purchase template message loaded by default
    #     """
    #     if not context:
    #         context= {}
    #     ir_model_data = self.pool.get("ir.model.data")
    #     try:
    #         if context.get("send_rfq", False):
    #             template_id = ir_model_data.get_object_reference(cr, uid, "is_bsa", "is_demande_de_prix_email_template")[1]
    #         else:
    #             template_id = ir_model_data.get_object_reference(cr, uid, "purchase", "email_template_edi_purchase_done")[1]
    #     except ValueError:
    #         template_id = False
    #     try:
    #         compose_form_id = ir_model_data.get_object_reference(cr, uid, "mail", "email_compose_message_wizard_form")[1]
    #     except ValueError:
    #         compose_form_id = False 
    #     ctx = dict(context)
    #     ctx.update({
    #         "default_model": "purchase.order",
    #         "default_res_id": ids[0],
    #         "default_use_template": bool(template_id),
    #         "default_template_id": template_id,
    #         "default_composition_mode": "comment",
    #     })
    #     return {
    #         "name": _("Compose Email"),
    #         "type": "ir.actions.act_window",
    #         "view_type": "form",
    #         "view_mode": "form",
    #         "res_model": "mail.compose.message",
    #         "views": [(compose_form_id, "form")],
    #         "view_id": compose_form_id,
    #         "target": "new",
    #         "context": ctx,
    #     }
