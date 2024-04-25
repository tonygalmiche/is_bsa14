# -*- coding: utf-8 -*-
from itertools import product
from odoo import models,fields,api
import datetime
import logging
_logger = logging.getLogger(__name__)


class is_historique_achat_actualiser(models.Model):
    _name='is.historique.achat.actualiser'
    _description='Actualiser historique des achats'
    _order='famille_id'
    _rec_name = 'famille_id'

    famille_id = fields.Many2one('is.famille', 'Famille', required=True)

    def get_qt(self, annee, product_id, picking_type_id=0, where=False):
        cr=self._cr
        SQL="""
            select sum(sm.product_uom_qty)
            from stock_move sm
            where sm.product_id=%s  and sm.picking_type_id=%s
        """
        if annee:
            date_debut = annee+'-01-01 00:00:00'
            date_fin   = annee+'-12-31 23:59:59'
            SQL+=" and date>='%s' and date<='%s' "%(date_debut,date_fin) 
        if where:
            SQL+=" and " + where
        cr.execute(SQL,[product_id, picking_type_id])
        moves = cr.fetchall()
        qt = 0
        for move in moves:
            qt = move[0]
        return qt



    def actualiser_action_ir_cron(self):
        res=self.env['is.historique.achat.actualiser'].search([])
        nb = len(res)
        ct=1
        for obj in res:
            obj.actualiser_action()
            _logger.info("%s/%s actualiser_action_ir_cron : %s (%s)"%(ct,nb,obj,obj.famille_id.name))
            ct+=1
        return True






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
                    qt = self.get_qt(line.annee, product.id, picking_type_id=1, where="sm.state='done'")
                    historique.qt_recue_importee = qt
                    qt = self.get_qt(line.annee, product.id, picking_type_id=8, where="sm.state='done'")
                    historique.qt_consommee_importee = qt

            # ** is.historique.achat ******************************************
            annees=self.env['is.annee'].search([],limit=3)
            ct=0
            for a in annees:
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
                    if len(historiques)>0:
                        historique = historiques[0]
                        if ct==0:
                            line.qt_recue_n0 = historique.qt_recue
                            line.qt_consommee_n0 = historique.qt_consommee

                            line.en_cours_livraison = self.get_qt(a.annee, product.id, picking_type_id=1, where="sm.state not in ('done', 'cancel')")
                            line.conso_prevue       = self.get_qt(False, product.id, picking_type_id=8, where="sm.state not in ('done', 'cancel')")



                        if ct==1:
                            line.qt_recue_n1 = historique.qt_recue
                            line.qt_consommee_n1 = historique.qt_consommee
                        if ct==2:
                            line.qt_recue_n2 = historique.qt_recue
                            line.qt_consommee_n2 = historique.qt_consommee
                    line.cout       = product.standard_price
                    line.stock_reel = product.qty_available

                ct+=1

            return obj.voir_les_lignes_action()


    def effacer_prevision_action(self):
        for obj in self:
            lines=self.env['is.historique.achat'].search([('famille_id', '=', obj.famille_id.id)])
            for line in lines:
                line.prevision_appro = 0


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
    qt_consommee_n1         = fields.Float("Qt consommée N-1", readonly=True)
    qt_consommee_kg_n1      = fields.Float("Qt consommée (Kg) N-1", store=True, readonly=True, compute='_compute_qt')

    qt_recue_n2             = fields.Float("Qt reçue N-2", readonly=True)
    qt_recue_kg_n2          = fields.Float("Qt reçue (Kg) N-2"    , store=True, readonly=True, compute='_compute_qt')
    qt_consommee_n2         = fields.Float("Qt consommée N-2", readonly=True)
    qt_consommee_kg_n2      = fields.Float("Qt consommée (Kg) N-2", store=True, readonly=True, compute='_compute_qt')

    stock_reel            = fields.Float("Stock réel", readonly=True)
    stock_reel_kg         = fields.Float("Stock réel (Kg)"            , store=True, readonly=True, compute='_compute_qt')
    en_cours_livraison    = fields.Float("En cours de livraison", readonly=True)
    en_cours_livraison_kg = fields.Float("En cours de livraison (Kg)" , store=True, readonly=True, compute='_compute_qt')
    conso_prevue          = fields.Float("Conso prévue", readonly=True)
    conso_prevue_kg       = fields.Float("Conso prévue (Kg)"          , store=True, readonly=True, compute='_compute_qt')
    stock_final           = fields.Float("Stock après mouvements"     , store=True, readonly=True, compute='_compute_qt')
    stock_final_kg        = fields.Float("Stock après mouvements (Kg)", store=True, readonly=True, compute='_compute_qt')
    stock_secu            = fields.Float("Stock sécu", readonly=True)
    stock_secu_kg         = fields.Float("Stock sécu (Kg)"            , store=True, readonly=True, compute='_compute_qt')
    prevision_appro       = fields.Float("Prévision d'appro")
    prevision_appro_kg    = fields.Float("Prévision d'appro (Kg)"     , store=True, readonly=True, compute='_compute_qt')
    cout                  = fields.Float("Coût (€/Kg)", readonly=True)
    montant_total         = fields.Float("Montant total (€)", store=True, readonly=True, compute='_compute_qt')

    @api.depends('qt_recue_n0','qt_consommee_n0','qt_recue_n1','qt_consommee_n1','qt_recue_n2','qt_consommee_n2', 'stock_reel', 'en_cours_livraison', 'conso_prevue', 'stock_final', 'prevision_appro', 'cout')
    def _compute_qt(self):
        for obj in self:
            obj.stock_final   = (obj.stock_reel or 0) + (obj.en_cours_livraison or 0)  - (obj.conso_prevue or 0) 
            obj.montant_total = (obj.prevision_appro or 0) * (obj.cout or 0) 

            masse_tole = obj.masse_tole or 0
            obj.qt_recue_kg_n0 = (obj.qt_recue_n0 or 0) * masse_tole
            obj.qt_recue_kg_n1 = (obj.qt_recue_n1 or 0) * masse_tole
            obj.qt_recue_kg_n2 = (obj.qt_recue_n2 or 0) * masse_tole

            obj.qt_consommee_kg_n0 = (obj.qt_consommee_n0 or 0) * masse_tole
            obj.qt_consommee_kg_n1 = (obj.qt_consommee_n1 or 0) * masse_tole
            obj.qt_consommee_kg_n2 = (obj.qt_consommee_n2 or 0) * masse_tole

            obj.stock_reel_kg         = (obj.stock_reel or 0) * masse_tole
            obj.en_cours_livraison_kg = (obj.en_cours_livraison or 0) * masse_tole
            obj.conso_prevue_kg       = (obj.conso_prevue or 0) * masse_tole
            obj.stock_final_kg        = (obj.stock_final or 0) * masse_tole
            obj.stock_secu_kg         = (obj.stock_secu or 0) * masse_tole
            obj.prevision_appro_kg    = (obj.prevision_appro or 0) * masse_tole


    def vue_formulaire_action(self):
        for obj in self:
            res={
                'name': 'Historique achat',
                'view_mode': 'form',
                'res_model': 'is.historique.achat',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res




