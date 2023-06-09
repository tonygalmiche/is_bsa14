# -*- coding: utf-8 -*-
from odoo import models,fields
from datetime import datetime, timedelta
from pytz import timezone


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
        cr=self._cr
        sql="delete from is_dispo_ressource"
        cr.execute(sql)

        # Calcul sur nb_jours de la disponibilité des employées toutes les 30mn
        nb_jours = 31
        tz = timezone('Europe/Paris')
        now = datetime.now()
        heure_debut = now.replace(microsecond=0).replace(second=0).replace(minute=0)
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
                vals={
                    "heure_debut"  : heure_debut,
                    "heure_fin"    : heure_fin,
                    "employe_id"   : employe.id,
                    "workcenter_id": employe.is_workcenter_id.id,
                    "disponibilite": 0,
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
                                            res.disponibilite = 0.5
            heure_debut = heure_debut + timedelta(minutes=30)
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
