# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Poste de charge',
        help="Poste de charge associé à ce congé"
    )