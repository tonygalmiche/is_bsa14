# -*- coding: utf-8 -*-
from odoo import models,fields,api


class is_cause_retour_plan(models.Model):
    _name = "is.cause.retour.plan"
    _description = "is.cause.retour.plan"

    name = fields.Char('Cause de retour plan',required=True)


class ProjectTask(models.Model):
    _inherit = "project.task"
    _order = 'date_deadline'


    @api.depends('is_description')
    def _compute_is_description_html(self):
        for obj in self:
            obj.is_description_html = (obj.is_description or '').replace('\n','<br />')



    is_description          = fields.Text('Description longue')
    is_description_html     = fields.Text('Description HTML', compute='_compute_is_description_html', readonly=True, store=False)
    is_appro_specifique     = fields.Boolean("Appro spécifique")
    is_appro_standard       = fields.Boolean("Appro standard")
    is_acompte_verse        = fields.Boolean("Acompte versé")
    is_cause_retour_plan_id = fields.Many2one('is.cause.retour.plan', "Cause retour plan")
    is_mise_en_place        = fields.Date('Date Limite de mise en plan')


