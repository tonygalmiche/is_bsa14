# -*- coding: utf-8 -*-
from odoo import models,fields,api,tools, SUPERUSER_ID
from datetime import datetime, date, timedelta
from odoo.exceptions import Warning
import pytz
from pytz import timezone




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
                    'time_cycle_manual': line.duree*60,
                    'is_duree_heure'   : line.duree,
                    'is_recouvrement'  : line.recouvrement,
                    'is_tps_apres'     : line.tps_apres,
                    'is_libre'         : line.libre,
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

    is_offset       = fields.Integer("Offset (jour)", help="Offset en jours par rapport à l'opération précédente pour le calcul du planning")
    is_duree_heure  = fields.Float("Durée (Heures)")
    is_recouvrement = fields.Integer("Recouvrement (%)", required=True, default=0, help="0%: Cette ligne commence à la fin de la ligne précédente\n50%: Cette ligne commence quand la ligne précédente est terminée à 50%\n100%: Cette ligne commence en même temps que la ligne précédente" )
    is_tps_apres    = fields.Float("Tps passage après (HH:MN)", default=0, help="Temps d'attente après cette opération avant de commencer la suivante (en heures ouvrées)")
    is_libre        = fields.Boolean("Libre", default=False, help="Permet de démarrer le suivi du temps sur cette opération à tout moment")


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

    is_temps_ouverture_ids    = fields.One2many("is.mrp.workcenter.temps.ouverture", "workcenter_id", "Temps d'ouverture")
    is_ordre_travail_line_ids = fields.One2many('is.ordre.travail.line', 'workcenter_id', 'Ordres de travail')
    is_fermeture_ids          = fields.One2many('is.mrp.workcenter.fermeture', 'workcenter_id', 'Fermetures')
    is_planning               = fields.Char("Planning")


    # def calculer_charge_action(self):
    #     cr=self._cr
    #     for obj in self:
    #         for line in obj.is_temps_ouverture_ids:
    #             SQL="""
    #                 SELECT sum(hour)
    #                 FROM mrp_production_workcenter_line
    #                 WHERE 
    #                     workcenter_id="""+str(obj.id)+""" and 
    #                     is_date_debut=""""+str(line.date_ouverture)+"""" and
    #                     state not in ("cancel","done")
    #             """
    #             cr.execute(SQL)
    #             temps_planifie = 0.0
    #             for row in cr.fetchall():
    #                 temps_planifie = row[0] or 0.0
    #             ecart = line.temps_ouverture - temps_planifie
    #             charge = 100
    #             if line.temps_ouverture>0:
    #                 charge = 100*(temps_planifie / line.temps_ouverture)
    #             line.temps_planifie = temps_planifie
    #             line.ecart          = ecart
    #             line.charge         = charge



    def clear_fermeture_action(self):
        for obj in self:
            obj.is_fermeture_ids.unlink()


    def utc_offset(self):
        now = datetime.now()
        tz = pytz.timezone('Europe/Paris')
        offset = tz.localize(now).utcoffset()
        return offset


    def create_fermeture(self, workcenter_id,date_debut,date_fin,motif):
        vals={
            "workcenter_id": workcenter_id,
            "date_debut"   : date_debut,
            "date_fin"     : date_fin,
            "motif"        : motif,
        }
        self.env['is.mrp.workcenter.fermeture'].create(vals)


    def fermeture_jour(self, jour, motif):
        for obj in self:
            now = datetime.now()
            x = now.strftime('%Y-%m-%d')+" 00:00:00"
            x = datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
            offset = self.utc_offset()
            date_debut = x - offset
            for x in range(0, 100):
                if date_debut.isoweekday()==jour: 
                    date_fin = date_debut + timedelta(days=1)
                    self.create_fermeture(obj.id,date_debut,date_fin,motif)
                date_debut = date_debut + timedelta(days=1)


    def fermeture_equipe(self, heure_debut, motif):
        for obj in self:
            now = datetime.now()
            x = now.strftime('%Y-%m-%d')+" 00:00:00"
            x = datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
            offset = self.utc_offset()
            date_debut = x - offset + timedelta(hours=heure_debut)
            for x in range(0, 30):
                date_fin = date_debut + timedelta(hours=8)
                self.create_fermeture(obj.id,date_debut,date_fin,motif)
                date_debut = date_debut + timedelta(days=1)



    def fermeture_e1_action(self):
        for obj in self:
            self.fermeture_equipe(5,"E1")


    def fermeture_e2_action(self):
        for obj in self:
            self.fermeture_equipe(13,"E2")


    def fermeture_e3_action(self):
        for obj in self:
            self.fermeture_equipe(-3,"E3")


    def fermeture_samedi_action(self):
        for obj in self:
            self.fermeture_jour(5, "Samedi")


    def fermeture_dimanche_action(self):
        for obj in self:
            self.fermeture_jour(6, "Dimanche")



                        # <button name="maj_planning_2J_action"  string="2J"  type="object" title="Mise à jour du planning sur 2 jours"/>
                        # <button name="maj_planning_5J_action"  string="5J"  type="object" title="Mise à jour du planning sur 5 jours"/>
                        # <button name="maj_planning_10J_action" string="10J" type="object" title="Mise à jour du planning sur 10 jours"/>
                        # <button name="maj_planning_20J_action" string="20J" type="object" title="Mise à jour du planning sur 20 jours"/>

    def maj_planning_2J_action(self):
        for obj in self:
            obj.maj_planning_action(2)

    def maj_planning_5J_action(self):
        for obj in self:
            obj.maj_planning_action(5)

    def maj_planning_10J_action(self):
        for obj in self:
            obj.maj_planning_action(10)

    def maj_planning_20J_action(self):
        for obj in self:
            obj.maj_planning_action(20)



    def maj_planning_action(self,nb_jour):
        for obj in self:
            self.maj_heure_debut_fin()
            height=44
            width_coef = 100
            color=html=""
            max_width=1760
            width_jour = max_width / nb_jour
            now = datetime.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            top=50
            left=0
            width_heure = max_width / nb_jour / 24
            offset = self.utc_offset()
            for line in obj.is_ordre_travail_line_ids:

                
                if left==0:
                    decal_heure = (line.heure_debut - midnight).total_seconds()/3600
                    left = (decal_heure + offset.seconds/3600) * width_heure



                #** Ordre de travail ******************************************
                if color=="orange":
                    color="LightGreen"
                else:
                    color="orange"
                color="AliceBlue"
                font_color="black"
                #width=line.duree_totale*width_heure

                duree = (line.heure_fin-line.heure_debut).total_seconds()/3600

                width = width_heure*duree


                name=line.name+"<br />"+line.product_id.name_get()[0][1]
                title="Durée hors fermeture: %sH, Durée avec fermeture: %sH Début: %s, Fin: %s"%(
                    round(line.duree_totale,1),
                    round(duree,1),
                    (line.heure_debut+offset).strftime("%d/%m/%Y %H:%M"),
                    (line.heure_fin+offset).strftime("%d/%m/%Y %H:%M")
                )
                html+="""
                    <div style="
                        background-color:%s;
                        width:%spx;
                        height:%spx;
                        position:absolute;left:%spx;top:%spx;
                        border-top: 1px solid gray;
                        border-bottom: 1px solid gray;
                        z-index: 3;
                    "/>
                """%(color,width,height,left,top)

                #** Informations sur ordre de travail *************************
                html+="""
                    <div 
                        title="%s"
                        style="
                            height:%spx;
                            position:absolute;left:%spx;top:%spx;
                            font-weight:bold;
                            color:%s;
                            z-index: 3;
                            white-space: nowrap;
                        ">
                        %s
                    </div>
                """%(title,height,(left+2),top,font_color,name)
                left+=width
                top+=height
                if left>1600:
                    break
            height = top
            top=left=0
            jour=now
            for x in range(0,nb_jour):
                #** Heures ****************************************************
                div_jour = 12
                if nb_jour>5:
                    div_jour=3
                for h in range(0,div_jour):
                    width_heure=width_jour/div_jour
                    name=int(h*24/div_jour)
                    html+="""
                        <span 
                            style="
                                width:%spx;
                                height:%spx;
                                position:absolute;left:%spx;top:%spx;
                                font-weight:bold;
                                color:black;
                                background-color:white;
                                border-right: 1px dotted #DEE2E6;
                                text-align:left;
                                padding-left:4px;
                                z-index: 1;
                            ">
                            %s
                        </span>
                    """%(width_heure,height-20,left+h*width_heure,top+20,name)

                #** Jours *****************************************************
                title="Jour"
                name=jour.strftime("%d/%m")
                html+="""
                    <span 
                        title="%s"
                        style="
                            width:%spx;
                            height:%spx;
                            position:absolute;left:%spx;top:%spx;
                            font-weight:bold;
                            color:black;
                            border: 1px solid #DEE2E6;
                            text-align:center;
                            z-index: 1;
                          ">
                        %s
                    </span>
                """%(title,width_jour,height,left,top,name)
                left+=width_jour
                jour = jour + timedelta(days=1)
            html+='<div style="height:%spx"/>'%(height-20)


            #** Heures de fermetures ******************************************

            now = datetime.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            limit = midnight + timedelta(days=nb_jour)
            for line in obj.is_fermeture_ids:
                top=40
                if line.date_debut>=midnight and line.date_debut<=limit:
                    x=line.date_debut-midnight
                    left=width_jour*(x.total_seconds()+offset.seconds)/3600/24
                    width = width_jour*(line.date_fin-line.date_debut).total_seconds()/3600/24
                    html+="""
                        <span 
                            style="
                                width:%spx;
                                height:%spx;
                                position:absolute;left:%spx;top:%spx;
                                background-color:#FCE5E7;
                                z-index: 2;
                              ">
                        </span>
                    """%(width,height-top,left,top)




            obj.is_planning=html


    def maj_heure_debut_fin(self):
        for obj in self:
            heure_debut = datetime.now()

            # ** Décale heure de début si fermeture ***************************
            test=True
            while test:
                filtre=[
                    ('workcenter_id', '=', obj.id),
                    ('date_debut', '<', heure_debut),
                    ('date_fin'  , '>', heure_debut),
                ]
                fermetures=self.env['is.mrp.workcenter.fermeture'].search(filtre)
                if len(fermetures)>0:
                    fermeture=fermetures[0]
                    heure_debut=fermeture.date_fin
                else:
                    test=False
            #******************************************************************

            for line in obj.is_ordre_travail_line_ids:
                line.heure_debut = heure_debut
                ts = datetime.timestamp(heure_debut) + line.reste*3600
                heure_fin = datetime.fromtimestamp(ts)
                duree = line.reste*3600
                tps_fermeture=0
                test=True
                while test:
                    ts = datetime.timestamp(heure_debut) + duree
                    heure_fin = datetime.fromtimestamp(ts)
                    filtre=[
                        ('workcenter_id', '=', obj.id),
                        ('date_debut', '>=', heure_debut),
                        ('date_debut', '<=', heure_fin),
                    ]
                    fermetures=self.env['is.mrp.workcenter.fermeture'].search(filtre)
                    if len(fermetures)>0:
                        fermeture=fermetures[0]
                        tps_fermeture+=(fermeture.date_fin-fermeture.date_debut).total_seconds()
                        delta = (fermeture.date_debut-heure_debut).total_seconds()
                        heure_debut=fermeture.date_fin
                        duree=duree-delta
                    else:
                        test=False
                line.heure_fin   = heure_fin
                heure_debut=heure_fin


    def tri_date_prevue_action(self):
        for obj in self:
            for line in obj.is_ordre_travail_line_ids:
                x = datetime.timestamp(line.date_prevue) - 1667900000 + line.sequence
                line.ordre_planning = x
            obj.maj_heure_debut_fin()


class is_mrp_workcenter_fermeture(models.Model):
    _name = "is.mrp.workcenter.fermeture"
    _description="Horaires de fermeture du poste de charge"
    _order = "date_debut"

    workcenter_id = fields.Many2one("mrp.workcenter", "Poste de charge", required=True, ondelete="cascade", readonly=True)
    date_debut    = fields.Datetime("Date début", required=True, index=True)
    date_fin      = fields.Datetime("Date fin"  , required=True, index=True)
    motif         = fields.Char("Motif")


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








