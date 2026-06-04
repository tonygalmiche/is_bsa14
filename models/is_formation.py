# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta


class IsFormation(models.Model):
    _name = 'is.formation'
    _description = 'Formation'
    _order = "name"


    name = fields.Char(string='Nom de la formation', required=True)
    validity_duration = fields.Integer(string='Durée de validité (mois)', required=True, default=12)


class IsFormationSuivi(models.Model):
    _name = 'is.formation.suivi'
    _description = 'Suivi formation'
    _order = "training_date desc"
    _rec_name = 'id'

    formation_id = fields.Many2one('is.formation', string='Formation', required=True)
    employee_id = fields.Many2one('hr.employee', string='Salarié', required=True)
    atelier = fields.Selection([('A', 'Atelier'), ('I', 'Intérieur')], string='Atelier', required=True)
    training_date = fields.Date(string='Date de la formation', required=True)
    validity_date = fields.Date(string='Validité de la formation', compute='_compute_validity_date', store=True)
    remaining_days = fields.Integer(string='Jours restant', compute='_compute_remaining_days', store=True)
    status = fields.Selection([('ok', 'OK'), ('expired', 'Expirée')], string='Statut', compute='_compute_status', store=True)

    @api.depends('training_date', 'formation_id.validity_duration')
    def _compute_validity_date(self):
        for record in self:
            if record.training_date and record.formation_id and record.formation_id.validity_duration:
                # Ajouter les mois de validité à la date de formation
                record.validity_date = record.training_date + relativedelta(months=record.formation_id.validity_duration)
            else:
                record.validity_date = None

    @api.depends('validity_date')
    def _compute_remaining_days(self):
        for record in self:
            if record.validity_date:
                today = datetime.now().date()
                delta = record.validity_date - today
                record.remaining_days = delta.days
            else:
                record.remaining_days = 0


    @api.depends('remaining_days')
    def _compute_status(self):
        for record in self:
            if record.remaining_days < 0:
                record.status = 'expired'
            else:
                record.status = 'ok'
        
        # Logique métier : si un employé a une formation OK, toutes les formations 
        # plus anciennes du même type pour cet employé doivent passer à OK
        for record in self:
            # Vérifier que l'enregistrement est persisté (a un vrai ID en base de données)
            if record.status == 'ok' and record.employee_id and record.formation_id and isinstance(record.id, int):
                # Chercher les autres formations du même employé et même type mais plus anciennes
                older_records = self.search([
                    ('employee_id', '=', record.employee_id.id),
                    ('formation_id', '=', record.formation_id.id),
                    ('training_date', '<', record.training_date),
                    ('id', '!=', record.id)
                ])
                # Les passer en OK puisqu'une formation plus récente est validée
                for older in older_records:
                    older.status = 'ok'
                    if older.remaining_days<0:
                        older.remaining_days = 0




    def action_open_suivi(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'is.formation.suivi',
            'res_id': self.id,
            'view_mode': 'form',
        }

    @api.model
    def recalculate_status_cron(self):
        """Tâche planifiée pour recalculer les jours restants et le statut chaque nuit"""
        records = self.env['is.formation.suivi'].search([])
        # Forcer l'exécution directe des fonctions de calcul
        records._compute_remaining_days()
        records._compute_status()
