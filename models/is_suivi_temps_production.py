# -*- coding: utf-8 -*-
from odoo import models,fields,api,tools
from odoo.addons.is_bsa14.models.mrp_production import _ETAT_OF


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






class is_suivi_temps_article(models.Model):
    _name='is.suivi.temps.article'
    _description='Suivi du temps des articles'
    _order='product_id'
    _auto = False


    ordre_id       = fields.Many2one('is.ordre.travail', 'N°OT')
    production_id  = fields.Many2one('mrp.production', 'Ordre de production')
    date_client    = fields.Date('Date client')
    date_prevue    = fields.Datetime('Date prévue')
    is_client_order_ref   = fields.Char(string="Référence client")
    is_sale_order_line_id = fields.Many2one("sale.order.line", "Ligne de commande")
    is_sale_order_id      = fields.Many2one("sale.order", "Commande")
    is_nom_affaire        = fields.Char("Affaire")
    bom_id                = fields.Many2one('mrp.bom', 'Nomenclature')
    product_id            = fields.Many2one('product.product', 'Article')
    is_cuve_niveau_complexite = fields.Text('Niveau de compléxité')
    is_type_cuve_id           = fields.Many2one("is.product.type.cuve", string="Type de cuve")
    is_volume_cuve_id         = fields.Many2one("is.volume.cuve", string="Volume cuve")
    is_finition_cuve_ids      = fields.Many2many(related='product_id.is_finition_cuve_ids')
    product_qty = fields.Float('Qt', help="Qt à produire")
    is_pret     = fields.Selection([
            ('oui', 'Oui'),
            ('non', 'Non'),
        ], "Prêt", help="Prêt à produire")
    heure_debut_reelle   = fields.Datetime("Heure début réelle")
    duree_prevue         = fields.Float("Tps prévu")
    temps_passe          = fields.Float("Tps passé")
    avancement           = fields.Float("Avancement (%)", compute="_compute_temps_passe", readonly=True, store=True)
    operation_encours_id = fields.Many2one('is.ordre.travail.line', 'Opération en cours')
    etat_of              = fields.Selection(_ETAT_OF, "État OF")


    def init(self):
        cr=self._cr
        tools.drop_view_if_exists(cr, 'is_suivi_temps_article')
        cr.execute("""
            CREATE OR REPLACE view is_suivi_temps_article AS (
                select 
                    iot.id,
                    iot.id ordre_id,
                    iot.production_id,
                    iot.date_prevue,
                    iot.heure_debut_reelle,
                    iot.operation_encours_id,
                    mp.is_date_prevue date_client,
                    mp.is_client_order_ref,
                    mp.is_sale_order_line_id,
                    mp.is_sale_order_id,
                    mp.is_nom_affaire,
                    mp.bom_id,
                    mp.product_id,
                    mp.product_qty,
                    mp.is_pret,
                    mp.state etat_of,
                    pt.is_cuve_niveau_complexite,
                    pt.is_type_cuve_id,
                    pt.is_volume_cuve_id,
                    iot.duree_prevue,
                    iot.temps_passe,
                    iot.avancement
                from is_ordre_travail iot join mrp_production    mp on iot.production_id=mp.id        
                                          join product_product   pp on mp.product_id=pp.id 
                                          join product_template  pt on pp.product_tmpl_id=pt.id                       
                where iot.id>0  
            );
        """)


