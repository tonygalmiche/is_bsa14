# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime
import pytz


class is_personnel_present(models.Model):
    _name='is.personnel.present'
    _description='is.personnel.present'
    _order='name desc'

    name = fields.Date("Date", required=True, default=lambda *a: datetime.date.today().strftime('%Y-%m-%d'))
    site = fields.Selection([
            ('192.168.1.9'  , 'BSA'),
            ('192.168.20.10', 'Bressane'),
        ], u"Site", required=True)


    def get_pointages(self):
        sites={
            '192.168.1.9'  : 'BSA',
            '192.168.20.10': 'Bressane',
        }
        cr = self._cr
        employes=[]
        for obj in self:
            SQL="""
                select id,name
                from hr_employee
                order by name
            """
            cr.execute(SQL)
            res = cr.fetchall()
            for row in res:
                SQL="""
                    select 
                        create_date at time zone 'utc' at time zone 'europe/paris',
                        entree_sortie,
                        pointeuse
                    from is_pointage 
                    where 
                        employee="""+str(row[0])+""" and
                        pointeuse='"""+obj.site+"""' and
                        create_date>='"""+str(obj.name)+""" 00:00:00' and
                        create_date<='"""+str(obj.name)+""" 23:59:59' 
                    order by id desc limit 1
                """
                cr.execute(SQL)
                pointages = cr.fetchall()
                pointage=False
                for p in pointages:
                    if p[1]=='E':
                        pointage = p
                name = row[1]+' : '+str(pointage)
                if pointage:
                    create_date = pointage[0]
                    #create_date = datetime.datetime.strptime(create_date, '%Y-%m-%d %H:%M:%S.%f')
                    create_date = create_date.strftime('%d/%m/%Y %H:%M')
                    employes.append({
                        'name'       : row[1],
                        'create_date': create_date,
                        'pointeuse'  : sites[pointage[2]],
                    })
        return employes


    def get_db_name(self):
        db_name = self._cr.dbname
        return db_name


    def get_connexions(self):
        cr = self._cr
        connexions=[]
        users = self.env['res.users'].search([])
        for user in users:
            d = str(user.login_date)[:10]
            if d==str(self.name):
                connexions.append(user.name)
        return connexions


