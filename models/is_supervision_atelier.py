# -*- coding: utf-8 -*-
from odoo import models,fields,api
from datetime import datetime, timedelta, date
import psycopg2
from psycopg2.extras import RealDictCursor


class is_supervision_atelier(models.Model):
    _name='is.supervision.atelier'
    _description='Supervision atelier'
    _order='employe_id'

    employe_id      = fields.Many2one('hr.employee', 'Employé', required=True)
    department_id   = fields.Many2one('hr.department', 'Département')
    debut_pointage  = fields.Datetime('Début pointage')
    workcenter_id   = fields.Many2one('mrp.workcenter', 'Poste en cours')
    ligne_ot_id     = fields.Many2one('is.ordre.travail.line', 'Ligne OT en cours')
    debut_poste     = fields.Datetime('Début poste')
    temps_restant   = fields.Float('Temps restant')


    def is_supervision_atelier_action(self):
        company = self.env.user.company_id
        dbname = company.is_bdd_pointage
        try:
            cnx_pointage = psycopg2.connect("dbname='%s'"%dbname)
            cr_pointage  = cnx_pointage.cursor(cursor_factory=RealDictCursor)
        except Exception:
            cnx_pointage=False
        now = datetime.now()
        self.env['is.supervision.atelier'].search([]).unlink()
        domain=[
            ('department_id', 'not in', ['Inactif','Administration']),
            ('department_id', '!=', False),
        ]
        employes=self.env['hr.employee'].search(domain)
        for employe in employes:
            #** Recherche ligne OT en cours *******************************
            domain=[
                ('employe_id' , '=', employe.id),
                ('heure_debut', '!=', False),
                ('heure_fin'  , '=', False),
            ]
            lines=self.env['is.ordre.travail.line.temps.passe'].search(domain,limit=1)
            ligne_ot_id=debut_poste=temps_restant=workcenter_id=False
            for line in lines:
                debut_poste   = line.heure_debut
                ligne_ot_id   = line.line_id.id
                workcenter_id = line.line_id.workcenter_id.id
                temps_depuis_pointage = (now-debut_poste).total_seconds()/3600
                temps_restant = line.line_id.reste - temps_depuis_pointage
                if temps_restant<0:
                    temps_restant=0
            #**********************************************************

            #** Recherche dernier pointage ****************************
            debut_pointage=False
            if cnx_pointage:
                SQL="""
                    SELECT ip.name
                    FROM is_pointage ip join hr_employee he on ip.employee=he.id
                    WHERE he.is_matricule=%s and ip.entree_sortie='E'
                    ORDER BY ip.id desc
                    limit 1
                """
                cr_pointage.execute(SQL,[employe.is_matricule])
                rows = cr_pointage.fetchall()
                for row in rows:
                    debut_pointage = row['name']
            #**********************************************************

            vals = {
                'employe_id':    employe.id,
                'department_id': employe.department_id.id,
                'ligne_ot_id':   ligne_ot_id,
                'debut_poste':   debut_poste,
                'temps_restant': temps_restant,
                'workcenter_id': workcenter_id,
                'debut_pointage': debut_pointage,
            }
            self.env['is.supervision.atelier'].create(vals)
        res= {
            'name': 'Supervision atelier',
            'view_mode': 'tree',
            'res_model': 'is.supervision.atelier',
            'type': 'ir.actions.act_window',
            'context':{
                'search_default_poste_en_cours':1
            }
        }
        return res

    