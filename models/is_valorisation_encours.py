# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_valorisation_encours(models.Model):
    _name='is.valorisation.encours'
    _description='Valorisation encours'
    _order='name desc'

    name               = fields.Char("N°", readonly=True)
    ligne_ids          = fields.One2many('is.valorisation.encours.ligne', 'valorisation_id', 'Lignes')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.valorisation.encours')
        res = super(is_valorisation_encours, self).create(vals)
        return res


    def generer_ligne_action(self):
        for obj in self:
            obj.ligne_ids.unlink()
            domain=[
                ('state','not in', ['cancel','done','draft']),
            ]
            productions=self.env['mrp.production'].search(domain, order='name')
            for production in productions:
                temps_restant=0
                for line in production.is_ordre_travail_id.line_ids:
                    temps_restant+=line.reste
                if temps_restant<0:
                    temps_restant=0

                order_line_id       = production.is_sale_order_line_id
                montant_facture     = order_line_id.price_subtotal * order_line_id.qty_invoiced
                reste_a_facturer    = order_line_id.price_subtotal - montant_facture
                montant_tps_restant = temps_restant*60
                reste               = reste_a_facturer - montant_tps_restant
                vals={
                    'valorisation_id'    : obj.id,
                    'production_id'      : production.id,
                    'ordre_id'           : production.is_ordre_travail_id.id,
                    'order_id'           : production.is_sale_order_id.id,
                    'order_line_id'      : order_line_id.id,
                    'temps_restant'      : temps_restant, 
                    'prix_vente'         : production.product_id.lst_price,
                    'montant_facture'    : montant_facture,
                    'reste_a_facturer'   : reste_a_facturer,
                    'montant_tps_restant': temps_restant*60,
                    'reste'              : reste,
                    'abattement'         : reste*0.85,
                }
                self.env['is.valorisation.encours.ligne'].create(vals)


class is_valorisation_encours_ligne(models.Model):
    _name = 'is.valorisation.encours.ligne'
    _description = "Lignes Valorisation encours"
    _order='production_id'

    valorisation_id     = fields.Many2one('is.valorisation.encours', 'Valorisation encours', required=True)
    production_id       = fields.Many2one('mrp.production', 'OF')
    ordre_id            = fields.Many2one('is.ordre.travail', 'OT')
    order_id            = fields.Many2one('sale.order', 'Commande')
    order_line_id       = fields.Many2one('sale.order.line', 'Ligne de commande')
    temps_restant       = fields.Float("Temps restant (HH:MM)")
    prix_vente          = fields.Float("Prix vente"     , digits='Product Price')
    montant_facture     = fields.Float("Montant facturé" , digits=(14,2), help="Montant facturé (Situation)")
    reste_a_facturer    = fields.Float("Reste à facturer", digits=(14,2))
    montant_tps_restant = fields.Float("Montant temps restant" , digits=(14,2))
    reste               = fields.Float("Reste à facturer - Tps restant", digits=(14,2), help="'Reste à facturer' MOINS 'Montant temps restant'")
    abattement          = fields.Float("Abattement moins 15%", digits=(14,2))
