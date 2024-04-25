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
                SQL="UPDATE stock_move set date=%s WHERE inventory_id=%s"
                res=cr.execute(SQL,[obj.is_date_forcee, obj.id])
                SQL="UPDATE  stock_move_line set date=%s where move_id in (select id from stock_move where inventory_id=%s)"
                res=cr.execute(SQL,[obj.is_date_forcee, obj.id])


    def _get_quantities(self):
        """Return quantities group by product_id, location_id, lot_id, package_id and owner_id

        :return: a dict with keys as tuple of group by and quantity as value
        :rtype: dict
        """
        self.ensure_one()
        if self.location_ids:
            domain_loc = [('id', 'child_of', self.location_ids.ids)]
        else:
            domain_loc = [('company_id', '=', self.company_id.id), ('usage', 'in', ['internal', 'transit'])]
        locations_ids = [l['id'] for l in self.env['stock.location'].search_read(domain_loc, ['id'])]

        domain = [('company_id', '=', self.company_id.id),
                  ('quantity', '!=', '0'),
                  ('location_id', 'in', locations_ids)]
        if self.prefill_counted_quantity == 'zero':
            domain.append(('product_id.active', '=', True))

        if self.product_ids:
            domain = expression.AND([domain, [('product_id', 'in', self.product_ids.ids)]])

        if self.product_stock_category_id:
            domain.append(('product_id.is_stock_category_id', '=', self.product_stock_category_id.id))

        fields = ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id', 'quantity:sum']
        group_by = ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id']

        quants = self.env['stock.quant'].read_group(domain, fields, group_by, lazy=False)
        return {(
            quant['product_id'] and quant['product_id'][0] or False,
            quant['location_id'] and quant['location_id'][0] or False,
            quant['lot_id'] and quant['lot_id'][0] or False,
            quant['package_id'] and quant['package_id'][0] or False,
            quant['owner_id'] and quant['owner_id'][0] or False):
            quant['quantity'] for quant in quants
        }


    def _get_exhausted_inventory_lines_vals(self, non_exhausted_set):
        """Return the values of the inventory lines to create if the user
        wants to include exhausted products. Exhausted products are products
        without quantities or quantity equal to 0.

        :param non_exhausted_set: set of tuple (product_id, location_id) of non exhausted product-location
        :return: a list containing the `stock.inventory.line` values to create
        :rtype: list
        """
        self.ensure_one()
        if self.product_ids:
            product_ids = self.product_ids.ids
        else:
            product_ids = self.env['product.product'].search_read([
                '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False),
                ('type', '=', 'product'),
                ('active', '=', True)], ['id'])
            product_ids = [p['id'] for p in product_ids]


        if self.product_stock_category_id:
            templates=self.env['product.template'].search([("is_stock_category_id","=", self.product_stock_category_id.id)])
            product_ids=[]
            for template in templates:
                for product in template.product_variant_ids:
                    product_ids.append(product.id)


        if self.location_ids:
            location_ids = self.location_ids.ids
        else:
            location_ids = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)]).lot_stock_id.ids

        vals = []
        for product_id in product_ids:
            for location_id in location_ids:
                if ((product_id, location_id) not in non_exhausted_set):
                    vals.append({
                        'inventory_id': self.id,
                        'product_id': product_id,
                        'location_id': location_id,
                        'theoretical_qty': 0
                    })
        return vals
