# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_correction_stock_cause(models.Model):
    _name='is.correction.stock.cause'
    _description='Cause correction stock'
    _order='name'

    name = fields.Char("Cause", required=True)


class is_correction_stock(models.Model):
    _name='is.correction.stock'
    _description='Correction stock'
    _order='name desc'

    name             = fields.Char("N°", readonly=True)
    product_id       = fields.Many2one('product.product', 'Article', required=True)
    quantite         = fields.Integer("Quantité à modifier", required=True)
    location_id      = fields.Many2one('stock.location', "Emplacement d'origine"     , required=False, store=True, readonly=True, compute='_compute_location_id')
    location_dest_id = fields.Many2one('stock.location', "Emplacement de destination", required=False, store=True, readonly=True, compute='_compute_location_id')
    move_id          = fields.Many2one('stock.move', 'Mouvement de stock', readonly=True, copy=False)
    cause_id         = fields.Many2one('is.correction.stock.cause', 'Cause correction stock')
    commentaire      = fields.Char("Commentaire")
    state            = fields.Selection([
        ('creation', 'Création'),
        ('valide'  , 'Validé'),
    ], "État", required=True, copy=False, default='creation')


    @api.depends('quantite')
    def _compute_location_id(self):
        for obj in self:
            location_id = location_dest_id = False
            locations=self.env['stock.location'].search([('usage' , '=' , 'internal')],limit=1)
            for location in locations:
                location_id = location.id
            locations=self.env['stock.location'].search([('usage' , '=' , 'production')],limit=1)
            for location in locations:
                location_dest_id = location.id
            if obj.quantite>0:
                mem_location_id  = location_id
                location_id      = location_dest_id
                location_dest_id = mem_location_id
            obj.location_id = location_id
            obj.location_dest_id = location_dest_id


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.correction.stock')
        res = super(is_correction_stock, self).create(vals)
        return res


    def correction_stock_action(self):
        for obj in self:
            if not obj.move_id:
                reference="%s %s %s"%(obj.name, obj.cause_id.name or '', obj.commentaire or '')
                vals={
                    "product_id": obj.product_id.id,
                    "product_uom": obj.product_id.uom_id.id,
                    "location_id": obj.location_id.id,
                    "location_dest_id": obj.location_dest_id.id,
                    "origin": reference,
                    "name": reference,
                    "reference": reference,
                    "product_uom_qty": abs(obj.quantite),
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
                    "qty_done": abs(obj.quantite),
                    "reference": reference,
                }
                self.env['stock.move.line'].create(vals)
                move._action_done()
                obj.move_id = move.id
                obj.state='valide'

