# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime
from odoo.exceptions import AccessError, UserError, ValidationError


class is_paye(models.Model):
    _name='is.paye'
    _description='is.paye'
    _rec_name = 'date_debut'
    _order='date_debut desc'

    date_debut  = fields.Date("Date de début", required=True)
    date_fin    = fields.Date("Date de fin"  , required=True)
    employe_ids = fields.One2many('is.paye.employe', 'paye_id', 'Employés')


    def preparation_action(self):
        cr=self._cr
        for obj in self:
            nb_jours = (obj.date_fin - obj.date_debut).days+2
            if nb_jours<28 or nb_jours>40:
                raise ValidationError("Période incorecte")
            obj.employe_ids.unlink()
            intitules = self.env['is.paye.intitule'].search([])
            employees = self.env['hr.employee'].search([('department_id','!=','Inactif'),('is_interimaire','=',False)])
            for employee in employees:
                date = obj.date_debut
                semaine = date.isocalendar().week
                vals={
                    "paye_id"    : obj.id,
                    "employee_id": employee.id,
                }
                employe = self.env['is.paye.employe'].create(vals)
                for intitule in intitules:
                    vals={
                        "employe_id" : employe.id,
                        "intitule_id": intitule.id,
                    }
                    res = self.env['is.paye.employe.intitule'].create(vals)
                total_heures_semaine=total_balance=0
                total_cp_heure=total_cp_jour=total_maladie=total_at=total_ecole=total_abs=0
                for i in range(0,nb_jours):                    
                    if date.weekday()==0:
                        semaine = date.isocalendar().week
                    heures_semaine=balance=info_id=info_complementaire=False
                    cp_heure=cp_jour=maladie=at=ecole=abs=False
                    if date.weekday()!=6:
                        jour=date
                        jour_char = jour.strftime('%d/%m/%Y')
                        heures = self.env['is.heure.effective'].search([('employee_id','=',employee.id),('name','=',jour)])
                        for heure in heures:
                            heures_semaine      = heure.effectif_reel
                            balance             = heure.balance_reelle
                            info_id             = heure.info_id.id
                            info_complementaire = heure.info_complementaire
                            if heure.info_id.name=="Congé payé":
                                cp_heure = -balance
                                cp_jour  = 1
                            if heure.info_id.name=="Arrêt maladie":
                                maladie = -balance
                            if heure.info_id.name=="Accident travail":
                                at = -balance
                            if heure.info_id.name=="Absence injustifiée":
                                abs = -balance
                            if heure.info_id.name=="Ecole":
                                ecole = -balance
                        total_heures_semaine+=heures_semaine
                        total_balance+=balance
                        total_cp_heure += cp_heure
                        total_cp_jour  += cp_jour
                        total_maladie  += maladie
                        total_at       += at
                        total_abs      += abs
                        total_ecole    += ecole
                    if date.weekday()==6 or i==(nb_jours-1):
                        jour=False
                        jour_char = "Semaine %s"%(semaine)
                        heures_semaine = total_heures_semaine
                        balance        = total_balance
                        cp_heure       = total_cp_heure
                        cp_jour        = total_cp_jour
                        maladie        = total_maladie
                        at             = total_at
                        abs            = total_abs
                        ecole          = total_ecole
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
                        "maladie"            : maladie,
                        "at"                 : at,
                        "abs"                : abs,
                        "ecole"              : ecole,
                    }
                    res = self.env['is.paye.employe.jour'].create(vals)
                    if date.weekday()==6:
                        total_heures_semaine=total_balance=0
                        total_cp_heure=total_cp_jour=total_maladie=total_at=total_ecole=total_abs=0
                    date = date + datetime.timedelta(days=1)
                employe.onchange_jour_ids()


class is_paye_employe(models.Model):
    _name='is.paye.employe'
    _description='is.paye.employe'
    _rec_name = 'employee_id'
    _order='employee_id'

    paye_id        = fields.Many2one('is.paye', 'Préparation salaire', required=True, ondelete='cascade')
    employee_id    = fields.Many2one('hr.employee', string='Employé' , required=True)
    jour_ids       = fields.One2many('is.paye.employe.jour', 'employe_id', 'Jours')
    intitule_ids   = fields.One2many('is.paye.employe.intitule', 'employe_id', 'Intitulés')
    heures_semaine = fields.Float("Heures semaine", digits=(14,2))
    balance        = fields.Float("Balance", digits=(14,2))
    hs25           = fields.Float("HS 25", digits=(14,2))
    hs50           = fields.Float("HS 50", digits=(14,2))
    cp_heure       = fields.Float("CP Heure", digits=(14,2))
    cp_jour        = fields.Float("CP Jour", digits=(14,2))
    maladie        = fields.Float("Maladie", digits=(14,2))
    at             = fields.Float("AT", digits=(14,2))
    abs            = fields.Float("Abs Injustifiée", digits=(14,2))
    ecole          = fields.Float("Ecole", digits=(14,2))

    @api.onchange('jour_ids')
    def onchange_jour_ids(self):
        for obj in self:
            heures_semaine=balance=hs25=hs50=cp_heure=cp_jour=maladie=at=abs=ecole=0
            for line in obj.jour_ids:
                if line.jour:
                    heures_semaine+=line.heures_semaine
                    balance+=line.balance
                    hs25+=line.hs25
                    hs50+=line.hs50
                    cp_heure+=line.cp_heure
                    cp_jour+=line.cp_jour
                    maladie+=line.maladie
                    at+=line.at
                    abs+=line.abs
                    ecole+=line.ecole
            obj.heures_semaine = heures_semaine
            obj.balance = balance
            obj.hs25 = hs25
            obj.hs50 = hs50
            obj.cp_heure = cp_heure
            obj.cp_jour = cp_jour
            obj.maladie = maladie
            obj.at = at
            obj.abs = abs
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
    intitule_id    = fields.Many2one('is.paye.intitule', 'Intitulé')
    heure          = fields.Float("Nb heures", digits=(14,2))


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
    abs            = fields.Float("Abs Injustifiée", digits=(14,2))
    ecole          = fields.Float("Ecole", digits=(14,2))


class is_paye_intitule(models.Model):
    _name='is.paye.intitule'
    _description='is.paye.intitule'

    name = fields.Char("Intitulé")
