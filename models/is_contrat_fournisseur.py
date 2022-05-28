# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import Warning
import datetime

class is_contrat_fournisseur(models.Model):
    _name='is.contrat.fournisseur'
    _description='Contrat de commande ouverte fournisseur'
    _inherit = ['mail.thread']
    _order='name desc'

    name            = fields.Char("N°", readonly=True)
    createur_id     = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation   = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    partner_id      = fields.Many2one('res.partner', 'Fournisseur', required=True)
    date_debut      = fields.Date("Date de début", required=True)
    date_fin        = fields.Date("Date de fin", required=True)
    ref_contrat     = fields.Char("Référence contrat", help="Référence contrat du fournisseur")
    ligne_ids       = fields.One2many('is.contrat.fournisseur.ligne', 'contrat_id', 'Lignes')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.contrat.fournisseur')
        res = super(is_contrat_fournisseur, self).create(vals)
        return res


class is_contrat_fournisseur_ligne(models.Model):
    _name='is.contrat.fournisseur.ligne'
    _description='Lignes de contrat de commande ouverte fournisseur'
    _order='product_id'

    contrat_id    = fields.Many2one('is.contrat.fournisseur', 'Contrat', required=True)
    product_id    = fields.Many2one('product.product', 'Article', required=True)
    qt_contrat    = fields.Float("Qt prévue", required=True)
    currency_id   = fields.Many2one('res.currency', "Devise"                     , compute='_compute_montant', readonly=True, store=True)
    prix_unitaire = fields.Monetary("Prix unitaire", currency_field='currency_id')
    montant       = fields.Monetary("Montant"      , currency_field='currency_id', compute='_compute_montant', readonly=True, store=True)
    qt_commande   = fields.Float("Qt commandée"     , compute='_compute_qt', readonly=True)
    qt_reste      = fields.Float("Reste à commander", compute='_compute_qt', readonly=True)


    @api.depends('product_id','qt_contrat','prix_unitaire')
    def _compute_montant(self):
        company = self.env.user.company_id
        for obj in self:
            obj.currency_id = company.currency_id.id
            montant = obj.qt_contrat*obj.prix_unitaire
            obj.montant = montant
    

    @api.depends('product_id','qt_contrat')
    def _compute_qt(self):
        company = self.env.user.company_id
        for obj in self:
            qt_contrat  = obj.qt_contrat
            qt_cde = self.env['purchase.order.line'].get_qt_cde(obj.contrat_id.partner_id.id, obj.product_id.id, obj.contrat_id.id)
            obj.qt_commande = qt_cde
            obj.qt_reste = qt_contrat - qt_cde


    def liste_commandes_action(self):
        for obj in self:

            view_id = self.env['ir.model.data'].get_object_reference('is_bsa14', 'is_purchase_order_line_tree')[1]


            filtre=[
                ("is_contrat_id","=",obj.contrat_id.id),
                ("product_id"   ,"=",obj.product_id.id),
                ("state"        ,"=","purchase"),
            ]
            lines = self.env["purchase.order.line"].search(filtre)
            ids=[]
            for line in lines:
                ids.append(line.id)
            return {
                "name": "Commandes du contrat "+obj.contrat_id.name,
                "view_mode": "tree,form",
                "view_type": "form",

                'views': [(view_id, 'tree')],
                #'view_id': compose_form_id,


                "res_model": "purchase.order.line",
                "domain": [
                    ("id","in",ids),
                ],
                "type": "ir.actions.act_window",
            }

