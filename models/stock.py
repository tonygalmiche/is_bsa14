# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_affecter_etiquette_livraison(models.Model):
    _name = "is.affecter.etiquette.livraison"
    _description = "is_affecter_etiquette_livraison"

    operateur_livraison_id = fields.Many2one("hr.employee", "Opérateur de la livraison", required=True)
    move_id                = fields.Many2one("stock.move", "Ligne de la livraison"   , required=True)
    product_id             = fields.Many2one("product.template", "Article", related="move_id.product_id.product_tmpl_id", readonly=True)
    etiquette_ids          = fields.Many2many("is.tracabilite.livraison", "is_affecter_etiquette_livraison_rel", "affecter_id", "etiquette_id")

    def ok_action(self):
        context=self._context
        ids=[]
        for obj in self:
            if "picking_id" in context:
                picking_id=context["picking_id"]
                picking = self.env["stock.picking"].browse(picking_id)
                if picking:
                    for etiquette in obj.etiquette_ids:
                        vals={
                            "sale_id": picking.document_id.id,
                            "move_id": obj.move_id.id,
                            "picking_id": picking.id,
                            "quantity": 1,
                            "livraison": picking.date_done,
                            "operateur_livraison_ids": [(6,0,[obj.operateur_livraison_id.id])]
                        }
                        etiquette.write(vals)
                        ids.append(etiquette.id)
            return {
                "name": "Etiquettes de livraison",
                "type": "ir.actions.act_window",
                "view_type": "form",
                "view_mode": "tree,form",
                "res_model": "is.tracabilite.livraison",
                "domain": [("id","in",ids)],
            }


class stock_move(models.Model):
    _inherit = "stock.move"


    is_date_ar              = fields.Date(related="purchase_line_id.is_date_ar"  , string="Date AR")
    is_date_planned         = fields.Datetime(related="purchase_line_id.date_planned", string="Date prévue")
    is_account_move_line_id = fields.Many2one("account.move.line", "Ligne de facture" )
    is_description          = fields.Text(related="sale_line_id.name", string="Description vente")

    is_pru_matiere       = fields.Float("PRU Matière"      , readonly=True, copy=False, digits=(14,4))
    is_pru_mo            = fields.Float("PRU MO"           , readonly=True, copy=False, digits=(14,4))
    is_pru_matiere_total = fields.Float("PRU Matière Total", readonly=True, copy=False, digits=(14,4))
    is_pru_mo_total      = fields.Float("PRU MO Total"     , readonly=True, copy=False, digits=(14,4))
    is_pru_total         = fields.Float("PRU Total"        , readonly=True, copy=False, digits=(14,4))
    is_pru_production_id = fields.Many2one("mrp.production", "OF PRU" )


    def _create_invoice_line_from_vals(self, cr, uid, move, invoice_line_vals, context=None):
        invoice_line_vals["is_stock_move_id"]=move.id
        res = super(stock_move, self)._create_invoice_line_from_vals(cr, uid, move, invoice_line_vals, context)
        return res

    def etiquette_livraison_action(self):
        for obj in self:
            context={
                "default_move_id": obj.id,
                "picking_id":obj.picking_id.id,
            }
            return {
                "type": "ir.actions.act_window",
                "view_type": "form",
                "view_mode": "form",
                "res_model": "is.affecter.etiquette.livraison",
                "target": "new",
                "context": context,
            }

    def fiche_article_action(self):
        for obj in self:
            return {
                "name": "Article",
                "view_mode": "form",
                "view_type": "form",
                "res_model": "product.template",
                "type": "ir.actions.act_window",
                "res_id": obj.product_id.product_tmpl_id.id,
                "domain": "[]",
            }


    def annuler_mouvement_action(self):
        for obj in self:
            obj._action_cancel()
 

    @api.depends('state', 'picking_id', 'product_id')
    def _compute_is_quantity_done_editable(self):
        for move in self:
            move.is_quantity_done_editable = True


class stock_quant(models.Model):
    _inherit = "stock.quant"
     
    product_stock_category_id = fields.Many2one(related="product_id.is_stock_category_id", string="Catégorie de stock")



