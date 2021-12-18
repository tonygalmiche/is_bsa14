# -*- coding: utf-8 -*-
from odoo import models,fields,api,tools

class is_account_move_line(models.Model):
    _name='is.account.move.line'
    _description='is.account.move.line'
    _order='move_id desc, id'
    _auto = False

    move_id                = fields.Many2one('account.move', 'Facture')
    #internal_number        = fields.Char("N°Facture")
    invoice_date           = fields.Date("Date Facture")
    #order_id               = fields.Many2one('sale.order', 'Commande')
    product_id             = fields.Many2one('product.product', 'Article')
    description            = fields.Text("Description")
    quantity               = fields.Float('Quantité'   , digits=(14,2))
    price_unit             = fields.Float('Prix unitaire', digits=(14,4))
    price_subtotal         = fields.Float('Montant HT'   , digits=(14,4))
    partner_id             = fields.Many2one('res.partner', u'Client/Fournisseur Facturé')
    #move_id                = fields.Many2one('stock.move', 'Mouvement')
    move_type              = fields.Char("Type Facture")
    state                  = fields.Char("Etat Facture")


    def init(self):
        cr=self._cr
        tools.drop_view_if_exists(cr, 'is_account_move_line')
        cr.execute("""
            CREATE OR REPLACE view is_account_move_line AS (
                select
                    aml.id,
                    aml.move_id,
                    am.invoice_date,
                    aml.product_id,
                    aml.name description,
                    aml.quantity,
                    aml.price_unit,
                    aml.price_subtotal,
                    am.partner_id,
                    am.move_type,
                    am.state
                from account_move_line aml inner join account_move am on aml.move_id=am.id
            );
        """)
# bsa14=# select * from sale_order_line_invoice_rel ;
#  invoice_line_id | order_line_id 
# -----------------+---------------
#                1 |             2
