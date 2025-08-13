# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class res_company(models.Model):
    _inherit = "res.company"


    is_type_imprimante = fields.Selection([
        ("datamax", "Datamax"),
        ("zebra"  , "Zebra"),
    ], "Type imprimante étiquettes", default="datamax", help="Champ utilisé pour connaitre le language de l'imprimante des étiquettes")
    is_nom_imprimante = fields.Char('Imprimante Etiquettes')
    is_imprimante_bl  = fields.Char('Imprimante BL')
    is_site = fields.Selection([
        ("bsa"     , "BSA Inox"),
        ("bressane", "BSA Acier"),
    ], "Site", default="bsa", help="Champ utilisé pour diférencier les sites de production (ex : CGV)")
    is_seuil_validation_rsp_achat   = fields.Integer('Seuil de validation par le responsable achat'   , default=5000)
    is_seuil_validation_dir_finance = fields.Integer('Seuil de validation par la direction financière', default=10000)
    is_cgv_ids                      = fields.Many2many('ir.attachment', 'res_company_cgv_rel', 'company_id', 'attachment_id', 'CGV')
    is_cout_horaire_montage         = fields.Float('Coût horaire montage')
    is_cout_horaire_be              = fields.Float('Coût horaire BE')
    is_bdd_pointage                 = fields.Char('Base de données des pointages', help="Utilisée pour le menu 'Supervision atelier'")
    is_url_app_flask                = fields.Char("URL application Flask", help="Gestion des taches")


