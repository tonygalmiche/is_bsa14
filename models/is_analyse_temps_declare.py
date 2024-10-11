# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_analyse_temps_declare(models.Model):
    _name='is.analyse.temps.declare'
    _description='Analyse temps déclaré'
    _order='name desc'

    name       = fields.Char("N°", readonly=True)
    date_debut = fields.Date("Date de début", required=True)
    date_fin   = fields.Date("Date de fin"  , required=True)
    ligne_ids  = fields.One2many('is.analyse.temps.declare.ligne', 'analyse_id', 'Lignes')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.analyse.temps.declare')
        res = super(is_analyse_temps_declare, self).create(vals)
        return res


    def generer_ligne_action(self):
        cr=self._cr
        for obj in self:
            print(obj)
            obj.ligne_ids.unlink()

        for obj in self:
            date_debut = '%s 00:00:00'%obj.date_debut
            date_fin   = '%s 23:59:59'%obj.date_fin
            SQL="""
                SELECT employe_id,sum(disponibilite) temps_prevu
                FROM is_dispo_ressource
                WHERE heure_debut>=%s and heure_debut<=%s and employe_id is not null and employe_id<>1
                GROUP BY employe_id
            """
            cr.execute(SQL,[date_debut,date_fin])
            rows = cr.dictfetchall()               
            for row in rows:
                print(row)
                employe_id  = row['employe_id']
                temps_prevu = row['temps_prevu']
                #** Recherche du temps déclaré ********************************
                temps_declare = ecart = 0
                SQL="""
                    SELECT sum(temps_passe) temps_declare
                    FROM is_suivi_temps_production
                    WHERE heure_debut>=%s and heure_debut<=%s and employe_id=%s
                """
                cr.execute(SQL,[date_debut,date_fin,employe_id])
                rows2 = cr.dictfetchall()               
                for row2 in rows2:
                    temps_declare = row2['temps_declare'] or 0
                ecart=temps_prevu-temps_declare
                #**************************************************************
                vals={
                    'analyse_id'   : obj.id,
                    'employe_id'   : employe_id,
                    'temps_prevu'  : temps_prevu,
                    'temps_declare': temps_declare,
                    'ecart'        : ecart, 
                }
                self.env['is.analyse.temps.declare.ligne'].create(vals)


class is_analyse_temps_declare_ligne(models.Model):
    _name = 'is.analyse.temps.declare.ligne'
    _description = "Lignes Analyse temps déclaré"
    _order='employe_id'

    analyse_id    = fields.Many2one('is.analyse.temps.declare', 'Analyse temps déclaré', required=True, ondelete='cascade')
    employe_id    = fields.Many2one('hr.employee', 'Employé', required=True)
    temps_prevu   = fields.Float("Temps prévu (HH:MM)")
    temps_declare = fields.Float("Temps déclaré (HH:MM)")
    ecart         = fields.Float("Ecart (HH:MM)")



    def voir_temps_declare_action(self):
        for obj in self:
            print(obj)
            #heure_debut = obj.heure_debut.replace(hour=0).replace(minute=0).replace(second=0).replace(microsecond=0).replace(day=1)
            #cemois=calendar.monthrange(heure_debut.year,heure_debut.month)
            #dernier_du_mois=cemois[1]
            #heure_fin   = heure_debut + timedelta(days=dernier_du_mois)
            domain=[
                ('employe_id' , '=' , obj.employe_id.id),
                ('heure_debut', '>=', obj.analyse_id.date_debut),
                ('heure_debut', '<=', obj.analyse_id.date_fin),
            ]
            lines=self.env['is.suivi.temps.production'].search(domain)
            ids=[]
            for line in lines:
                ids.append(line.id)
            return {
                "name": 'Lignes',
                "view_mode": "tree,form",
                "res_model": "is.suivi.temps.production",
                "domain": [
                    ("id" ,"in",ids),
                ],
                "type": "ir.actions.act_window",
            }




