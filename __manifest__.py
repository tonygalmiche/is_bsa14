# -*- coding: utf-8 -*-
{
    "name" : "InfoSaône - Module Odoo 14 pour BSA",
    "version" : "0.1",
    "author" : "InfoSaône / Tony Galmiche",
    "category" : "InfoSaône",
    "description": """
InfoSaône - Module Odoo 14 pour BSA
===================================================

InfoSaône - Module Odoo 14 pour BSA
""",
    "maintainer": "InfoSaône",
    "website": "http://www.infosaone.com",
    "depends" : [
        "base",
        "mail",
        "sale_management",
        "stock",
        "mrp",
        "purchase",
        "hr",
        "project",
        "hr_timesheet",
        "attachment_indexation",
    ],
    "data" : [
        "security/ir.model.access.csv",
        "views/assets.xml",
        "views/account_move_line_view.xml",
        "views/is_fiche_controle.xml",
        "views/is_fiche_travail.xml",
        "views/is_import_nomenclature.xml",
        "views/product_view.xml",
        "views/res_company_view.xml",
        "views/res_partner_view.xml",
        "views/sale_view.xml",
        "views/is_accident_travail_view.xml",
        "views/is_account_move_line.xml",
        "views/is_badge.xml",
        "views/is_balance_agee.xml",
        "views/is_derniere_commande_achat.xml",
        "views/is_export_compta.xml",
        "views/is_gamme_generique_view.xml",
        "views/is_jour_ferie.xml",
        "views/is_liste_manquants.xml",
        "views/is_mrp_bom_line.xml",
        "views/is_personnel_present.xml",
        "views/is_picking_line.xml",
        "views/is_pointage_commentaire.xml",
        "views/is_pointage.xml",
        "views/is_sale_order_line.xml",
        "views/is_tracabilite_view.xml",
        "views/bsa_fnc_view.xml",
        "views/bsa_stock_a_date_view.xml",
        "views/hr_view.xml",
        #"views/mail_view.xml",
        "views/mrp_view.xml",
        "views/mrp_production_view.xml",
        "views/pricelist_view.xml",
        "views/project_view.xml",
        "views/purchase_view.xml",
        "views/stock_view.xml",
        "views/stock_picking_view.xml",
        "views/account_move_view.xml",

        # "views/is_report_view.xml",
        # "views/is_report.xml",

        "report/report_template.xml",
        "report/conditions_generales_de_vente_bressane_templates.xml",
        "report/conditions_generales_de_vente_bsa_templates.xml",
        "report/purchase_order_templates.xml",


        # "report/layouts.xml",
        "report/report_bon_atelier.xml",
        # "report/report_expense_list.xml",
        # "report/report_expense.xml",
        # "report/report_fiche_controle.xml",
        # "report/report_fiche_travail.xml",
        "report/report_invoice.xml",
        # "report/report_mrporder.xml",
        # "report/report_personnel_present.xml",
        # "report/report_qweb_mrp.xml",
        # "report/report_stockpicking.xml",
        # "report/report_template2.xml",
        "report/report.xml", 
        # "report/report2.xml",
        "report/sale_report_templates.xml",


        "wizard/assistent_report_view.xml",
        "wizard/is_etiquette_reception_view.xml",
        "wizard/is_mrp_workcenter_temps_ouverture_wiz.xml",
        "wizard/is_tracabilite_reception_view.xml",
        #"wizard/stock_transfer_details.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "active": False,
    "application": True
}




