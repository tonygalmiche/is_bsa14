# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, date, timedelta


class is_mrp_workcenter_temps_ouverture_wiz(models.TransientModel):
    _name = 'is.mrp.workcenter.temps.ouverture.wiz'
    _description = 'is.mrp.workcenter.temps.ouverture.wiz'


    def _date_debut(self):
        now  = date.today()
        return now


    def _date_fin(self):
        now  = date.today()
        d    = now + timedelta(days=60)
        return d.strftime('%Y-%m-%d')


    date_debut    = fields.Date("Date de début", required=True, default=lambda self: self._date_debut())
    date_fin      = fields.Date("Date de fin", required=True, default=lambda self: self._date_fin())
    nb_heures     = fields.Float("Nombre d'heures par jour et par opérateur", required=True, default=8)
    nb_operateurs = fields.Integer("Nombre d'opérateur", required=True, default=1)


    def validation(self):
        if self._context and self._context.get('active_ids'):
            ids = self._context.get('active_ids')
            workcenters = self.env["mrp.workcenter"].search([('id','in',ids)])
            for workcenter in workcenters:
                dates=[]
                for line in workcenter.is_temps_ouverture_ids:
                    if line.date_ouverture<str(date.today()):
                        line.unlink()
                    else:
                        dates.append(str(line.date_ouverture))
                date_debut = datetime.strptime(self.date_debut, '%Y-%m-%d')
                date_fin   = datetime.strptime(self.date_fin  , '%Y-%m-%d')
                nb_jours   = (date_fin - date_debut).days
                temps_ouverture = self.nb_heures*self.nb_operateurs
                for x in range(nb_jours+1):
                    if str(date_debut)>= str(date.today()):
                        if date_debut.weekday() not in [5,6]:
                            if str(date_debut)[:10] in dates:
                                vals={
                                    'temps_ouverture': temps_ouverture,
                                }
                                lines = self.env["is.mrp.workcenter.temps.ouverture"].search([('workcenter_id','=',workcenter.id),('date_ouverture','=',str(date_debut)[:10])])
                                lines.write(vals)
                            else:
                                vals={
                                    'workcenter_id'  : workcenter.id,
                                    'date_ouverture' : str(date_debut)[:10],
                                    'temps_ouverture': temps_ouverture,
                                }
                                self.env["is.mrp.workcenter.temps.ouverture"].create(vals)
                    date_debut = date_debut + timedelta(days=1)
        return True
