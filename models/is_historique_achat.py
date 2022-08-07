# -*- coding: utf-8 -*-
from itertools import product
from odoo import models,fields,api
import datetime


class is_historique_achat_actualiser(models.Model):
    _name='is.historique.achat.actualiser'
    _description='Actualiser historique des achats'
    _order='famille_id'
    _rec_name = 'famille_id'

    famille_id = fields.Many2one('is.famille', 'Famille', required=True)

    def get_qt(self, annee, product_id, picking_type_id=0):
        cr=self._cr
        date_debut = annee+'-01-01 00:00:00'
        date_fin   = annee+'-12-31 23:59:59'
        SQL="""
            select sum(sm.product_uom_qty)
            from stock_move sm
            where 
                sm.product_id=%s  and 
                date>=%s and 
                date<=%s and 
                sm.state='done' and
                sm.picking_type_id=%s
        """
        cr.execute(SQL,[product_id, date_debut, date_fin, picking_type_id])
        moves = cr.fetchall()
        qt = 0
        for move in moves:
            qt = move[0]
        return qt


    def actualiser_action(self):
        for obj in self:
            # ** is.historique.achat.annee ************************************
            annees=self.env['is.annee'].search([])
            for line in annees:
                products=self.env['product.product'].search([('is_famille_id', '=', obj.famille_id.id)])
                for product in products:
                    historiques=self.env['is.historique.achat.annee'].search([('annee', '=', line.annee),('product_id', '=', product.id)])
                    if len(historiques)==0:
                        vals={
                            "product_id": product.id,
                            "annee"     : line.annee
                        }
                        historique=self.env['is.historique.achat.annee'].create(vals)
                    else:
                        historique=historiques[0]
                    qt = self.get_qt(line.annee, product.id, picking_type_id=1)
                    historique.qt_recue_importee = qt
                    qt = self.get_qt(line.annee, product.id, picking_type_id=8)
                    historique.qt_consommee_importee = qt

            # ** is.historique.achat ******************************************
            annees=self.env['is.annee'].search([],limit=3)
            ct=0
            for a in annees:
                print(a.annee)
                products=self.env['product.product'].search([('is_famille_id', '=', obj.famille_id.id)])
                for product in products:
                    lines=self.env['is.historique.achat'].search([('product_id', '=', product.id)])
                    if len(lines)==0:
                        vals={
                            "product_id": product.id,
                        }
                        line=self.env['is.historique.achat'].create(vals)
                    else:
                        line=lines[0]
                    historiques=self.env['is.historique.achat.annee'].search([('annee', '=', a.annee),('product_id', '=', product.id)])
                    print(historiques)
                    if len(historiques)>0:
                        historique = historiques[0]
                        if ct==0:
                            line.qt_recue_n0 = historique.qt_recue
                            line.qt_consommee_n0 = historique.qt_consommee
                        if ct==1:
                            line.qt_recue_n1 = historique.qt_recue
                            line.qt_consommee_n1 = historique.qt_consommee
                        if ct==2:
                            line.qt_recue_n2 = historique.qt_recue
                            line.qt_consommee_n2 = historique.qt_consommee
                ct+=1

            return obj.voir_les_lignes_action()


    def voir_les_lignes_action(self):
        for obj in self:
            return {
                "name": "Historique "+obj.famille_id.name,
                "view_mode": "tree,form",
                "res_model": "is.historique.achat",
                "domain": [
                    ("famille_id","=",obj.famille_id.id),
                ],
                "type": "ir.actions.act_window",
            }


class is_annee(models.Model):
    _name = 'is.annee'
    _description = "Années"
    _order='annee desc'
    _rec_name = 'annee'
    annee = fields.Char("Année", required=True)


class is_historique_achat_annee(models.Model):
    _name = 'is.historique.achat.annee'
    _description = "Historique des achats - Années"
    _order='annee desc, product_id'
    _rec_name = 'annee'

    annee                   = fields.Char("Année", required=True, index=True, readonly=True)
    product_id              = fields.Many2one('product.product', 'Article', required=True, index=True, readonly=True)
    famille_id              = fields.Many2one('is.famille', "Famille", related="product_id.is_famille_id", readonly=True)
    masse_tole              = fields.Float("Masse tôle", related="product_id.is_masse_tole", readonly=True)
    qt_recue_importee       = fields.Float("Qt reçue importée (unité)"               , readonly=True)
    qt_recue_correction     = fields.Float("Qt reçue correction (unité)")
    qt_recue                = fields.Float("Qt reçue (unité)"                        , store=True, readonly=True, compute='_compute_qt')
    qt_recue_kg             = fields.Float("Qt reçue (Kg)"                           , store=True, readonly=True, compute='_compute_qt')
    qt_consommee_importee   = fields.Float("Qt consommée importée (unité)"           , readonly=True)
    qt_consommee_correction = fields.Float("Qt consommée correction (unité)")
    qt_consommee            = fields.Float("Qt consommée (unité)"                    , store=True, readonly=True, compute='_compute_qt')
    qt_consommee_kg         = fields.Float("Qt consommée (Kg)"                       , store=True, readonly=True, compute='_compute_qt')


    @api.depends('qt_recue_importee','qt_recue_correction','qt_consommee_importee','qt_consommee_correction')
    def _compute_qt(self):
        for obj in self:
            qt_recue     = (obj.qt_recue_importee     or 0) + (obj.qt_recue_correction     or 0) 
            qt_consommee = (obj.qt_consommee_importee or 0) + (obj.qt_consommee_correction or 0) 
            obj.qt_recue     = qt_recue
            obj.qt_consommee = qt_consommee
            obj.qt_recue_kg     = qt_recue     * obj.masse_tole
            obj.qt_consommee_kg = qt_consommee * obj.masse_tole


class is_historique_achat(models.Model):
    _name = 'is.historique.achat'
    _description = "Historique des achats"
    _order='product_id'
    _rec_name = 'product_id'

    product_id              = fields.Many2one('product.product', 'Article', required=True, index=True, readonly=True)
    famille_id              = fields.Many2one('is.famille', "Famille", related="product_id.is_famille_id", readonly=True)
    masse_tole              = fields.Float("Masse tôle", related="product_id.is_masse_tole", readonly=True)
    qt_recue_n0             = fields.Float("Qt reçue N", readonly=True)
    qt_recue_kg_n0          = fields.Float("Qt reçue (Kg) N"      , store=True, readonly=True, compute='_compute_qt')
    qt_consommee_n0         = fields.Float("Qt consommée N", readonly=True)
    qt_consommee_kg_n0      = fields.Float("Qt consommée (Kg) N"  , store=True, readonly=True, compute='_compute_qt')

    qt_recue_n1             = fields.Float("Qt reçue N-1", readonly=True)
    qt_recue_kg_n1          = fields.Float("Qt reçue (Kg) N-1"    , store=True, readonly=True, compute='_compute_qt')
    qt_consommee_n1         = fields.Float("Qt consommée (unité) N-1", readonly=True)
    qt_consommee_kg_n1      = fields.Float("Qt consommée (Kg) N-1", store=True, readonly=True, compute='_compute_qt')

    qt_recue_n2             = fields.Float("Qt reçue N-2", readonly=True)
    qt_recue_kg_n2          = fields.Float("Qt reçue (Kg) N-2"    , store=True, readonly=True, compute='_compute_qt')
    qt_consommee_n2         = fields.Float("Qt consommée N-2", readonly=True)
    qt_consommee_kg_n2      = fields.Float("Qt consommée (Kg) N-2", store=True, readonly=True, compute='_compute_qt')


    @api.depends('qt_recue_n0','qt_consommee_n0','qt_recue_n1','qt_consommee_n1','qt_recue_n2','qt_consommee_n2')
    def _compute_qt(self):
        for obj in self:
            obj.qt_recue_kg_n0 = (obj.qt_recue_n0 or 0) * (obj.masse_tole or 0)
            obj.qt_recue_kg_n1 = (obj.qt_recue_n1 or 0) * (obj.masse_tole or 0)
            obj.qt_recue_kg_n2 = (obj.qt_recue_n2 or 0) * (obj.masse_tole or 0)

            obj.qt_consommee_kg_n0 = (obj.qt_consommee_n0 or 0) * (obj.masse_tole or 0)
            obj.qt_consommee_kg_n1 = (obj.qt_consommee_n1 or 0) * (obj.masse_tole or 0)
            obj.qt_consommee_kg_n2 = (obj.qt_consommee_n2 or 0) * (obj.masse_tole or 0)
