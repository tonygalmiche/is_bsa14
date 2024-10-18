# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_correction_stock(models.Model):
    _name='is.correction.stock'
    _description='Correction stock'
    _order='name desc'

    name             = fields.Char("N°", readonly=True)
    product_id       = fields.Many2one('product.product', 'Article', required=True)
    quantite         = fields.Integer("Quantité", required=True)
    location_id      = fields.Many2one('stock.location', "Emplacement d'origine", required=True)
    location_dest_id = fields.Many2one('stock.location', "Emplacement de destination", required=True)
    move_id          = fields.Many2one('stock.move', 'Mouvement de stock', readonly=True, copy=False)
    commentaire      = fields.Char("Commentaire")
    state            = fields.Selection([
        ('creation', 'Création'),
        ('valide'  , 'Validé'),
    ], "État", required=True, copy=False, default='creation')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.correction.stock')
        res = super(is_correction_stock, self).create(vals)
        return res


    def correction_stock_action(self):
        for obj in self:
            if not obj.move_id:
                reference="%s %s"%(obj.name, obj.commentaire or '')
                vals={
                    "product_id": obj.product_id.id,
                    "product_uom": obj.product_id.uom_id.id,
                    "location_id": obj.location_id.id,
                    "location_dest_id": obj.location_dest_id.id,
                    "origin": reference,
                    "name": reference,
                    "reference": reference,
                    "product_uom_qty": obj.quantite,
                    "scrapped": False,
                    "propagate_cancel": True,
                    "additional": False,
                }
                move=self.env['stock.move'].create(vals)
                vals={
                    "move_id": move.id,
                    "product_id": obj.product_id.id,
                    "product_uom_id": obj.product_id.uom_id.id,
                    "location_id": obj.location_id.id,
                    "location_dest_id": obj.location_dest_id.id,
                    "qty_done": obj.quantite,
                    "reference": reference,
                }
                self.env['stock.move.line'].create(vals)
                move._action_done()
                obj.move_id = move.id
                obj.state='valide'

