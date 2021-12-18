# -*- coding: utf-8 -*-
from odoo import models,fields
from datetime import datetime
from pytz import timezone


class is_pointage(models.Model):
    _name='is.pointage'
    _description='is.pointage'
    _order='name desc'

    name          = fields.Datetime("Date Heure",required=True, default=fields.datetime.now)
    employee      = fields.Many2one('hr.employee', 'Employé', required=True, help="Sélectionnez un employé", index=True)
    entree_sortie = fields.Selection([("E", "Entrée"), ("S", "Sortie")], "Entrée/Sortie", required=True)
    pointeuse     = fields.Char('Pointeuse', help='Adresse IP du lecteur de badges', required=False)
    commentaire   = fields.Text('Commentaire')

    def write(self, vals):
        now = datetime.now(timezone('Europe/Berlin'))
        user_obj = self.pool.get('res.users')
        user = user_obj.browse(cr, uid, uid, context=context)
        this = self.pool.get(str(self))
        doc = this.browse(cr, uid, ids, context=context)
        msg="\nPointage modifié manuellement "+now.strftime('le %d/%m/%Y à %H:%M:%S')+' par '+str(user.name)
        vals.update({'commentaire': msg})
        return super(is_pointage, self).write(cr, uid, ids, vals, context=context)


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







# Vue créée pour éssayer d'identifier les anomalies de pointage, mais c'est trop complexe à faire comme cela
# Je la conserve juste pour l'exemple (Menu Configuration / Configuration / Anomalies de pointage)
# class is_pointage_anomalie(osv.osv):
#     _name = "is.pointage.anomalie"
#     _auto = False
#     _columns = {
#         'pointage_id': fields.many2one('is.pointage', 'Pointage', required=True, ondelete='set null', help="Pointage", select=True),
#         'name':fields.datetime("Date Heure",required=True),
#         'employee': fields.many2one('hr.employee', 'Employé', required=True, ondelete='set null', help="Sélectionnez un employé", select=True),
#         'entree_sortie': fields.selection([("E", "Entrée"), ("S", "Sortie")], "Entrée/Sortie", required=True),
#     }
#     def init(self, cr):
#         tools.drop_view_if_exists(cr, 'is_pointage_anomalie')
#         cr.execute("""
#                 CREATE OR REPLACE view is_pointage_anomalie AS (
#                     SELECT id as id, id as pointage_id, name, employee, entree_sortie
#                     FROM is_pointage 
#                     WHERE id>0
#                )
#         """)


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
        if "effectif_reel" in vals:
            obj = self.browse(cr, uid, ids[0], context=context)
            vals["balance_reelle"]=vals["effectif_reel"]-obj.theorique
        res = super(is_heure_effective, self).write(cr, uid, ids, vals, context=context)
        return res


class is_heure_effective_info(models.Model):
    _name='is.heure.effective.info'
    _description='is.heure.effective.info'
    _order='name'

    name = fields.Char("Information",required=True)







