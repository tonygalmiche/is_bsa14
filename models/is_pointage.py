# -*- coding: utf-8 -*-
import logging
from odoo import models,fields,api
from datetime import datetime, timedelta
from collections import defaultdict
from pytz import timezone

_logger = logging.getLogger(__name__)


class is_pointage(models.Model):
    _name='is.pointage'
    _description='is.pointage'
    _order='name desc'

    name          = fields.Datetime("Date Heure",required=True, default=lambda self: fields.Datetime.now())
    employee      = fields.Many2one('hr.employee', 'Employé', required=True, help="Sélectionnez un employé", index=True)
    entree_sortie = fields.Selection([("E", "Entrée"), ("S", "Sortie")], "Entrée/Sortie", required=True)
    pointeuse     = fields.Char('Pointeuse', help='Adresse IP du lecteur de badges', required=False)
    commentaire   = fields.Text('Commentaire')

    def write(self, vals):
        now = datetime.now(timezone('Europe/Paris'))
        msg="Pointage modifié manuellement %s par %s"%(now.strftime('le %d/%m/%Y à %H:%M:%S'), self.env.user.name)
        vals.update({'commentaire': msg})
        res = super(is_pointage, self).write(vals)
        return res


    def init(self):
        cr=self._cr

        cr.execute("""      
            CREATE OR REPLACE PROCEDURE procedure_is_pointage_on_insert(employee integer, entree_sortie char)
            AS $$
            import subprocess
            import syslog
            result = subprocess.run(['/usr/bin/python3', '/opt/script_is_pointage_on_insert.py', str(employee), str(entree_sortie)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)                   
            syslog.syslog(syslog.LOG_INFO, "result=%s : employee=%s : entree_sortie=%s"%(str(result),employee,entree_sortie))
            $$ 
            LANGUAGE plpython3u;
          
            CREATE OR REPLACE FUNCTION function_is_pointage_on_insert() RETURNS trigger AS
            $$
            BEGIN
                if NEW.entree_sortie='S' then
                    CALL procedure_is_pointage_on_insert(NEW.employee,NEW.entree_sortie);
                end if;
                RETURN NEW;
            END
            $$
            LANGUAGE 'plpgsql' VOLATILE;

            DROP TRIGGER IF EXISTS trigger_is_pointage_on_insert ON is_pointage;

            create trigger trigger_is_pointage_on_insert
            after insert on is_pointage
            for each row
            execute procedure function_is_pointage_on_insert();
        """)
           

class is_pointage_commentaire(models.Model):
    _name='is.pointage.commentaire'
    _description='is.pointage.commentaire'
    _order='name desc'

    name        = fields.Date("Date",required=True, default=fields.datetime.now)
    employee    = fields.Many2one('hr.employee', 'Employé', required=True, help="Sélectionnez un employé", index=True)
    commentaire = fields.Char('Commentaire', size=15, help="Mettre un commentaire court sur 15 caractères maximum")


class is_jour_ferie(models.Model):
    _name='is.jour.ferie'
    _description='is.jour.ferie'
    _order='date'

    name      = fields.Char("Intitulé",size=100,help='Intitulé du jour férié (ex : Pâques)', required=True, index=True)
    date      = fields.Date("Date",required=True)
    jour_fixe = fields.Boolean('jour férié fixe',  help="Cocher pour préciser que ce jour férié est valable tous les ans")
    info_id   = fields.Many2one('is.heure.effective.info', 'Information')


class is_heure_effective(models.Model):
    _name='is.heure.effective'
    _description='is.heure.effective'
    _order='name desc'

    name                = fields.Date("Date",required=True)
    employee_id         = fields.Many2one('hr.employee', 'Employé', required=True)
    department_id       = fields.Many2one('hr.department', 'Département')
    theorique           = fields.Float('Heures théoriques')
    effectif_calcule    = fields.Float('Heures éffectives calculées')
    effectif_reel       = fields.Float('Heures éffectives réelles')
    balance_reelle      = fields.Float('Balance réelle')
    info_id             = fields.Many2one('is.heure.effective.info', 'Information')
    info_complementaire = fields.Char('Information complémentaire')


    def write(self, vals):
        for obj in self:
            if "effectif_reel" in vals:
                #obj = self.browse(cr, uid, ids[0], context=context)
                vals["balance_reelle"]=vals["effectif_reel"]-obj.theorique
        res = super(is_heure_effective, self).write(vals)
        return res


class is_heure_effective_info(models.Model):
    _name='is.heure.effective.info'
    _description='is.heure.effective.info'
    _order='name'

    name   = fields.Char("Information",required=True)
    active = fields.Boolean("Active",default=True)


class is_suivi_heures(models.Model):
    _name        = 'is.suivi.heures'
    _description = 'Suivi des heures travaillées'
    _order       = 'week_start desc, employee_id'

    employee_id     = fields.Many2one('hr.employee', 'Employé', required=True, index=True)
    department_id   = fields.Many2one('hr.department', 'Département')
    week_start      = fields.Date('Semaine du', required=True)
    annee           = fields.Char('Année',       store=True, compute='_compute_annee_semaine')
    mois_numero     = fields.Char('Mois N°',     store=True, compute='_compute_annee_semaine')
    mois            = fields.Char('Mois',         store=True, compute='_compute_annee_semaine')
    semaine         = fields.Char('Semaine N°',  store=True, compute='_compute_annee_semaine')
    semaine_label   = fields.Char('Semaine',      store=True, compute='_compute_annee_semaine')
    balance_semaine = fields.Float('Heures sup semaine', digits=(14, 2))

    @api.depends('week_start')
    def _compute_annee_semaine(self):
        for obj in self:
            if obj.week_start:
                iso = obj.week_start.isocalendar()
                obj.annee         = str(iso[0])
                obj.mois_numero   = '%02d' % obj.week_start.month
                obj.mois          = '%s-%s' % (str(iso[0]), '%02d' % obj.week_start.month)
                obj.semaine       = '%02d' % iso[1]
                obj.semaine_label = '%s-S%s' % (str(iso[0]), '%02d' % iso[1])
            else:
                obj.annee         = ''
                obj.mois_numero   = ''
                obj.mois          = ''
                obj.semaine       = ''
                obj.semaine_label = ''

    def action_calculer(self, nb_semaines=None):
        """Calcule le suivi des heures sup par employé et par semaine
        à partir des données de is.heure.effective.
        Règle : si la balance hebdomadaire < 0, on met 0.
        nb_semaines : si renseigné, ne recalcule que les n dernières semaines.
                      Si None, recalcule toutes les semaines.
        """
        from datetime import date
        debut = datetime.now()

        if nb_semaines:
            today       = date.today()
            monday_now  = today - timedelta(days=today.weekday())
            date_limite = monday_now - timedelta(weeks=nb_semaines - 1)
            domaine_suivi  = [('week_start', '>=', date_limite)]
            domaine_heures = [('name', '>=', date_limite)]
            info_fenetre = "%d semaines depuis le %s" % (nb_semaines, date_limite.strftime('%d/%m/%Y'))
        else:
            domaine_suivi  = []
            domaine_heures = []
            info_fenetre = "complet"

        _logger.info("Suivi des heures travaillées : début du calcul %s (%s)", info_fenetre, debut.strftime('%d/%m/%Y %H:%M:%S'))

        # Suppression des enregistrements concernés
        self.env['is.suivi.heures'].search(domaine_suivi).unlink()

        # Lecture des heures effectives
        heures = self.env['is.heure.effective'].search(domaine_heures)

        # Accumulation par (employee_id, lundi_de_la_semaine)
        balances   = defaultdict(float)
        dept_cache = {}

        for h in heures:
            if not h.name or not h.employee_id:
                continue
            d      = h.name
            monday = d - timedelta(days=d.weekday())
            key    = (h.employee_id.id, monday)
            balances[key] += h.balance_reelle
            if h.employee_id.id not in dept_cache:
                dept_cache[h.employee_id.id] = h.employee_id.department_id.id or False

        # Création des enregistrements
        vals_list = []
        for (employee_id, monday), balance in balances.items():
            vals_list.append({
                'employee_id'    : employee_id,
                'department_id'  : dept_cache.get(employee_id, False),
                'week_start'     : monday,
                'balance_semaine': max(0.0, balance),
            })

        if vals_list:
            self.env['is.suivi.heures'].create(vals_list)

        fin   = datetime.now()
        duree = (fin - debut).total_seconds()
        _logger.info(
            "Suivi des heures travaillées : fin du calcul (%s) — %d enregistrement(s) créé(s) — durée : %.2f s",
            fin.strftime('%d/%m/%Y %H:%M:%S'),
            len(vals_list),
            duree,
        )

        return {
            'type'   : 'ir.actions.client',
            'tag'    : 'reload',
        }







