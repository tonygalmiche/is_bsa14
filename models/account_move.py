# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_mode_reglement(models.Model):
    _name = "is.mode.reglement"
    _description = "is.mode.reglement"
    name = fields.Char(string='Mode de règlement')


class is_situation(models.Model):
    _name = "is.situation"
    _description = "Situation de la facture"
    name = fields.Char(string='Situation', required=True)


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
    is_sale_order_id         = fields.Many2one('sale.order', string="Facture de situation sur la commande", copy=False)
    is_sale_order_compute_id = fields.Many2one('sale.order', string="Commande client", store=False, readonly=True, compute='_compute_is_sale_order_compute_id')
    is_account_invoice_id    = fields.Many2one('account.move', string="Acompte traité sur la facture")
    is_alerte_acompte        = fields.Char("Alerte acompte", store=False, compute='_alerte_acompte')

    is_type_livraison        = fields.Selection([
            ('livraison_biens'                    , 'Livraison de biens'),
            ('prestation_services'                , 'Prestation de services'),
            ('livraison_biens_prestation_services', 'Livraison de biens et prestation de services'),
        ], "Type de livraison", compute='_compute_is_type_livraison', help="Mention obligatoire sur les factures depuis le 01/10/22")
    is_situation    = fields.Char("Situation (ancien champ)", readonly=True)
    is_situation_id = fields.Many2one('is.situation', string='Situation')
    is_type_facturation = fields.Selection(related="is_sale_order_id.is_type_facturation")


    def write(self, vals):
        res = super(account_move, self).write(vals)
        for obj in self:
            obj.is_sale_order_id._compute_is_total_facture()
            obj.is_sale_order_compute_id._compute_is_total_facture()
        return res


    def acceder_facture_action(self):
        for obj in self:
            res= {
                'name': 'Facture',
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
                'domain': [('type','=','out_invoice')],
            }
            return res




    @api.depends('posted_before', 'state', 'journal_id', 'date')
    def _compute_name(self):
        res = super(account_move, self)._compute_name()
        print("## actualiser_facturable_action",res,self)
        for obj in self:
            for line in obj.invoice_line_ids:
                if line.is_sale_line_id:
                    line.is_sale_line_id.actualiser_facturable_action()



