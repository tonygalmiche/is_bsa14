# -*- coding: utf-8 -*-

from odoo import models,fields,api


class res_users(models.Model):
    _inherit = "res.users"

    is_image_signature = fields.Binary("Image signature", help="Utilsée dans les devis paramètrables")


