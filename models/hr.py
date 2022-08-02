# -*- coding: utf-8 -*-
from odoo import models,fields

class hr_employee(models.Model):
    _inherit = "hr.employee"

    is_workcenter_ids = fields.Many2many('mrp.workcenter', 'hr_employee_mrp_workcenter_rel', 'employe_id', 'workcenter_id', 'Postes de charges autorisés')

    is_matricule = fields.Char('Matricule', help='N° de matricule du logiciel de paye', required=False)
    is_categorie = fields.Selection([
        ("2x8" , "Équipe en 2x8"), 
        ("2x8r", "Équipe en 2x8 avec recouvrement"), 
        ("nuit", "Équipe de nuit"),
        ("3x8" , "en 3x8"),
        ("jour", "Personnel de journée"),
    ], "Catégorie de personnel", required=False)
    is_interimaire    = fields.Boolean('Intérimaire',  help="Cocher pour indiquer que c'est un intérimaire")
    is_badge_count    = fields.Integer(string='# Badges'   , compute="_badge_count")
    is_pointage_count = fields.Integer(string='# Pointages', compute="_pointage_count")
    is_jour1 = fields.Float('Lundi')
    is_jour2 = fields.Float('Mardi')
    is_jour3 = fields.Float('Mercredi')
    is_jour4 = fields.Float('Jeudi')
    is_jour5 = fields.Float('Vendredi')
    is_jour6 = fields.Float('Samedi')
    is_jour7 = fields.Float('Dimanche')

    is_observation = fields.Text('Observations')


    def _badge_count(self):
        for obj in self:
            print(obj)
            obj.is_badge_count = 0
        # obj = self.pool('is.badge')
        # res = {}
        # for id in ids:
        #     nb = obj.search_count(cr, uid, [('employee', '=', id)], context=context)
        #     res[id] = {
        #         'is_badge_count': nb,
        #     }
        # return res


    def _pointage_count(self):
        for obj in self:
            print(obj)
            obj.is_pointage_count = 0
        # obj = self.pool('is.pointage')
        # res = {}
        # for id in ids:
        #     nb = obj.search_count(cr, uid, [('employee', '=', id)], context=context)
        #     res[id] = {
        #         'is_pointage_count': nb,
        #     }
        # return res


    def action_view_badge(self):
        res = {}
        res['context'] = "{'employee': " + str(ids[0]) + "}"
        return res



