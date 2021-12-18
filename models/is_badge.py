# -*- coding: utf-8 -*-
from odoo import models,fields

class is_badge(models.Model):
    _name='is.badge'
    _description='is.badge'
    _order='employee'
    _sql_constraints = [('name_uniq', 'UNIQUE(name)', 'Ce badge existe deja')]

    name     = fields.Char("Code", required=True, index=True)
    employee = fields.Many2one('hr.employee', 'Employé', required=False, ondelete='set null', help="Sélectionnez un employé")


