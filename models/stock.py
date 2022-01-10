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

    is_date_ar      = fields.Date(related="purchase_line_id.is_date_ar"  , string="Date AR")
    is_date_planned = fields.Datetime(related="purchase_line_id.date_planned", string="Date prévue")

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


class stock_quant(models.Model):
    _inherit = "stock.quant"
     
    product_stock_category_id = fields.Many2one(related="product_id.is_stock_category_id", string="Catégorie de stock")


class stock_inventory(models.Model):
    _inherit = "stock.inventory"
    _order="date desc"
     
    product_stock_category_id = fields.Many2one("is.stock.category", string="Catégorie de stock")
    is_date_forcee            = fields.Datetime("Date forcée pour l'inventaire")

    def action_force_date_inventaire(self):
        cr = self._cr
        for obj in self:
            if obj.is_date_forcee:
                SQL="""
                    UPDATE stock_move set date='"""+str(obj.is_date_forcee)+"""'
                    WHERE inventory_id="""+str(obj.id)+"""
                """
                res=cr.execute(SQL)

    def _get_inventory_lines(self, cr, uid, inventory, context=None):
        location_obj = self.pool.get("stock.location")
        product_obj = self.pool.get("product.product")
        location_ids = location_obj.search(cr, uid, [("id", "child_of", [inventory.location_id.id])], context=context)
        domain = " location_id in %s"
        args = (tuple(location_ids),)
        if inventory.partner_id:
            domain += " and owner_id = %s"
            args += (inventory.partner_id.id,)
        if inventory.lot_id:
            domain += " and lot_id = %s"
            args += (inventory.lot_id.id,)
        if inventory.product_id:
            domain += " and product_id = %s"
            args += (inventory.product_id.id,)
        if inventory.package_id:
            domain += " and package_id = %s"
            args += (inventory.package_id.id,)
        
        cr.execute("""
           SELECT product_id, sum(qty) as product_qty, location_id, lot_id as prod_lot_id, package_id, owner_id as partner_id
           FROM stock_quant WHERE""" + domain + """
           GROUP BY product_id, location_id, lot_id, package_id, partner_id
        """, args)
        vals = []
        for product_line in cr.dictfetchall():
            for key, value in product_line.items():
                if not value:
                    product_line[key] = False
            product_line["inventory_id"] = inventory.id
            product_line["theoretical_qty"] = product_line["product_qty"]
            if product_line["product_id"]:
                product = product_obj.browse(cr, uid, product_line["product_id"], context=context)
                product_line["product_uom_id"] = product.uom_id.id
            if inventory.product_stock_category_id:
                if product_obj.search(cr, uid, [("id", "=", product_line["product_id"]),("is_stock_category_id","=",inventory.product_stock_category_id.id)], count=True):
                    vals.append(product_line)
            else:
                vals.append(product_line)
        return vals
