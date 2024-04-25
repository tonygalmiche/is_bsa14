# -*- coding: utf-8 -*-
from odoo import models,fields
from datetime import datetime
from pytz import timezone


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







