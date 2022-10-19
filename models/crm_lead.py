# -*- coding: utf-8 -*-
from odoo import models,fields,api


class crm_lead(models.Model):
    _inherit  = "crm.lead"

    is_affaire_id = fields.Many2one('is.devis.parametrable.affaire', 'Affaire')

