# -*- coding: utf-8 -*-
from odoo import models,fields,api,tools, SUPERUSER_ID
from datetime import datetime, date, timedelta
from odoo.exceptions import Warning


class is_gabarit(models.Model):
    _name="is.gabarit"
    _description="is_gabarit"
    _order="name"
    _sql_constraints = [("name_uniq","UNIQUE(name)", "Ce gabarit existe déjà")] 

    name = fields.Char("Gabarit", required=True)


class is_workcenter_line_temps_passe(models.Model):
    _name = "is.workcenter.line.temps.passe"
    _description="is_workcenter_line_temps_passe"

    @api.depends("heure_debut","heure_fin")
    def _compute_temps_passe(self):
        for obj in self:
            temps_passe = 0
            if obj.heure_debut and obj.heure_fin:
                nb = obj.nb or 1
                heure_debut = datetime.strptime(obj.heure_debut, "%Y-%m-%d %H:%M:%S")
                heure_fin   = datetime.strptime(obj.heure_fin, "%Y-%m-%d %H:%M:%S")
                temps_passe = nb*(heure_fin - heure_debut).total_seconds()/3600
            obj.temps_passe = temps_passe

    #workcenter_line_id = fields.Many2one("mrp.production.workcenter.line", "Ordre de travail", required=True, ondelete="cascade", readonly=True)
    employe_id  = fields.Many2one("hr.employee", "Opérateur")
    nb          = fields.Integer("Nombre de personnes au poste",default=1)
    heure_debut = fields.Datetime("Heure de début")
    heure_fin   = fields.Datetime("Heure de fin")
    temps_passe = fields.Float("Temps passé", compute="_compute_temps_passe", readonly=True, store=True)


class mrp_bom(models.Model):
    _inherit  = "mrp.bom"
    _order    = "product_tmpl_id"

    is_gamme_generique_id = fields.Many2one('is.gamme.generique', 'Gamme générique')


    def actualiser_gammes_action(self):
        for obj in self:
            obj.operation_ids.unlink()
            for line in obj.is_gamme_generique_id.ligne_ids:
                vals={
                    'bom_id'           : obj.id,
                    'sequence'         : line.sequence,
                    'name'             : line.name,
                    'workcenter_id'    : line.workcenter_id.id,
                    'time_cycle_manual': line.duree,
                    'is_duree_heure'   : line.duree/60,
                }
                self.env['mrp.routing.workcenter'].create(vals)


class mrp_bom_line(models.Model):
    _inherit  = "mrp.bom.line"

    @api.depends("product_id")
    def _compute_is_line_type(self):
        for obj in self:
            x="composant"
            for line in obj.product_id.bom_ids:
                x=line.type
            obj.is_line_type= x


    is_line_type = fields.Selection([
            ('composant'   , 'Composant'),
            ('normal', 'Nomenclature'),
            ('phantom'         , 'Kit'),
        ], "Type", compute="_compute_is_line_type", readonly=True, store=False)


class mrp_routing_workcenter(models.Model):
    _inherit  = "mrp.routing.workcenter"

    is_offset      = fields.Integer("Offset (jour)", help="Offset en jours par rapport à l'opération précédente pour le calcul du planning")
    is_duree_heure = fields.Float("Durée (Heures)")


    @api.onchange('is_duree_heure')
    def onchange_is_duree_heure(self):
        for obj in self:
            obj.time_cycle_manual=60*obj.is_duree_heure


    @api.onchange('time_cycle_manual')
    def onchange_time_cycle_manual(self):
        for obj in self:
            obj.is_duree_heure=obj.time_cycle_manual/60


class mrp_workcenter(models.Model):
    _inherit  = "mrp.workcenter"

    is_temps_ouverture_ids = fields.One2many("is.mrp.workcenter.temps.ouverture", "workcenter_id", "Temps d'ouverture")


    def calculer_charge_action(self):
        cr=self._cr
        for obj in self:
            for line in obj.is_temps_ouverture_ids:
                SQL="""
                    SELECT sum(hour)
                    FROM mrp_production_workcenter_line
                    WHERE 
                        workcenter_id="""+str(obj.id)+""" and 
                        is_date_debut=""""+str(line.date_ouverture)+"""" and
                        state not in ("cancel","done")
                """
                cr.execute(SQL)
                temps_planifie = 0.0
                for row in cr.fetchall():
                    temps_planifie = row[0] or 0.0
                ecart = line.temps_ouverture - temps_planifie
                charge = 100
                if line.temps_ouverture>0:
                    charge = 100*(temps_planifie / line.temps_ouverture)
                line.temps_planifie = temps_planifie
                line.ecart          = ecart
                line.charge         = charge


class is_mrp_workcenter_temps_ouverture(models.Model):
    _name = "is.mrp.workcenter.temps.ouverture"
    _description="is_mrp_workcenter_temps_ouverture"
    _order = "workcenter_id,date_ouverture"

    @api.depends("date_ouverture")
    def _compute_date_ouverture(self):
        for obj in self:
            if obj.date_ouverture:
                date_ouverture = datetime.strptime(obj.date_ouverture, "%Y-%m-%d")
                obj.semaine_ouverture = date_ouverture.strftime("%Y")+"-S"+date_ouverture.strftime("%V")
                obj.mois_ouverture    = date_ouverture.strftime("%Y-%m")


    workcenter_id     = fields.Many2one("mrp.workcenter", "Poste de charge", required=True, ondelete="cascade", readonly=True)
    date_ouverture    = fields.Date("Date d'ouverture"      , required=True, index=True)
    semaine_ouverture = fields.Char("Semaine d'ouverture", compute="_compute_date_ouverture", readonly=True, store=True)
    mois_ouverture    = fields.Char("Mois d'ouverture"   , compute="_compute_date_ouverture", readonly=True, store=True)
    temps_ouverture   = fields.Float("Temps d'ouverture (H)", required=True)
    temps_planifie    = fields.Float("Temps planifié (H)", readonly=True)
    ecart             = fields.Float("Ecart (H)"         , readonly=True)
    charge            = fields.Float("Charge (%)"        , readonly=True)
    operateur_ids     = fields.Many2many("hr.employee", "is_mrp_workcenter_temps_ouverture_operateur_rel", "date_id", "employe_id", "Opérateurs")


    def acceder_ordres_travaux(self):
        for obj in self:
            return {
                "name": "travaux "+obj.workcenter_id.name+" "+str(obj.date_ouverture),
                "view_mode": "tree,form",
                "view_type": "form",
                "res_model": "mrp.production.workcenter.line",
                "domain": [
                    ("workcenter_id","=",obj.workcenter_id.id),
                    ("is_date_debut","=",obj.date_ouverture),
                    ("state","not in", ["cancel","done"]),
                ],
                "type": "ir.actions.act_window",
            }








