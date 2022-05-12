# -*- coding: utf-8 -*-

from odoo import models,fields,api


class is_categorie_client(models.Model):
    _name = "is.categorie.client"
    _description = "Catégorie client"

    name = fields.Char(string="Catégorie", size=32)


class res_partner(models.Model):
    _inherit = "res.partner"

    is_code_client         = fields.Char("Code comptable client")
    is_categorie_client_id = fields.Many2one("is.categorie.client", string="Catégorie de client")
    is_rib_bsa             = fields.Many2one("res.partner.bank"   , string="RIB BSA")


#"['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
