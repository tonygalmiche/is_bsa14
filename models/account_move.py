# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_mode_reglement(models.Model):
    _name = "is.mode.reglement"
    _description = "is.mode.reglement"
    name = fields.Char(string='Mode de règlement')


class account_move(models.Model):
    _inherit = "account.move"
    _order = "create_date desc"

    def _alerte_acompte(self):
        for obj in self:
            # ids=[]
            # for line in obj.invoice_line:
            #     id=line.is_stock_move_id.picking_id.sale_id.id
            #     if id and id not in ids:
            #         ids.append(id)
            # invoices=self.env['account.invoice'].search([
            #     ('is_sale_order_id', 'in' , ids),
            #     ('is_account_invoice_id', '=', False),
            #     ('state','not in', ['draft','cancel']),
            # ])
            # alerte = False
            # if invoices:
            #     alerte = u"ATTENTION : L'acompte "+str(invoices[0].number)+u" sur la commande "+str(invoices[0].is_sale_order_id.name)+u" n'a pas été traité"
            alerte=False
            obj.is_alerte_acompte = alerte


    @api.depends('invoice_line_ids')
    def _compute_is_sale_order_compute_id(self):
        for obj in self:
            order_id = False
            for line in obj.invoice_line_ids:
                for l in line.sale_line_ids:
                    order_id = l.order_id.id
            obj.is_sale_order_compute_id = order_id


    @api.depends('invoice_line_ids')
    def _compute_is_type_livraison(self):
        for obj in self:
            order_id = False
            v=type_livraison=False
            for line in obj.invoice_line_ids:
                type_livraison = line.product_id.is_type_livraison
                if type_livraison and not v:
                    v=type_livraison
                if type_livraison and v and v!=type_livraison:
                    type_livraison='livraison_biens_prestation_services'
                    break
            obj.is_type_livraison = type_livraison



    is_acompte               = fields.Float("Acompte")
    is_imputation_partenaire = fields.Char("Imputation partenaire")
    is_contact_id            = fields.Many2one('res.partner', string='Contact')
    is_mode_reglement_id     = fields.Many2one('is.mode.reglement', string='Mode de règlement')
    is_sale_order_id         = fields.Many2one('sale.order', string="Facture de situation sur la commande")
    is_sale_order_compute_id = fields.Many2one('sale.order', string="Commande client", store=False, readonly=True, compute='_compute_is_sale_order_compute_id')
    is_account_invoice_id    = fields.Many2one('account.move', string="Acompte traité sur la facture")
    is_alerte_acompte        = fields.Char("Alerte acompte", store=False, compute='_alerte_acompte')

    is_type_livraison        = fields.Selection([
            ('livraison_biens'                    , 'Livraison de biens'),
            ('prestation_services'                , 'Prestation de services'),
            ('livraison_biens_prestation_services', 'Livraison de biens et prestation de services'),
        ], "Type de livraison", compute='_compute_is_type_livraison', help="Mention obligatoire sur les factures depuis le 01/10/22")



    # def name_get(self):
    #     res=[]
    #     for obj in self:
    #         name=obj.number or ''
    #         res.append((obj.id, name))
    #     return res


    # def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
    #     if not args:
    #         args = []
    #     if name:
    #         filtre=['|',('name','ilike', name),('internal_number','ilike', name)]
    #         ids = self.search(cr, user, filtre, limit=limit, context=context)
    #     else:
    #         ids = self.search(cr, user, args, limit=limit, context=context)
    #     result = self.name_get(cr, user, ids, context=context)
    #     return result

