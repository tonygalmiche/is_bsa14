# -*- coding: utf-8 -*-
from email.policy import default
from odoo import models,fields,api
import datetime
from odoo.exceptions import AccessError, UserError, ValidationError


class is_paye(models.Model):
    _name='is.paye'
    _description='is.paye'
    _rec_name = 'date_debut'
    _order='date_debut desc'

    date_debut    = fields.Date("Date de début", required=True)
    date_fin      = fields.Date("Date de fin"  , required=True)
    date_pointage = fields.Date("Date limite des pointages"  , required=True)
    employe_ids   = fields.One2many('is.paye.employe', 'paye_id', 'Employés')


    def preparation_action(self):
        cr=self._cr
        for obj in self:

            previous=False
            lines = self.env['is.paye'].search([("id","!=",obj.id),("date_debut","<",obj.date_debut)], limit=1)
            if len(lines)>0:
                previous=lines[0]
            nb_jours = (obj.date_fin - obj.date_debut).days+2
            if nb_jours<28 or nb_jours>40:
                raise ValidationError("Période incorecte")
            obj.employe_ids.unlink()
            intitules = self.env['is.paye.intitule'].search([])
            filtre=[
                ('department_id','!=','Inactif'),
                ('department_id','!=','Détaché'),
                ('is_interimaire','=',False),
                #('id','in',[798,942]),
            ]
            employees = self.env['hr.employee'].search(filtre)
            for employee in employees:
                #** Recherche compteur du mois précédent **********************
                compteur=False
                if previous:
                    lines = self.env['is.paye.employe'].search([("paye_id","=",previous.id),('employee_id','=',employee.id)], limit=1)
                    for line in lines:
                        for l in line.intitule_ids:
                            if l.intitule_id.name=="Compteur":
                                compteur = l.heure
                #**************************************************************
                date = obj.date_debut
                semaine = date.isocalendar().week
                vals={
                    "paye_id"    : obj.id,
                    "matricule"  : employee.is_matricule,
                    "employee_id": employee.id,
                }
                employe = self.env['is.paye.employe'].create(vals)
                for intitule in intitules:
                    vals={
                        "employe_id" : employe.id,
                        "intitule_id": intitule.id,
                    }
                    if compteur and intitule.name=="Compteur":
                        vals["heure"]=compteur
                    res = self.env['is.paye.employe.intitule'].create(vals)
                total_heures_semaine=total_balance=0
                total_balance_heure_sup=0
                total_cp_heure=total_cp_jour=total_maladie=total_at=total_ecole=total_abs=total_abs_justifiee=total_abs_enfant_malade=0
                heures_samedi=nb_detachements=0
                for i in range(0,nb_jours):                    
                    if date.weekday()==0:
                        semaine = date.isocalendar().week
                    info_id=info_complementaire=False
                    cp_heure=cp_jour=maladie=at=ecole=abs=abs_justifiee=abs_enfant_malade=heures_semaine=balance=hs25=hs50=0
                    balance_heure_sup=0
                    if date.weekday()!=6:
                        #** Recherche Détachement *****************************
                        detachement=False
                        filtre=[
                            ('employe_id','=' ,employee.id),
                            ('date_debut','<=',date),
                            ('date_fin'  ,'>=',date),
                        ]
                        detachements = self.env['is.detachement'].search(filtre)
                        if len(detachements):
                            detachement=True
                        #print(employee.name, date, detachements, detachement)
                        #******************************************************
                        jour=date
                        jour_char = jour.strftime('%d/%m/%Y')
                        if date<=obj.date_pointage:
                            heures = self.env['is.heure.effective'].search([('employee_id','=',employee.id),('name','=',jour)])
                            for heure in heures:
                                heures_semaine      = heure.effectif_reel
                                if date.weekday()==5:
                                    heures_samedi = heure.effectif_reel
                                balance             = heure.balance_reelle
                                balance_heure_sup = 0
                                if balance>0:
                                    balance_heure_sup = balance
                                info_id             = heure.info_id.id
                                info_complementaire = heure.info_complementaire
                                if heure.info_id.name=="Congé payé":
                                    cp_heure = -balance
                                    cp_jour  = 1
                                if heure.info_id.name=="Arrêt maladie" or heure.info_id.name=="Maladie temps partiel":
                                    maladie = -balance
                                if heure.info_id.name=="Accident travail":
                                    at = -balance

                                if heure.info_id.name=="Abs injustifiée non rémunérée" or heure.info_id.name=="Abs non rémunérée":
                                    abs = -balance
                                if heure.info_id.name=="Abs justifiée non rémunérée":
                                    abs_justifiee = -balance
                                if heure.info_id.name=="Abs enfant malade":
                                    abs_enfant_malade = -balance

                                if heure.info_id.name=="Ecole":
                                    ecole = -balance
                                if heure.info_id.name in ["Congé payé","Férié"]:
                                    balance=0
                                    balance_heure_sup = 0
                                    cp_heure=0
                        else:
                            if date.weekday()==0:
                                heures_semaine = employee.is_jour1
                            if date.weekday()==1:
                                heures_semaine = employee.is_jour2
                            if date.weekday()==2:
                                heures_semaine = employee.is_jour3
                            if date.weekday()==3:
                                heures_semaine = employee.is_jour4
                            if date.weekday()==4:
                                heures_semaine = employee.is_jour5
                            if date.weekday()==5:
                                heures_semaine = employee.is_jour6
                                heures_samedi  = employee.is_jour6
                            if date.weekday()==6:
                                heures_semaine = employee.is_jour7

                        if detachement and heures_semaine>0:
                            nb_detachements+=1
                            if info_complementaire:
                                info_complementaire="Détachement, "+info_complementaire
                            else:
                                info_complementaire="Détachement"

                        total_heures_semaine+=heures_semaine
                        total_balance+=balance
                        total_balance_heure_sup+=balance_heure_sup
                        total_cp_heure += cp_heure
                        total_cp_jour  += cp_jour
                        total_maladie  += maladie
                        total_at       += at
                        total_abs               += abs
                        total_abs_justifiee     += abs_justifiee
                        total_abs_enfant_malade += abs_enfant_malade
                        total_ecole    += ecole
                    if date.weekday()==6 or i==(nb_jours-1):
                        info_complementaire=False
                        if heures_samedi>0:
                            x=total_heures_semaine-heures_samedi
                            info_complementaire="Sem:%.2f, Sa:%.2f"%(x,heures_samedi)

                        jour=False
                        jour_char = "Semaine %s"%(semaine)
                        heures_semaine = total_heures_semaine
                        balance        = total_balance
                        cp_heure       = total_cp_heure
                        cp_jour        = total_cp_jour
                        maladie        = total_maladie
                        at             = total_at
                        abs               = total_abs
                        abs_justifiee     = total_abs_justifiee
                        abs_enfant_malade = total_abs_enfant_malade
                        ecole             = total_ecole

                        #Le samedi est toujours compté à 50%
                        total_balance_heure_sup=total_balance_heure_sup-heures_samedi
                        if total_balance_heure_sup>0:
                            if total_balance_heure_sup<=4:
                                hs25=total_balance_heure_sup
                            else:
                                hs25=4
                        if total_balance_heure_sup>4:
                            hs50=total_balance_heure_sup-4
                        if heures_samedi>0:
                            hs50+=heures_samedi

                    vals={
                        "employe_id"         : employe.id,
                        "jour"               : jour,
                        "jour_char"          : jour_char,
                        "heures_semaine"     : heures_semaine,
                        "balance"            : balance,
                        "info_id"            : info_id,
                        "info_complementaire": info_complementaire,
                        "cp_heure"           : cp_heure,
                        "cp_jour"            : cp_jour,
                        "hs25"               : hs25,
                        "hs50"               : hs50,
                        "maladie"            : maladie,
                        "at"                 : at,
                        "abs"                : abs,
                        "abs_justifiee"      : abs_justifiee,
                        "abs_enfant_malade"  : abs_enfant_malade,
                        "ecole"              : ecole,
                    }
                    res = self.env['is.paye.employe.jour'].create(vals)
                    if date.weekday()==6:
                        total_heures_semaine=total_balance=total_balance_heure_sup=0
                        total_cp_heure=total_cp_jour=total_maladie=total_at=total_ecole=total_abs=total_abs_justifiee=total_abs_enfant_malade=0
                        heures_samedi=0
                    date = date + datetime.timedelta(days=1)
                employe.onchange_jour_ids()

                #** Déplacement ***************************************************
                v = 0
                for line in employe.jour_ids:
                    if line.info_id.name=="Déplacement":
                        v+=1
                employe.deplacement=v
                #******************************************************************

                #** Détachement ***************************************************
                # v = 0
                # for line in employe.jour_ids:
                #     if line.info_id.name=="Détachement":
                #         v+=1
                employe.detachement=nb_detachements
                #******************************************************************

                #** Ticket restaurant *********************************************
                v = 0
                for line in employe.jour_ids:
                    if line.jour and line.heures_semaine>6:
                        v+=1
                if v>11:
                    v=11
                employe.ticket_restaurant = v
                #******************************************************************


class is_paye_employe(models.Model):
    _name='is.paye.employe'
    _description='is.paye.employe'
    _rec_name = 'employee_id'
    _order='matricule'

    paye_id        = fields.Many2one('is.paye', 'Préparation salaire', required=True, ondelete='cascade')
    matricule      = fields.Char("Matricule")
    employee_id    = fields.Many2one('hr.employee', string='Employé' , required=True)
    jour_ids       = fields.One2many('is.paye.employe.jour', 'employe_id', 'Jours')
    intitule_ids   = fields.One2many('is.paye.employe.intitule', 'employe_id', 'Intitulé')
    intitule_calcule_ids = fields.One2many('is.paye.employe.intitule.calcule', 'employe_id', 'Intitulé Calculé')
    heures_semaine = fields.Float("Heures semaine", digits=(14,2))
    balance        = fields.Float("Balance", digits=(14,2))
    hs25           = fields.Float("HS 25", digits=(14,2))
    hs50           = fields.Float("HS 50", digits=(14,2))
    cp_heure       = fields.Float("CP Heure", digits=(14,2))
    cp_jour        = fields.Float("CP Jour", digits=(14,2))
    maladie        = fields.Float("Maladie", digits=(14,2))
    at             = fields.Float("AT", digits=(14,2))

    abs               = fields.Float("Abs injustifiée non rémunérée", digits=(14,2))
    abs_justifiee     = fields.Float("Abs justifiée non rémunérée", digits=(14,2))
    abs_enfant_malade = fields.Float("Abs enfant malade", digits=(14,2))

    ecole          = fields.Float("Ecole", digits=(14,2))
    deplacement       = fields.Float("Déplacement"      , digits=(14,2))
    detachement       = fields.Float("Détachement"      , digits=(14,2))
    ticket_restaurant = fields.Float("Ticket restaurant", digits=(14,2))
    intitules         = fields.Text("Intitulés", store=False, readonly=True, compute='_compute_intitules')
    commentaire       = fields.Text("Commentaire")

    @api.depends('intitule_ids')
    def _compute_intitules(self):
        for obj in self:
            html=""
            html+="<table style='width:100%' class='colisage'>"
            html+="<thead><tr><th>Intitulé</th><th>Valeur</th><th>Commentaire</th></tr></thead>"
            html+="<tbody>"
            for line in obj.intitule_ids:
                html+="<tr>"
                html+="<td>"+line.intitule_id.name+"</td>"
                html+="<td style='text-align:right'>"+str(line.heure)+"</td>"
                html+="<td style='text-align:left'>"+(line.commentaire or '')+"</td>"
                html+="</tr>"
            html+="<div style='white-space: nowrap;'>                                                 </div>"
            html+="</tbody>"
            html+="</table>"
            obj.intitules=html


    @api.onchange('jour_ids')
    def onchange_jour_ids(self):
        for obj in self:
            heures_semaine=balance=hs25=hs50=cp_heure=cp_jour=maladie=at=abs=abs_justifiee=abs_enfant_malade=ecole=0
            for line in obj.jour_ids:
                if line.jour:
                    heures_semaine+=line.heures_semaine
                    balance+=line.balance
                    cp_heure+=line.cp_heure
                    cp_jour+=line.cp_jour
                    maladie+=line.maladie
                    at+=line.at
                    abs+=line.abs
                    abs_justifiee+=line.abs_justifiee
                    abs_enfant_malade+=line.abs_enfant_malade
                    ecole+=line.ecole
                else:
                    hs25+=line.hs25
                    hs50+=line.hs50
            obj.heures_semaine = heures_semaine
            obj.balance = balance
            obj.hs25 = hs25
            obj.hs50 = hs50
            obj.cp_heure = cp_heure
            obj.cp_jour = cp_jour
            obj.maladie = maladie
            obj.at = at
            obj.abs = abs
            obj.abs_justifiee = abs_justifiee
            obj.abs_enfant_malade = abs_enfant_malade
            obj.ecole = ecole
 

    def acceder_employe_action(self):
        for obj in self:
            res={
                'name': 'Employé',
                'view_mode': 'form',
                'res_model': 'is.paye.employe',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res


class is_paye_employe_intitule(models.Model):
    _name='is.paye.employe.intitule'
    _description='is.paye.employe.intitule'

    employe_id     = fields.Many2one('is.paye.employe', 'Employé', required=True, ondelete='cascade')
    intitule_id    = fields.Many2one('is.paye.intitule', 'Intitulé', required=True)
    heure          = fields.Float("Valeur", digits=(14,2))
    commentaire    = fields.Char("Commentaire")


class is_paye_employe_intitule_calcule(models.Model):
    _name='is.paye.employe.intitule.calcule'
    _description='is.paye.employe.intitule.calcule'
    _odrer='intitule_calcule'

    employe_id     = fields.Many2one('is.paye.employe', 'Employé', required=True, ondelete='cascade')
    intitule_calcule = fields.Selection([
        ('detachement'      , 'Détachement'),
        ('deplacement'      , 'Déplacement'),
        ('cp'               , 'CP'),
        ('ticket_restaurant', 'Ticket restaurant'),
    ], "Intitulé calculé", required=True)
    heure          = fields.Float("Valeur", digits=(14,2))
    commentaire    = fields.Char("Commentaire")


class is_paye_employe_jour(models.Model):
    _name='is.paye.employe.jour'
    _description='is.paye.employe.jour'
    _rec_name = 'jour'
    _order='id'

    employe_id     = fields.Many2one('is.paye.employe', 'Employé', required=True, ondelete='cascade')
    jour           = fields.Date("Date")
    jour_char      = fields.Char("Date/Semaine")
    heures_semaine = fields.Float("Heures semaine", digits=(14,2))
    balance        = fields.Float("Balance", digits=(14,2))
    info_id             = fields.Many2one('is.heure.effective.info', 'Information')
    info_complementaire = fields.Char('Information complémentaire')
    hs25           = fields.Float("HS 25", digits=(14,2))
    hs50           = fields.Float("HS 50", digits=(14,2))
    cp_heure       = fields.Float("CP Heure", digits=(14,2))
    cp_jour        = fields.Float("CP Jour", digits=(14,2))
    maladie        = fields.Float("Maladie", digits=(14,2))
    at             = fields.Float("AT", digits=(14,2))

    abs               = fields.Float("Abs injustifiée non rémunérée", digits=(14,2))
    abs_justifiee     = fields.Float("Abs justifiée non rémunérée", digits=(14,2))
    abs_enfant_malade = fields.Float("Abs enfant malade", digits=(14,2))

    ecole          = fields.Float("Ecole", digits=(14,2))


class is_paye_intitule(models.Model):
    _name='is.paye.intitule'
    _description='is.paye.intitule'

    name   = fields.Char("Intitulé", required=True)
    active = fields.Boolean("Actif", default="True")
