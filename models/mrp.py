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
    """Méthode surchargée pour ajouter le champ is_offset"""
    _inherit  = "mrp.bom"
    _order    = "product_tmpl_id"
    #_rec_name = "name"

    is_gamme_generique_id = fields.Many2one('is.gamme.generique', 'Gamme générique')


    def _bom_explode(self, cr, uid, bom, product, factor, properties=None, level=0, routing_id=False, previous_products=None, master_bom=None, context=None):
        result, result2 = super(mrp_bom, self)._bom_explode(cr, uid, bom, product, factor, properties=properties, level=level, routing_id=routing_id, previous_products=previous_products, master_bom=master_bom, context=context)
        uom_obj = self.pool.get("product.uom")
        routing_obj = self.pool.get("mrp.routing")
        master_bom = master_bom or bom
        def _factor(factor, product_efficiency, product_rounding):
            factor = factor / (product_efficiency or 1.0)
            factor = _common.ceiling(factor, product_rounding)
            if factor < product_rounding:
                factor = product_rounding
            return factor

        factor = _factor(factor, bom.product_efficiency, bom.product_rounding)
        result2 = []
        routing = (routing_id and routing_obj.browse(cr, uid, routing_id)) or bom.routing_id or False
        if routing:
            for wc_use in routing.workcenter_lines:
                wc = wc_use.workcenter_id
                d, m = divmod(factor, wc_use.workcenter_id.capacity_per_cycle)
                m=round(m,6) #TODO : Pour corriger un bug
                mult = (d + (m and 1.0 or 0.0))
                cycle = mult * wc_use.cycle_nbr
                result2.append({
                    "name": tools.ustr(wc_use.name) + " - " + tools.ustr(bom.product_tmpl_id.name_get()[0][1]),
                    "workcenter_id": wc.id,
                    "sequence": level + (wc_use.sequence or 0),
                    "is_offset": wc_use.is_offset,
                    "cycle": cycle,
                    "hour": float(wc_use.hour_nbr * mult + ((wc.time_start or 0.0) + (wc.time_stop or 0.0) + cycle * (wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
                })
        return result, result2


class mrp_routing_workcenter(models.Model):
    _inherit  = "mrp.routing.workcenter"

    is_offset = fields.Integer("Offset (jour)", help="Offset en jours par rapport à l'opération précédente pour le calcul du planning")


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








