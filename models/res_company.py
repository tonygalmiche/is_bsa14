# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class res_company(models.Model):
    _inherit = "res.company"

    is_nom_imprimante = fields.Char('Nom imprimante Etiquettes')
    is_site = fields.Selection([
        ("bsa"     , "BSA"),
        ("bressane", "Bressane"),
    ], "Site", default="bsa", help="Champ utilisé pour diférencier les sites de production (ex : CGV)")


