# -*- coding: utf-8 -*-
from odoo import models,fields,api,tools

class is_suivi_temps_production(models.Model):
    _name='is.suivi.temps.production'
    _description='Suivi du temps des employés'
    _order='heure_debut desc'
    _auto = False

    line_id     = fields.Many2one('is.ordre.travail.line', 'Ligne ordre de travail')
    employe_id  = fields.Many2one("hr.employee", "Opérateur")
    heure_debut = fields.Datetime("Heure de début")
    heure_fin   = fields.Datetime("Heure de fin")
    temps_passe = fields.Float("Temps passé (HH:MM)")

    name           = fields.Char("Opération")
    workcenter_id  = fields.Many2one('mrp.workcenter', 'Poste de Travail')
    ordre_id       = fields.Many2one('is.ordre.travail', 'N°OT')
    state          = fields.Selection([
            ('attente', 'Attente'),
            ('pret'   , 'Prêt'),
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
            ('annule' , 'Annulé'),
        ], "État", default='attente')

    production_id = fields.Many2one('mrp.production', 'Ordre de production')
    date_prevue   = fields.Datetime('Date prévue')

    is_client_order_ref   = fields.Char(string="Référence client")
    is_sale_order_line_id = fields.Many2one("sale.order.line", "Ligne de commande")
    is_sale_order_id      = fields.Many2one("sale.order", "Commande")
    is_nom_affaire        = fields.Char("Nom de l'affaire")
    bom_id                = fields.Many2one('mrp.bom', 'Nomenclature')
    product_id            = fields.Many2one('product.product', 'Article')


    def init(self):
        cr=self._cr
        tools.drop_view_if_exists(cr, 'is_suivi_temps_production')
        cr.execute("""
            CREATE OR REPLACE view is_suivi_temps_production AS (
                select 
                   tps.id,
                   tps.line_id,
                   tps.employe_id,
                   tps.heure_debut,
                   tps.heure_fin,
                   tps.temps_passe,
                   line.name,
                   line.workcenter_id,
                   line.ordre_id,
                   line.state,
                   iot.production_id,
                   iot.date_prevue,
                   mp.is_client_order_ref,
                   mp.is_sale_order_line_id,
                   mp.is_sale_order_id,
                   mp.is_nom_affaire,
                   mp.bom_id,
                   mp.product_id
                from is_ordre_travail_line_temps_passe tps join is_ordre_travail_line line on tps.line_id=line.id
                                                           join is_ordre_travail       iot on line.ordre_id=iot.id       
                                                           join mrp_production          mp on iot.production_id=mp.id                               
                where 
                    tps.id>0
            );
        """)
























class is_suivi_temps_production_ot(models.Model):
    _name='is.suivi.temps.production.ot'
    _description='Suivi du temps des OT'
    _order='date_prevue desc'
    _auto = False

    line_id        = fields.Many2one('is.ordre.travail.line', 'Ligne ordre de travail')
    duree_totale   = fields.Float("Temps prévu (HH:MM)")
    temps_passe    = fields.Float("Temps passé (HH:MM)")
    name           = fields.Char("Opération")
    workcenter_id  = fields.Many2one('mrp.workcenter', 'Poste de Travail')
    ordre_id       = fields.Many2one('is.ordre.travail', 'N°OT')
    state          = fields.Selection([
            ('attente', 'Attente'),
            ('pret'   , 'Prêt'),
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
            ('annule' , 'Annulé'),
        ], "État", default='attente')
    production_id = fields.Many2one('mrp.production', 'Ordre de production')
    date_prevue   = fields.Datetime('Date prévue')
    is_client_order_ref   = fields.Char(string="Référence client")
    is_sale_order_line_id = fields.Many2one("sale.order.line", "Ligne de commande")
    is_sale_order_id      = fields.Many2one("sale.order", "Commande")
    is_nom_affaire        = fields.Char("Nom de l'affaire")
    bom_id                = fields.Many2one('mrp.bom', 'Nomenclature')
    product_id            = fields.Many2one('product.product', 'Article')


    def init(self):
        cr=self._cr
        tools.drop_view_if_exists(cr, 'is_suivi_temps_production_ot')
        cr.execute("""
            CREATE OR REPLACE view is_suivi_temps_production_ot AS (
                select 
                   line.id,
                   line.id line_id,
                   line.duree_totale,
                   line.temps_passe,
                   line.name,
                   line.workcenter_id,
                   line.ordre_id,
                   line.state,
                   iot.production_id,
                   iot.date_prevue,
                   mp.is_client_order_ref,
                   mp.is_sale_order_line_id,
                   mp.is_sale_order_id,
                   mp.is_nom_affaire,
                   mp.bom_id,
                   mp.product_id
                from is_ordre_travail_line line join is_ordre_travail iot on line.ordre_id=iot.id       
                                                join mrp_production    mp on iot.production_id=mp.id                               
                where 
                    line.id>0
            );
        """)
