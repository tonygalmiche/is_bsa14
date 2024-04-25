# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime
import time

class assistent_report1(models.TransientModel):
    _name = "assistent.report1"
    _description = "assistent.report1"


    def date_debut_mois():
        now = datetime.date.today()                               # Date du jour
        date_debut_mois = datetime.datetime( now.year, now.month, 1 )   # Premier jour du mois
        return date_debut_mois.strftime('%Y-%m-%d')                     # Formatage


    def date_hier():
        now = datetime.date.today()                               # Date du jour
        date_hier = now + datetime.timedelta(days=-1)
        return date_hier.strftime('%Y-%m-%d')                     # Formatage


    type_rapport = fields.Selection([
        ("rapport_a_date", "Liste à date"),
        ("rapport_date_a_date", "Liste de date à date"),  
        ("rapport_mois", "Liste mensuelle"), 
    ], "Modèle de rapport", required=True)
    date_jour     = fields.Date("Date", required=False)
    date_mois     = fields.Date("Date dans le mois", required=False)
    date_debut    = fields.Date("Date de début", required=False)
    date_fin      = fields.Date("Date de fin", required=False)
    department_id = fields.Many2one('hr.department', 'Service', help="Sélectionnez un service")
    employee      = fields.Many2one('hr.employee', 'Employé', required=False, ondelete='set null', help="Sélectionnez un employé")
    interimaire   = fields.Boolean('Intérimaire',  help="Cocher pour sélectionner uniquement les intérimaires")
    saut_page     = fields.Boolean('Saut de page',  help="Cocher pour avoir un saut de page pour chaque employé")
    detail        = fields.Boolean("Vue détaillée")

    _defaults = {
        'date_jour'   :  date_hier(),
        'date_mois'   :  date_debut_mois(),
        'date_debut'  : date_debut_mois(),
        'date_fin'    :   time.strftime('%Y-%m-%d'),
        'type_rapport': 'rapport_mois',
    }


    def assistent_report1(self):
        for obj in self:
            cr = self._cr
            #report_data = self.browse(cr, uid, ids[0])
            report_link = "https://odoo14-acier-scan.bsa-inox.fr/rh/rapport1.php"
            url = str(report_link)  + '?' \
                + '&dbname='        + str(cr.dbname) \
                + '&type_rapport='  + str(obj.type_rapport) \
                + '&date_jour='     + str(obj.date_jour) \
                + '&date_mois='     + str(obj.date_mois) \
                + '&detail='        + str(obj.detail) \
                + '&department_id=' + str(obj.department_id.id) \
                + '&employee='      + str(obj.employee.id) \
                + '&interimaire='   + str(obj.interimaire) \
                + '&saut_page='     + str(obj.saut_page) \
                + '&date_debut='    + str(obj.date_debut) \
                + '&date_fin='      + str(obj.date_fin)
            return {
                'name'     : 'Go to website',
                'res_model': 'ir.actions.act_url',
                'type'     : 'ir.actions.act_url',
                'target'   : 'current',
                'url'      : url
            }
