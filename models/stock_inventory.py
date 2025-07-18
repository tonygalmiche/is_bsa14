# -*- coding: utf-8 -*-
from odoo import models,fields,api



class stock_inventory(models.Model):
    _inherit = "stock.inventory"
    _order="date desc"
     
    product_stock_category_id = fields.Many2one("is.stock.category", string="Catégorie de stock")
    is_date_forcee            = fields.Datetime("Date forcée pour l'inventaire")
    is_saisie_ids             = fields.One2many('is.stock.inventory.ligne', 'inventaire_id', 'Saisies', help="Saisies par scan")


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



    def voir_saisies_action(self):
        for obj in self:
            return {
                "name": 'Lignes',
                "view_mode": "tree",
                "res_model": "is.stock.inventory.ligne",
                "domain": [
                    ("inventaire_id" ,"=",obj.id),
                ],
                'context': {
                    'default_inventaire_id': obj.id 
                },
                "type": "ir.actions.act_window",
            }



    def actualiser_inventaire_action(self):
        for obj in self:
            scans = self.env['is.stock.inventory.ligne'].search([('inventaire_id', '=', obj.id)])
            scan_dict={}
            for scan in scans:
                if scan.product_id not in scan_dict:
                    scan_dict[scan.product_id] = 0
                scan_dict[scan.product_id] += scan.quantite
            lines = self.env['stock.inventory.line'].search([('inventory_id', '=', obj.id)])
            products=[]
            for line in lines:
                if line.product_id not in products:
                    products.append(line.product_id)

            #** Recherche de l'emplacement de stock par défaut ****************
            warehouses = self.env['stock.warehouse'].search([])
            location_id=False
            for warehouse in warehouses:
                location_id = warehouse.lot_stock_id.id
            #******************************************************************

            #** Ajout des artiles si manquant *********************************
            if location_id:
                for product in scan_dict:
                    if product not in products:
                        vals={
                            'product_id'  : product.id,
                            'inventory_id': obj.id,
                            'location_id' : location_id,
                        }
                        self.env['stock.inventory.line'].create(vals)
            for line in lines:
                line.product_qty = scan_dict.get(line.product_id)
 

class stock_inventory_line(models.Model):
    _inherit = "stock.inventory.line"
     
    is_stock_category_id = fields.Many2one("is.stock.category", related="product_id.is_stock_category_id")


class is_stock_inventory_ligne(models.Model):
    _name = "is.stock.inventory.ligne"
    _description = "Lignes des saisies par scan pour l'inventaire"
    _order='create_date desc'

    inventaire_id = fields.Many2one('stock.inventory', 'Inventaire', required=True, ondelete='cascade')
    product_id    = fields.Many2one('product.product', 'Article', required=True)
    quantite      = fields.Float("Quantité comptée"  , digits='Product Unit of Measure')
    employe_id    = fields.Many2one('hr.employee', 'Employé', readonly=True)


