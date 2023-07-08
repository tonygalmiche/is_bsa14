# -*- coding: utf-8 -*-
from odoo import models,fields,api
from datetime import datetime, timedelta
from pytz import timezone
import pandas as pd
import numpy as np
from math import ceil
from pprint import pprint
import logging
_logger = logging.getLogger(__name__)


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


    def calculer_dispo_ressource(self, date_debut, date_fin):
        debut = datetime.now() 
        cr=self._cr
 
        # Calcul sur nb_jours de la disponibilité des employées toutes les 30mn
        nb_jours = (date_fin-date_debut).days

        tz = timezone('Europe/Paris')
        now = datetime.now()
        heure_now = now.replace(microsecond=0).replace(second=0).replace(minute=0).replace(hour=0)

        heure = datetime.min.time() 
        heure_debut = datetime.combine(date_debut, heure) # Transforme un date en datetime
        heure_fin   = heure_debut + timedelta(days=nb_jours)

        _logger.info("calculer_dispo_ressource : Début du traitement entre %s et %s (%s jours)"%(heure_debut, heure_fin, nb_jours))

        #Suppression des lignes passées et des lignes dans l'interval à recalculer
        sql="delete from is_dispo_ressource where heure_debut<%s or (heure_debut>=%s and heure_debut<=%s)"
        cr.execute(sql, [heure_now, heure_debut, heure_fin])

        _logger.info("calculer_dispo_ressource : delete is_dispo_ressource en %sms"%duree(debut))

        listd=[]
        for i in range(0, 24*nb_jours*2):
            offset    = tz.localize(heure_debut).utcoffset().total_seconds()/3600
            heure_fin = heure_debut + timedelta(minutes=30)
            weekday   = str(heure_debut.weekday())
            hour      = heure_debut.hour
            minute    = heure_debut.minute
            heure     = hour+offset+minute/60
            week      = heure_debut.isocalendar().week
            modulo    = str(week%2) # 0=pair, 1=impair
            employes = self.env['hr.employee'].search([
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
        _logger.info("calculer_dispo_ressource : Fin du traitement en %sms"%duree(debut))

        #listd : Disponibilité des ressources par employé et par heure
        #self.calculer_charge_action()


    @api.model
    def calculer_dispo_ressource_ir_cron(self):
        date_debut = datetime.now()
        date_fin   = date_debut + timedelta(days=366)

        print(date_debut, date_fin)

        self.env['is.dispo.ressource'].calculer_dispo_ressource(date_debut, date_fin)
        return True



    def calculer_charge_action(self):
        self.calculer_plage_dispo_ressource()




    def calculer_plage_dispo_ressource(self):
        "Calculer les plages de disponibilités des ressources"

        #** Calcul des plages pour les employés *******************************
        employes = self.env['hr.employee'].search([])
        for employe in employes:
            employe_id = employe.id

            #** Suppression des lignes ****************************************
            cr=self._cr
            sql="delete from is_dispo_ressource_plage where employe_id=%s"
            cr.execute(sql,[employe_id])
            #**********************************************************************

            #** Disponibilité des ressources **************************************
            debut = datetime.now() 
            dispos = [{
                "heure_debut"  : line.heure_debut,
                "heure_fin"    : line.heure_fin,
                "employe"      : line.employe_id.name,
                "employe_id"   : str(line.employe_id.id),
                "workcenter_id": line.workcenter_id.id,
                "disponibilite": line.disponibilite,
            } for line in self.env['is.dispo.ressource'].search([("employe_id","=", employe_id)], order="heure_debut")]
            #_logger.info("Création de la liste 'dispos' en %sms"%duree(debut))
            #******************************************************************

            if len(dispos)>0:
                _logger.info("Calcul des plages de disponibilité pour %s"%employe.name)

                #** Convertir la liste en DataFrame ***************************
                debut = datetime.now() 
                pd.set_option('display.max_rows', 7,) # Il est inutile de metttre plus de 10, car cela n'est pas pris en compte
                df_dispos = pd.DataFrame(dispos)
                #_logger.info("Convertion de la liste 'dispos' en DataFrame en %sms"%duree(debut))
                #print(df_dispos)
                #**************************************************************

                #** Extraire les lignes avec une disponibilité à 0 ************
                df_open = df_dispos[df_dispos["disponibilite"]>0]
                #print(df_open)
                #**************************************************************

                # Ajout d'info sur les lignes i+1 et i-1
                # Ajouter une colomne qui a pour info le "start" de la prochaine ligne et le "end" de la ligne d'avant, afin de savoir si c'est une fermeture "nouvelle" ou bien une qui s'arrête ou encore une qui continue son petit bonhomme de chemin.
                # `shift` permet d'accéder aux lignes d'avant/après. Vu sur [StackOverflow](https://stackoverflow.com/questions/30673209/pandas-compare-next-row)
                df_aug = df_open.copy()
                df_aug["heure_debut_next"] = df_open["heure_debut"].shift(-1) # Heure de début de la ligne suivante
                df_aug["heure_fin_prev"]   = df_open["heure_fin"].shift(1)    # Heure de fin de la ligne précédente
                #print(df_aug)

                #Pour chaque ligne, vérifier si on est dans le cas d'un début de fermeture ou la fin d'une fermeture (il y a le cas où on est au milieu d'une fermeture qui est le cas dont on veut justement se débarasser)
                df_aug["end_open"] = (df_aug["heure_debut_next"] != df_aug["heure_fin"])
                df_aug["start_open"] = (df_aug["heure_fin_prev"] != df_aug["heure_debut"])
                #print(df_aug)

                ### Extraire toutes les dates de début
                df_start = df_aug[df_aug["start_open"] == True]["heure_debut"]
                #print(df_start)

                ### Extraire toutes les dates de fin
                df_end = df_aug[df_aug["end_open"] == True]["heure_fin"]
                #print(df_end)

                #Combiner le tout (et le tout dans le même format d'origine)
                N = len(df_start)
                res = [{
                    "start" : df_start.iloc[i],
                    "end" : df_end.iloc[i],
                } for i in range(N)]
                for line in res:
                    vals={
                        "employe_id" : employe_id,
                        "heure_debut": line["start"],
                        "heure_fin"  : line["end"],
                    }
                    id=self.env['is.dispo.ressource.plage'].create(vals)




        #** Calcul des plages pour les postes de charges **********************
        workcenters = self.env['mrp.workcenter'].search([])
        for workcenter in workcenters:
            #** Suppression des lignes ****************************************
            cr=self._cr
            sql="delete from is_dispo_ressource_plage where workcenter_id=%s"
            cr.execute(sql,[workcenter.id])

            #** Disponibilité des ressources **************************************
            dispos = [{
                "heure_debut"  : line.heure_debut,
                "heure_fin"    : line.heure_fin,
                "workcenter_id": line.workcenter_id.id,
                "disponibilite": line.disponibilite,
            } for line in self.env['is.dispo.ressource'].search([("workcenter_id","=", workcenter.id)], order="heure_debut")]
            #******************************************************************

            if len(dispos)>0:
                df_dispos = pd.DataFrame(dispos)                              # Convertir la liste en DataFrame
                df_open = df_dispos[df_dispos["disponibilite"]>0]             # Extraire les lignes avec une disponibilité >0
                df_aug = df_open.copy()
                df_aug["heure_debut_next"] = df_open["heure_debut"].shift(-1) # Heure de début de la ligne suivante
                df_aug["heure_fin_prev"]   = df_open["heure_fin"].shift(1)    # Heure de fin de la ligne précédente
                #Pour chaque ligne, vérifier si on est dans le cas d'un début de fermeture ou la fin d'une fermeture
                df_aug["end_open"] = (df_aug["heure_debut_next"] != df_aug["heure_fin"])
                df_aug["start_open"] = (df_aug["heure_fin_prev"] != df_aug["heure_debut"])
                df_start = df_aug[df_aug["start_open"] == True]["heure_debut"] # Extraire toutes les dates de début
                df_end   = df_aug[df_aug["end_open"] == True]["heure_fin"]     # Extraire toutes les dates de fin
                #Combiner le tout et création des plages
                N = len(df_start)
                res = [{
                    "start" : df_start.iloc[i],
                    "end" : df_end.iloc[i],
                } for i in range(N)]
                for line in res:
                    vals={
                        "workcenter_id" : workcenter.id,
                        "heure_debut": line["start"],
                        "heure_fin"  : line["end"],
                    }
                    id=self.env['is.dispo.ressource.plage'].create(vals)










    def calculer_charge_action2(self):
        debut = datetime.now() 

        #** Disponibilité des ressources **************************************
        listd = [{
            "heure_debut"  : line.heure_debut,
            "heure_fin"    : line.heure_fin,
            "employe"      : line.employe_id.name,
            "employe_id"   : str(line.employe_id.id),
            "workcenter_id": line.workcenter_id.id,
            "disponibilite": line.disponibilite,
        } for line in self.env['is.dispo.ressource'].search([])]
        _logger.info("Création de listd en %sms"%duree(debut))

        pd.set_option('display.max_rows', 7,) # Il est inutile de metttre plus de 10, car cela n'est pas pris en compte
        df_pers = pd.DataFrame(listd)

        print("#### Affichage de listd au format DataFrame de Pandas = Table is_dispo_ressource ####")
        print(df_pers)
        #**********************************************************************


        #** Liste des taches **************************************************
        workcenter_id = 15 # Soudage manuel
        ordre_id = 82 # 14 taches

        lines=self.env['is.ordre.travail.line'].search([('ordre_id','=',ordre_id)],order="sequence")
        taches=[]
        num=1
        for line in lines:
            taches.append({
                "num"         : num,
                "tache_id"    : line.id,
                "sequence"    : line.sequence,
                "date_prevue" : line.date_prevue,
                "ordre_id"    : line.ordre_id.id,
                "ordre"       : line.ordre_id.name,
                "production"  : line.production_id.name,
                "reste"       : int(line.reste),
                "recouvrement": 0 # 0.5 => la tache suivante commence à 50% de la tache en cours
            })
            num+=1
        df_taches = pd.DataFrame(taches)
        print("#### Liste des taches ####")
        print(df_taches)

        # #### Liste des taches ####
        #     num  sequence         date_prevue  ordre_id  tache production  reste
        # 0     1       100 2023-04-24 05:19:20        82  00082   OFA02165    0.0
        # 1     2       101 2023-04-24 05:19:20        82  00082   OFA02165  168.0
        # 2     3       102 2023-04-24 05:19:20        82  00082   OFA02165  258.0
        # ..  ...       ...                 ...       ...    ...        ...    ...
        # 11   12       111 2023-04-24 05:19:20        82  00082   OFA02165    8.0
        # 12   13       112 2023-04-24 05:19:20        82  00082   OFA02165    4.0
        # 13   14       113 2023-04-24 05:19:20        82  00082   OFA02165    2.0
        #**********************************************************************

        # Ajouter une colonne 'taches'
        df_pers["taches"] = [[] for _ in range(len(df_pers))]
        print(df_pers)


        # Ne garder que les lignes qui concernent le workcenter avec des gens qui sont vraiment là
        #df_bureau = df_pers[(df_pers["workcenter_id"] == workcenter_id) & (df_pers["disponibilite"] >0)]
        df_bureau = df_pers[(df_pers["disponibilite"]>0)]
        print(df_bureau)


        # Ajouter une colonne 'employe_ids' pour la liste des employes
        #df_bureau["employe_ids"] = ""
        #df_bureau["employe_ids"] = ["" for _ in range(len(df_bureau))]
        #df_bureau.insert(1, 'employe_ids', '')
        #df_bureau = df_bureau.assign(employe_ids='')
        #print(df_bureau)


        # Faire un groupby magique
        # Voir doc sur `agg`=> https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.DataFrameGroupBy.aggregate.html
        aggr_bureau = df_bureau.groupby(["heure_debut", "heure_fin"], as_index=False)[["employe", "employe_id", "taches"]].agg({
            "employe"   : lambda x: ', '.join(x), # On joint les noms des employés
            "employe_id": lambda x: ','.join(x),  # On joint les noms des employés
            "taches"    : lambda x: [],           # On met la valeur [] partout
        })
        print(aggr_bureau)



        ## Commencer à calculer les horaires des tâches (Le gros du travail)

        # Quand la dernière tache a commencé / quand on doit commencer la courante
        T_start = 0
        # Quand la dernière tache a fini / quand on doit finir la courante
        T_end = 0
        # Combien de temps a duré la dernière tache
        Temps_prev = 0

        # Fonction à utiliser dans le 'apply'
        def f_apply(l, x):
            # Append la nouvelle tache à la liste actuelle des taches
            l.append(x)

        # Connaître l'index de la colonne 'Taches' pour pouvoir utiliser .iloc
        col_taches = aggr_bureau.columns.get_loc("taches")
        #print("col_taches=",col_taches)


        res={}

        for i, t in enumerate(taches):

            tache_id = t["tache_id"]
            res[tache_id] = tache_id

            #print(t)

            #print(t)
            
            # Savoir quand commencer/finir la nouvelle tache
            # En fonction du précédent T_end en Temps et du recouvrement actuel
            T_start = T_end - ceil(t["recouvrement"]*Temps_prev)
            T_end = T_start+t["reste"]
            
            #print(T_start,T_end,t["recouvrement"],t["reste"] )
            
            # Mettre à jour la Dataframe avec la Tache courante
            



            # -------------  Version naive avec une boucle -------------
            #for i in range(T_start, T_end):
            #    print(i,col_taches,aggr_bureau.iloc[i, col_taches])
            #    # syntaxe : .iloc[row_index, column_index]
            #    aggr_bureau.iloc[i, col_taches].append(t["tache"])
            
            # -------------  Version efficace avec un apply -------------
            # .apply() va appliquer une function à chaque ligne
            # .apply() prend en premier paramètre la valeur de ligne actuelle
            aggr_bureau.iloc[T_start: T_end, col_taches].apply(lambda l: f_apply(l, t["tache_id"]) )
            
            # Preparer la prochaine iteration 
            Temps_prev = t["reste"]


            date_debut = aggr_bureau["heure_debut"].iloc[T_start]
            date_fin   = aggr_bureau["heure_fin"].iloc[T_end-1]
            print(t["num"],t["tache_id"],date_debut, date_fin)



            
        print(aggr_bureau)

        ### Ajouter le nombre d'employés par tranche horaire
        aggr_bureau["nb_employes"] = aggr_bureau["employe_id"].str.split(",").str.len()


        ### Ajouter le nombre de tache par tranche horaire
        aggr_bureau["nb_taches"] = aggr_bureau["taches"].str.len()
        print(aggr_bureau)




        # Ajouter une colonne "nombre de la semaine" depuis la date
        aggr_bureau["semaine"] = aggr_bureau['heure_debut'].dt.isocalendar().week
        print(aggr_bureau)



        # Test de filtre (sans intéret pour la suite)
        print("### df_test ###")
        df_test = aggr_bureau[(aggr_bureau["nb_taches"]>0) & (aggr_bureau["nb_employes"] >0)]
        print(df_test)




        # ## Ajouter le nombre d'employés
        # aggr_bureau["nb_employes"] = aggr_bureau["employe"].str.len()
        # print(aggr_bureau)


        # #Test de filtre (sans intéret pour la suite)
        # #df_test = aggr_bureau[(aggr_bureau["nb_employes"]>1)]
        # #print(df_test)


        print(res)









        # _logger.info("Convertion listd en DateFrame en %sms"%duree(debut))

        # employes=self.env['hr.employee'].search([
        #     ('is_workcenter_id', '!=', False),
        #     #('id', '=', 9),
        # ])
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

        #     #print("#### Liste des plages fermées pour mettre dans gantt pour ce poste de charge ###")
        #     #for line in res_plus_efficace:
        #     #   print(workcenter_id,line["start"].to_pydatetime(),  line["end"].to_pydatetime())

        # _logger.info("Traitement du DateFrame en %sms"%duree(debut))






class is_dispo_ressource_plage(models.Model):
    _name='is.dispo.ressource.plage'
    _description='Plages de disponibilité des employés et des postes de charges pour vue agenda'
    _order='heure_debut'
    _rec_name = 'heure_debut'

    heure_debut   = fields.Datetime('Heure début'                      , required=True, index=True)
    heure_fin     = fields.Datetime('Heure fin'                        , required=True)
    employe_id    = fields.Many2one('hr.employee', 'Employé'           , required=False, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Poste de charge', required=False, index=True)


class is_calcul_dispo_ressource_wizard(models.TransientModel):
    _name = "is.calcul.dispo.ressource.wizard"
    _description = "Calcul de la dispo des ressurces de date à date"

    date_debut = fields.Date('Date de début', default=lambda *a: datetime.now(), required=True)
    date_fin   = fields.Date('Date de fin'  , default=lambda *a: datetime.now() + timedelta(days=7), required=True)

    def calcul_action(self):
        for obj in self:
            self.env['is.dispo.ressource'].calculer_dispo_ressource(obj.date_debut, obj.date_fin)

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
