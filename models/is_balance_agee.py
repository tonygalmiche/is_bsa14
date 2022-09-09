# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime
from odoo.exceptions import Warning
import unicodedata


class is_balance_agee(models.Model):
    _name='is.balance.agee'
    _description='is.balance.agee'
    _order='date_creation desc'
    _rec_name = 'date_creation'

    type_balance  = fields.Selection([('ventes', u'Ventes'),('achats', u'Achats')], "Type de balance", required=True, default="ventes")
    avoir         = fields.Boolean("Inclure les avoirs"                   , default=True)
    date_creation = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    createur_id   = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    ligne_ids     = fields.One2many('is.balance.agee.ligne', 'balance_id', u'Lignes')


    def generer_lignes_action(self):
        for obj in self:
            res={}
            now = datetime.date.today()
            obj.ligne_ids.unlink()
            if obj.type_balance=='ventes':
                move_type=['out_invoice']
                if obj.avoir:
                    move_type=['out_invoice', 'out_refund']
            else:
                move_type=['in_invoice']
                if obj.avoir:
                    move_type=['in_invoice', 'in_refund']
            filter=[
                ('state'       , 'in' , ['posted']),
                ('move_type'   , 'in' , move_type)
            ]


            invoices = self.env['account.move'].search(filter, order="partner_id,invoice_date_due,id")
            for invoice in invoices:
                date_due = invoice.invoice_date_due
                delta  = (date_due - now).days + 1
                residual   = invoice.amount_residual

                if invoice.move_type=="out_refund":
                    residual=-residual


                partner_id = invoice.partner_id
                if partner_id not in res:
                    res[partner_id]=[0,0,0,0,0,0,0]

                res[partner_id][0]+=residual
                if delta>=0:
                    res[partner_id][1]+=residual
                if delta<0 and delta>=-30:
                    res[partner_id][2]+=residual
                if delta<-30 and delta>=-60:
                    res[partner_id][3]+=residual
                if delta<-60 and delta>=-90:
                    res[partner_id][4]+=residual
                if delta<-90 and delta>=-120:
                    res[partner_id][5]+=residual
                if delta<-120:
                    res[partner_id][6]+=residual

                #print(invoice.invoice_date_due,delta, invoice.partner_id.name,invoice.amount_residual)

            for line in res:
                if line.id:
                    vals={
                        'balance_id': obj.id,
                        'partner_id': line.id,
                        'solde'     : res[line][0],
                        'creance1'  : res[line][1],
                        'creance2'  : res[line][2],
                        'creance3'  : res[line][3],
                        'creance4'  : res[line][4],
                        'creance5'  : res[line][5],
                        'creance6'  : res[line][6],
                    }
                    self.env['is.balance.agee.ligne'].create(vals)


class is_balance_agee_ligne(models.Model):
    _name = 'is.balance.agee.ligne'
    _description = "Lignes balance agée"
    _order='partner_id'

    balance_id = fields.Many2one('is.balance.agee', u'Balance agée', required=True)
    partner_id = fields.Many2one('res.partner', u'Partenaire', required=True)
    solde      = fields.Float("Solde")
    creance1   = fields.Float("Créance non échue")
    creance2   = fields.Float("Créance +0j à 30j")
    creance3   = fields.Float("Créance +30j à 60j")
    creance4   = fields.Float("Créance +60j à 90j")
    creance5   = fields.Float("Créance +90j à 120j")
    creance6   = fields.Float("Créance +120j")





