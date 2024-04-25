# -*- coding: utf-8 -*-
#import cProfile
from odoo import models,fields,api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar
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
    is_detachement_ids      = fields.One2many('is.detachement', 'employe_id', 'Détachement')
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


class is_detachement(models.Model):
    _name="is.detachement"
    _description="L'employé est détaché"
    _ordre="date_debut"

    employe_id = fields.Many2one('hr.employee', 'Employé', required=True, ondelete='cascade')
    date_debut = fields.Date('Date début', required=True)
    date_fin   = fields.Date('Date fin', required=True)


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
    employe_id    = fields.Many2one('hr.employee', 'Employé'           , required=False, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Poste de charge', required=True, index=True)
    disponibilite = fields.Float('Disponibilité (H)', default=0)
    charge        = fields.Float('Charge (H)' , default=0, compute='_compute_charge', store=True)
    restant       = fields.Float('Restant (H)', default=0, compute='_compute_charge', store=True)
    taches_ids    = fields.Many2many('is.ordre.travail.line', 'is_dispo_ressource_ordre_travail_line_rel', 'dispo_id', 'tache_id', 'Tâches')
    description_taches = fields.Text('Description tâches', compute="_compute_description_taches", store=True)


    @api.depends('taches_ids')
    def _compute_description_taches(self):
        for obj in self:
            descriptions=[]
            for tache in obj.taches_ids:
                x="%s : %s : %s : %s"%(tache.production_id.name, tache.name, tache.production_id.is_sale_order_id.name, (tache.production_id.is_client_order_ref or '?'))
                descriptions.append(x)
            obj.description_taches = "\n".join(descriptions)


    @api.depends('disponibilite','taches_ids')
    def _compute_charge(self):
        for obj in self:
            obj.charge = len(obj.taches_ids)*0.5 # Une tache = 1 personne = 0.5H
            obj.restant=obj.disponibilite-obj.charge


    def search_absences(self,heure_debut, employe):
        absences=self.env['is.absence'].search([
            ('employe_id', '=', employe.id),
            ('date_debut', '<=', heure_debut),
            ('date_fin', '>', heure_debut),
        ])
        return absences


    def search_conges(self,heure_debut):
        conges=self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', heure_debut),
            ('date_to', '>', heure_debut),
        ])
        return len(conges)
    

    # #TODO : Il est 3 fois plus long de passer par cette recherche avec un DataFrame que directement avec une recherche Odoo
    # def search_conges_pandas(self,df_conges, heure_debut):
    #     masque = ((df_conges["date_from"] <= heure_debut) & (df_conges["date_to"] > heure_debut))
    #     res = len(df_conges[masque])
    #     return res


    def calculer_dispo_ressource(self, date_debut, date_fin):
        #Début de l'analyse : 
        #pr=cProfile.Profile() 
        #pr.enable()
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


        # #** Mettre les congés dans un DataFrame *******************************
        # #TODO : Il est 3 fois plus long de passer par cette recherche avec un DataFrame que directement avec une recherche Odoo
        # conges = [{
        #     "date_from": line.date_from,
        #     "date_to"  : line.date_to,
        # } for line in self.env['resource.calendar.leaves'].search([])]
        # df_conges = pd.DataFrame(conges)
        # #**********************************************************************


        listd=[]
        workcenter_dict={}
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
                workcenter_id =  employe.is_workcenter_id.id
                vals={
                    "heure_debut"  : heure_debut,
                    "heure_fin"    : heure_fin,
                    "employe_id"   : employe.id,
                    "workcenter_id": workcenter_id,
                    #"disponibilite": disponibilite,
                }
                #res=self.env['is.dispo.ressource'].create(vals)
                for line in employe.resource_calendar_id.attendance_ids:
                    if not line.display_type:
                        if weekday==line.dayofweek:
                            if line.week_type==False or line.week_type==modulo:
                                if heure>=line.hour_from and heure<line.hour_to:
                                    #** Recherche des congés ******************
                                    # conges=self.env['resource.calendar.leaves'].search([
                                    #     ('date_from', '<=', heure_debut),
                                    #     ('date_to', '>', heure_debut),
                                    # ])
                                    nb_conges = self.search_conges(heure_debut)
                                    #nb_conges = self.search_conges_pandas(df_conges,heure_debut)
                                    #******************************************

                                    if nb_conges==0:
                                        #** Recherche des absences ************
                                        # absences=self.env['is.absence'].search([
                                        #     ('employe_id', '=', employe.id),
                                        #     ('date_debut', '<=', heure_debut),
                                        #     ('date_fin', '>', heure_debut),
                                        # ])
                                        absences = self.search_absences(heure_debut, employe)
                                        #**************************************
                                        if len(absences)==0:
                                            disponibilite = 0.5
                                            #res.disponibilite = disponibilite


                if heure_debut not in workcenter_dict:
                    workcenter_dict[heure_debut]={}
                if workcenter_id not in workcenter_dict[heure_debut]:
                    workcenter_dict[heure_debut][workcenter_id]=0
                workcenter_dict[heure_debut][workcenter_id]+=disponibilite


                vals["disponibilite"] = disponibilite
                #res=self.env['is.dispo.ressource'].create(vals)
                listd.append(vals)
            heure_debut = heure_debut + timedelta(minutes=30)

        _logger.info("calculer_dispo_ressource : Début création des lignes en %sms"%duree(debut))
        res=self.env['is.dispo.ressource'].create(listd) #50% du temps de traitement
        _logger.info("calculer_dispo_ressource : Fin création des lignes en %sms"%duree(debut))
        _logger.info("calculer_dispo_ressource : Fin du traitement en %sms"%duree(debut))

        _logger.info("calculer_dispo_ressource : Début enregistrement workcenter_dict en %sms"%duree(debut))
        listd=[]
        for heure_debut in workcenter_dict:
            heure_fin = heure_debut + timedelta(minutes=30)
            for workcenter_id in workcenter_dict[heure_debut]:
                disponibilite = workcenter_dict[heure_debut][workcenter_id]
                vals={
                    "heure_debut"  : heure_debut,
                    "heure_fin"    : heure_fin,
                    "workcenter_id": workcenter_id,
                    "disponibilite": disponibilite,
                }
                listd.append(vals)
        res=self.env['is.dispo.ressource'].create(listd)
        _logger.info("calculer_dispo_ressource : Fin enregistrement workcenter_dict en %sms"%duree(debut))

        #pr.disable() 
        #pr.dump_stats('/media/sf_dev_odoo/14.0/bsa/analyse2.cProfile') 

        #listd : Disponibilité des ressources par employé et par heure
        #self.calculer_charge_action()


    @api.model
    def calculer_dispo_ressource_ir_cron(self):
        debut = datetime.now() 
        _logger.info("calculer_dispo_ressource_ir_cron : ** DEBUT ***********************")
        date_debut = datetime.now()
        date_fin   = date_debut + timedelta(days=366)
        self.env['is.dispo.ressource'].calculer_dispo_ressource(date_debut, date_fin)
        self.env['is.dispo.ressource'].calculer_plage_dispo_ressource()
        self.env['mrp.production'].calculer_charge_action()
        duree = (datetime.now() - debut).total_seconds()
        _logger.info("calculer_dispo_ressource_ir_cron : ** FIN en %.1fs ****************"%duree)
        return True


    def calculer_plage_dispo_ressource(self):
        "Calculer les plages de disponibilités des ressources pour la vue agenda"

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
                #**************************************************************

                #** Extraire les lignes avec une disponibilité à 0 ************
                df_open = df_dispos[df_dispos["disponibilite"]>0]
                #**************************************************************

                # Ajout d'info sur les lignes i+1 et i-1
                # Ajouter une colomne qui a pour info le "start" de la prochaine ligne et le "end" de la ligne d'avant, afin de savoir si c'est une fermeture "nouvelle" ou bien une qui s'arrête ou encore une qui continue son petit bonhomme de chemin.
                # `shift` permet d'accéder aux lignes d'avant/après. Vu sur [StackOverflow](https://stackoverflow.com/questions/30673209/pandas-compare-next-row)
                df_aug = df_open.copy()
                df_aug["heure_debut_next"] = df_open["heure_debut"].shift(-1) # Heure de début de la ligne suivante
                df_aug["heure_fin_prev"]   = df_open["heure_fin"].shift(1)    # Heure de fin de la ligne précédente

                #Pour chaque ligne, vérifier si on est dans le cas d'un début de fermeture ou la fin d'une fermeture (il y a le cas où on est au milieu d'une fermeture qui est le cas dont on veut justement se débarasser)
                df_aug["end_open"] = (df_aug["heure_debut_next"] != df_aug["heure_fin"])
                df_aug["start_open"] = (df_aug["heure_fin_prev"] != df_aug["heure_debut"])

                ### Extraire toutes les dates de début
                df_start = df_aug[df_aug["start_open"] == True]["heure_debut"]

                ### Extraire toutes les dates de fin
                df_end = df_aug[df_aug["end_open"] == True]["heure_fin"]

                #Combiner le tout (et le tout dans le même format d'origine)
                N = len(df_start)
                res = [{
                    "start" : df_start.iloc[i],
                    "end" : df_end.iloc[i],
                } for i in range(N)]
                for line in res:
                    duree=(line["end"]-line["start"]).total_seconds()/3600
                    vals={
                        "employe_id" : employe_id,
                        "heure_debut": line["start"],
                        "heure_fin"  : line["end"],
                        "duree"      : duree,
                    }
                    id=self.env['is.dispo.ressource.plage'].create(vals)


        #** Calcul des plages pour les postes de charges **********************
        workcenters = self.env['mrp.workcenter'].search([])
        for workcenter in workcenters:
            _logger.info("Calcul des plages de disponibilité pour %s"%workcenter.name)

            #** Suppression des lignes ****************************************
            cr=self._cr
            sql="delete from is_dispo_ressource_plage where workcenter_id=%s"
            cr.execute(sql,[workcenter.id])

            #** Disponibilité des ressources **************************************
            SQL="select distinct heure_debut, heure_fin from is_dispo_ressource where workcenter_id=%s and disponibilite>0 order by heure_debut"
            cr.execute(SQL,[workcenter.id])
            # rows = cr.fetchall()
            # dispos=[]
            # for row in rows:
            #     dispos.append({
            #         "heure_debut"  : row[0],
            #         "heure_fin"    : row[1],
            #     })
            dispos = [{
                "heure_debut"  : row[0],
                "heure_fin"    : row[1],
            } for row in cr.fetchall()]
            #******************************************************************

            if len(dispos)>0:
                _logger.info("Calcul des plages de disponibilité pour %s"%workcenter.name)
                df_dispos = pd.DataFrame(dispos)                                # Convertir la liste en DataFrame
                df_aug = df_dispos.copy()
                df_aug["heure_debut_next"] = df_dispos["heure_debut"].shift(-1) # Heure de début de la ligne suivante
                df_aug["heure_fin_prev"]   = df_dispos["heure_fin"].shift(1)    # Heure de fin de la ligne précédente
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
                    duree=(line["end"]-line["start"]).total_seconds()/3600
                    vals={
                        "workcenter_id" : workcenter.id,
                        "heure_debut": line["start"],
                        "heure_fin"  : line["end"],
                        "duree"      : duree,
                    }
                    id=self.env['is.dispo.ressource.plage'].create(vals)


    def voir_productions_act_window(self,ids,title):
        return {
            "name": title,
            "view_mode": "tree,form",
            "res_model": "mrp.production",
            "domain": [
                ("id" ,"in",ids),
            ],
            "type": "ir.actions.act_window",
        }


    # def voir_productions_action(self):
    #     ids=[]
    #     for obj in self:
    #         for tache in obj.taches_ids:
    #             ids.append(tache.production_id.id)
    #     return self.voir_productions_act_window(ids,"Heure")


    def voir_productions_jour_action(self):
        ids=[]
        for obj in self:
            heure_debut = obj.heure_debut.replace(hour=0).replace(minute=0).replace(second=0).replace(microsecond=0)
            heure_fin = heure_debut + timedelta(days=1)
            filtre=[
                ('workcenter_id', '=' , obj.workcenter_id.id),
                ('disponibilite', '>' , 0),
                ('employe_id'   , '=' , False),
                ('heure_debut'  , '>=', heure_debut),
                ('heure_fin'    , '<=', heure_fin),
            ]
            dispos=self.env['is.dispo.ressource'].search(filtre)
            ids=[]
            for dispo in dispos:
                for tache in dispo.taches_ids:
                    ids.append(tache.production_id.id)
        return self.voir_productions_act_window(ids,"Jour")


    def voir_productions_semaine_action(self):
        for obj in self:
            heure_debut = obj.heure_debut.replace(hour=0).replace(minute=0).replace(second=0).replace(microsecond=0)
            weekday = heure_debut.weekday() # 0=lundi
            heure_debut = heure_debut - timedelta(days=weekday) #Date au lundi
            heure_fin   = heure_debut + timedelta(days=7)      #+ jours
            filtre=[
                ('workcenter_id', '=' , obj.workcenter_id.id),
                ('disponibilite', '>' , 0),
                ('employe_id'   , '=' , False),
                ('heure_debut'  , '>=', heure_debut),
                ('heure_fin'    , '<=', heure_fin),
            ]
            dispos=self.env['is.dispo.ressource'].search(filtre)
            ids=[]
            for dispo in dispos:
                for tache in dispo.taches_ids:
                    ids.append(tache.production_id.id)
        return self.voir_productions_act_window(ids,"Semaine")


    def voir_productions_mois_action(self):
        for obj in self:
            heure_debut = obj.heure_debut.replace(hour=0).replace(minute=0).replace(second=0).replace(microsecond=0).replace(day=1)
            cemois=calendar.monthrange(heure_debut.year,heure_debut.month)
            dernier_du_mois=cemois[1]
            heure_fin   = heure_debut + timedelta(days=dernier_du_mois)
            filtre=[
                ('workcenter_id', '=' , obj.workcenter_id.id),
                ('disponibilite', '>' , 0),
                ('employe_id'   , '=' , False),
                ('heure_debut'  , '>=', heure_debut),
                ('heure_fin'    , '<=', heure_fin),
            ]
            dispos=self.env['is.dispo.ressource'].search(filtre)
            ids=[]
            for dispo in dispos:
                for tache in dispo.taches_ids:
                    ids.append(tache.production_id.id)
        return self.voir_productions_act_window(ids,"Semaine")


class is_dispo_ressource_plage(models.Model):
    _name='is.dispo.ressource.plage'
    _description='Plages de disponibilité des employés et des postes de charges pour vue agenda'
    _order='heure_debut'
    _rec_name = 'heure_debut'

    heure_debut   = fields.Datetime('Heure début'                      , required=True, index=True)
    heure_fin     = fields.Datetime('Heure fin'                        , required=True)
    duree         = fields.Float('Durée (H)')
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


