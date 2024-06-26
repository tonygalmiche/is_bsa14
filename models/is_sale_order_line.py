# -*- coding: utf-8 -*-
from odoo import models,fields,api,tools

class is_sale_order_line(models.Model):
    _name='is.sale.order.line'
    _description='is.sale.order.line'
    _order='date_order desc'
    _auto = False

    order_id               = fields.Many2one('sale.order', 'Commande')
    date_order             = fields.Date("Date commande")
    client_order_ref       = fields.Char("Commande client")
    is_notre_ref_devis     = fields.Char("Notre référence de devis")
    is_nom_affaire         = fields.Char("Nom de l'affaire")
    contact_id             = fields.Many2one('res.partner', 'Contact')
    partner_id             = fields.Many2one('res.partner', 'Client')
    is_categorie_client_id = fields.Many2one('is.categorie.client', string='Catégorie de client')
    product_id             = fields.Many2one('product.product', 'Article')
    product_uom_qty        = fields.Float('Qt commandée', digits=(14,2))
    qt_livree              = fields.Float('Qt livrée'   , digits=(14,2))
    reste_a_livrer         = fields.Float('Reste à livrer'   , digits=(14,2))
    price_unit             = fields.Float('Prix'        , digits=(14,2))
    discount               = fields.Float('Remise (%)'  , digits=(14,2))
    montant_ht             = fields.Float('Montant HT commandé'  , digits=(14,2))
    montant_reste_a_livrer = fields.Float('Montant HT reste à livrer'  , digits=(14,2))
    is_date_prevue         = fields.Date("Date prévue")
    is_date_demandee       = fields.Date("Date demandée")
    state                  = fields.Char("Etat de la commande")

    is_facturable_pourcent     = fields.Float("% facturable"    , digits=(14,2), help="% facturable à ce jour permettant de générer une nouvelle facture" )
    is_facture_avant_pourcent  = fields.Float("% facturé avant" , digits=(14,2), help="% factturé hors situation (ex : Accompte) pour reprendre l'historique")
    is_deja_facture_pourcent   = fields.Float("% déjà facturé"  , digits=(14,2))
    is_facturable              = fields.Float("Facturable"      , digits=(14,2))
    is_deja_facture            = fields.Float("Déja facturé"    , digits=(14,2))
    is_a_facturer              = fields.Float("A Facturer"      , digits=(14,2))
    is_reste_a_facturer        = fields.Float("Reste à facturer", digits=(14,2))


    def init(self):
        cr=self._cr
        tools.drop_view_if_exists(cr, 'is_sale_order_line')
        cr.execute("""
            CREATE OR REPLACE view is_sale_order_line AS (
                select 
                    sol.id,
                    sol.order_id,
                    so.date_order,
                    so.partner_id contact_id,
                    COALESCE(rp.parent_id,so.partner_id) partner_id,
                    rp.is_categorie_client_id,
                    sol.product_id,
                    sol.product_uom_qty,
                    sol.price_unit,
                    sol.discount,
                   
                    sol.is_facturable_pourcent,
                    sol.is_facture_avant_pourcent,
                    sol.is_deja_facture_pourcent,
                    sol.is_facturable,
                    sol.is_deja_facture,
                    sol.is_a_facturer,
                    sol.is_reste_a_facturer,

                    sol.product_uom_qty*sol.price_unit*(100-discount)/100 montant_ht,
                    sol.is_date_prevue,
                    sol.is_date_demandee,
                    so.client_order_ref,
                    so.is_notre_ref_devis,
                    so.is_nom_affaire,
                    so.state,
                    COALESCE((select sum(sm.product_uom_qty) from stock_move sm where sm.sale_line_id=sol.id and sm.state='done'),0) qt_livree,
                    (sol.product_uom_qty-COALESCE((select sum(sm.product_uom_qty) from stock_move sm where sm.sale_line_id=sol.id and sm.state='done'),0)) reste_a_livrer,
                    (sol.product_uom_qty-COALESCE((select sum(sm.product_uom_qty) from stock_move sm where sm.sale_line_id=sol.id and sm.state='done'),0))*sol.price_unit*(100-discount)/100 montant_reste_a_livrer
                from sale_order_line sol inner join sale_order so on sol.order_id=so.id
                                         inner join res_partner rp on so.partner_id=rp.id
                where 
                    sol.state<>'cancel' and 
                    so.state<>'cancel'
            );
        """)

                    # 
