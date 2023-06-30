# -*- coding: utf-8 -*-
from odoo import models,fields
from datetime import datetime, timedelta
from pytz import timezone
#import pandas as pd
#import numpy as np
#from pprint import pprint

def duree(debut):
    dt = datetime.now() - debut
    ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
    ms=int(ms)
    return ms


class hr_employee(models.Model):
    _inherit = "hr.employee"

    is_workcenter_id  = fields.Many2one('mrp.workcenter', 'Poste de charge affecté', help="Utilisé pour le calcul de la charge par employé")
    is_workcenter_ids = fields.Many2many('mrp.workcenter', 'hr_employee_mrp_workcenter_rel', 'employe_id', 'workcenter_id', 'Postes de charges autorisés')

    is_matricule = fields.Char('Matricule', help='N° de matricule du logiciel de paye', required=False)
    is_categorie = fields.Selection([
        ("2x8" , "Équipe en 2x8"), 
        ("2x8r", "Équipe en 2x8 avec recouvrement"), 
        ("nuit", "Équipe de nuit"),
        ("3x8" , "en 3x8"),
        ("jour", "Personnel de journée"),
    ], "Catégorie de personnel", required=False)
    is_interimaire    = fields.Boolean('Intérimaire',  help="Cocher pour indiquer que c'est un intérimaire")
    is_badge_count    = fields.Integer(string='# Badges'   , compute="_badge_count")
    is_pointage_count = fields.Integer(string='# Pointages', compute="_pointage_count")
    is_jour1 = fields.Float('Lundi')
    is_jour2 = fields.Float('Mardi')
    is_jour3 = fields.Float('Mercredi')
    is_jour4 = fields.Float('Jeudi')
    is_jour5 = fields.Float('Vendredi')
    is_jour6 = fields.Float('Samedi')
    is_jour7 = fields.Float('Dimanche')

    is_observation = fields.Text('Observations')


    def _badge_count(self):
        for obj in self:
            obj.is_badge_count = 0


    def _pointage_count(self):
        for obj in self:
            obj.is_pointage_count = 0


    def action_view_badge(self):
        for obj in self:
            print(obj)


class is_motif_absence(models.Model):
    _name='is.motif.absence'
    _description="Motifs d'absenses des employés"
    _order='name'

    name = fields.Char("Motif", required=True, index=True)


class is_absence(models.Model):
    _name='is.absence'
    _description='Absenses des employés'
    _order='date_debut desc'
    _rec_name = 'employe_id'


    employe_id  = fields.Many2one('hr.employee', 'Employé' , required=True)
    motif_id    = fields.Many2one('is.motif.absence', 'Motif', required=True)
    date_debut  = fields.Datetime('Date début', required=True)
    date_fin    = fields.Datetime('Date fin', required=True)
    commentaire = fields.Char("Commentaire")


class is_dispo_ressource(models.Model):
    _name='is.dispo.ressource'
    _description='Disponibilité des employés et des postes de charges par heure'
    _order='heure_debut desc'
    _rec_name = 'heure_debut'

    heure_debut   = fields.Datetime('Heure début'                      , required=True, index=True)
    heure_fin     = fields.Datetime('Heure fin'                        , required=True)
    employe_id    = fields.Many2one('hr.employee', 'Employé'           , required=True, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Poste de charge', required=True, index=True)
    disponibilite = fields.Float('Disponibilité (H)')



    #TODO : 
    # - Ajouter des entrées dans "Regrouper par"


    def recalculer_dispo_ressource_action(self):
        debut = datetime.now() 

        cr=self._cr
        sql="delete from is_dispo_ressource"
        cr.execute(sql)

        print("delete is_dispo_ressource en %sms"%duree(debut))

        debut = datetime.now() 


        # Calcul sur nb_jours de la disponibilité des employées toutes les 30mn
        #nb_jours = 5
        nb_jours = 31

        tz = timezone('Europe/Paris')
        now = datetime.now()
        heure_debut = now.replace(microsecond=0).replace(second=0).replace(minute=0)

        listd=[]
        for i in range(0, 24*nb_jours*2):
            offset = tz.localize(heure_debut).utcoffset().total_seconds()/3600
            heure_fin = heure_debut + timedelta(minutes=30)
            weekday = str(heure_debut.weekday())
            hour    = heure_debut.hour
            minute  = heure_debut.minute
            heure   = hour+offset+minute/60
            week    = heure_debut.isocalendar().week
            modulo  = str(week%2) # 0=pair, 1=impair
            employes=self.env['hr.employee'].search([
                ('is_workcenter_id', '!=', False),
                #('id', '=', 9),
            ])


            for employe in employes:
                disponibilite = 0
                vals={
                    "heure_debut"  : heure_debut,
                    "heure_fin"    : heure_fin,
                    "employe_id"   : employe.id,
                    "workcenter_id": employe.is_workcenter_id.id,
                    "disponibilite": disponibilite,
                }
                res=self.env['is.dispo.ressource'].create(vals)
                for line in employe.resource_calendar_id.attendance_ids:
                    if not line.display_type:
                        if weekday==line.dayofweek:
                            if line.week_type==False or line.week_type==modulo:
                                if heure>=line.hour_from and heure<line.hour_to:
                                    #** Recherche des congés ******************
                                    conges=self.env['resource.calendar.leaves'].search([
                                        ('date_from', '<=', heure_debut),
                                        ('date_to', '>', heure_debut),
                                    ])
                                    #******************************************
                                    if len(conges)==0:
                                        #** Recherche des absences ************
                                        absences=self.env['is.absence'].search([
                                            ('employe_id', '=', employe.id),
                                            ('date_debut', '<=', heure_debut),
                                            ('date_fin', '>', heure_debut),
                                        ])
                                        #**************************************
                                        if len(absences)==0:
                                            disponibilite = 0.5
                                            res.disponibilite = disponibilite
                vals["disponibilite"] = disponibilite
                listd.append(vals)

            heure_debut = heure_debut + timedelta(minutes=30)

        # print("Création et enregistement delistd en %sms"%duree(debut))

        # debut = datetime.now() 

        # pd.set_option('display.max_rows', 7,) # Il est inutile de metttre plus de 10, car cela n'est pas pris en compte
        # df = pd.DataFrame(listd)

        # for employe in employes:
        #     print("####",employe.name, employe.is_workcenter_id.name, employe.is_workcenter_id.id)

        #     df_workcenter = df[df["workcenter_id"] == employe.is_workcenter_id.id]
        #     print(df_workcenter)


        # print(df.workcenter_id.unique())
        # for workcenter_id in df.workcenter_id.unique():
        #     print("#### workcenter_id=",workcenter_id)

        #     df_workcenter = df[df["workcenter_id"] == workcenter_id]
        #     print(df_workcenter)

        #     df_workcenter_groupby = df_workcenter.groupby(["heure_debut","heure_fin","workcenter_id"], as_index=False)[["disponibilite"]].sum()

        #     #Juste pour l'exemple (sans utilité par la suite), ajout d'une colonne 'week' à la DataFrame
        #     df_workcenter_groupby["week"] = df_workcenter_groupby["heure_debut"].dt.isocalendar().week
        #     print(df_workcenter_groupby)

        #     #context pour afficher toutes les lignes
        #     #with pd.option_context('display.max_rows', None,):
        #     #   print(df_workcenter_groupby)

        #     # Extraire les ligne avec "disponibilite=0"
        #     df_closed = df_workcenter_groupby[df_workcenter_groupby["disponibilite"] == 0]
        #     print(df_closed)


        #     # next_closed = heure_debut de la ligne précédente, prev_closed = heure_fin de la ligne suivant 
        #     df_aug = df_closed.copy()
        #     df_aug["next_closed"] = df_closed["heure_debut"].shift(-1)
        #     df_aug["prev_closed"] = df_closed["heure_fin"].shift(1)
        #     print(df_aug)

        #     df_aug["end_closing"]   = (df_aug["next_closed"] != df_aug["heure_fin"])
        #     df_aug["start_closing"] = (df_aug["prev_closed"] != df_aug["heure_debut"])
        #     print(df_aug)


        #     # Extraire toutes les dates de début
        #     df_start = df_aug[df_aug["start_closing"] == True]["heure_debut"]
        #     print(df_start)

        #     # Extraire toutes les dates de fin
        #     df_end   = df_aug[df_aug["end_closing"] == True]["heure_fin"]
        #     print(df_end)

        #     # Combiner le tout (et le tout dans le même format d'origine)
        #     res_plus_efficace = [{
        #         "start" : dstart,
        #         "end" : dend,
        #     } for (dstart, dend) in zip(df_start, df_end)]

        #     print("#### Liste des plages fermées pour mettre dans gantt pour ce poste de charge ###")
        #     for line in res_plus_efficace:
        #        print(workcenter_id,line["start"].to_pydatetime(),  line["end"].to_pydatetime())

        # print("Traitement du DateFrame en %sms"%duree(debut))



        return {
            "name": "Disponibilité des employés",
            "view_mode": "pivot,graph,tree,form",
            "res_model": "is.dispo.ressource",
             "type": "ir.actions.act_window",
        }







#    def utc_offset(self):
#         now = datetime.now()
#         tz = pytz.timezone('Europe/Paris')
#         offset = tz.localize(now).utcoffset()
#         return offset
