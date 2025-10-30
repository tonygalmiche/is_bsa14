from odoo import models,fields,api,tools, SUPERUSER_ID
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from math import ceil
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


_ETAT_OF=[
    ('draft'    , 'Brouillon'),
    ('confirmed', 'Confirmé'),
    ('progress' , 'En cours'),
    ('to_close' , 'À clôturer'),
    ('done'     , 'Fait'),
    ('cancel'   , 'Annulé'),
]


class mrp_production(models.Model):
    _inherit = "mrp.production"
    _order = "id desc"

    @api.depends('is_sale_order_line_id','is_sale_order_line_id.order_id.client_order_ref','is_sale_order_line_id.order_id.is_nom_affaire')
    def _compute_is_sale_order_id(self):
        for obj in self:
            obj.is_sale_order_id    = obj.is_sale_order_line_id.order_id.id
            obj.is_client_order_ref = obj.is_sale_order_line_id.order_id.client_order_ref or "??"
            obj.is_nom_affaire      = obj.is_sale_order_line_id.order_id.is_nom_affaire


    @api.depends('is_sale_order_line_id','is_sale_order_line_id.is_date_prevue')
    def _compute_is_date_prevue(self):
        for obj in self:
            obj.is_date_prevue = obj.is_sale_order_line_id.is_date_prevue # or obj.date_planned_start


    date_planned          = fields.Datetime("Date plannifiée", required=False, index=True, readonly=False, states={}, copy=False)
    is_date_prevue        = fields.Date(string="Date client" , compute='_compute_is_date_prevue'  , store=True, readonly=True, help="Date prévue sur la ligne de commande client")
    is_client_order_ref   = fields.Char(string="Référence client", compute='_compute_is_sale_order_id', store=True, readonly=True)
    is_date_planifiee     = fields.Datetime("Date planifiée début")
    is_date_planifiee_fin = fields.Datetime("Date planifiée fin", readonly=True)
    is_ecart_date         = fields.Integer("Ecart date", readonly=True)
    is_gabarit_id         = fields.Many2one("is.gabarit", "Gabarit")
    is_sale_order_line_id = fields.Many2one("sale.order.line", "Ligne de commande",index=True)
    is_sale_order_id      = fields.Many2one("sale.order", "Commande", compute='_compute_is_sale_order_id', store=True, readonly=True)
    is_nom_affaire        = fields.Char("Nom de l'affaire"          , compute='_compute_is_sale_order_id', store=True, readonly=True)
    generer_etiquette     = fields.Boolean('Etiquettes générées', default=False, copy=False)
    etiquette_ids         = fields.One2many('is.tracabilite.livraison', 'production_id', 'Etiquettes', copy=False)
    is_gestion_lot        = fields.Boolean('Gestion par lots')
    is_ref_client         = fields.Char("Référence client (champ obsolète)")
    is_ordre_travail_id   = fields.Many2one("is.ordre.travail", "Ordre de travail", copy=False)
    is_planification      = fields.Selection([
            ('au_plus_tot' , 'Au plus tôt'),
            ('au_plus_tard', 'Au plus tard'),
            ('date_fixee'  , 'Date fixée'),
        ], "Planification", required=True, default="au_plus_tard", 
        help="Au plus tôt : Démarrer dés maintenant\nAu plus tard : Terminer pour date client\nDate fixée : Commence à la date prévue fixée manuellement")
    is_operation_ids  = fields.One2many('is.ordre.travail.line', 'production_id', 'Opérations')
    is_semaine_prevue = fields.Char(string="Semaine prévue") #compute='_compute_is_semaine_prevue', store=True, readonly=True)
    is_mois_prevu     = fields.Char(string="Mois prévu")     #compute='_compute_is_semaine_prevue', store=True, readonly=True)
    is_pret = fields.Selection([
            ('oui', 'Oui'),
            ('non', 'Non'),
        ], "Prêt", help="Prêt à produire")
    is_move_production_ids = fields.One2many('stock.move', 'production_id', 'Produits finis',  copy=False, readonly=True)
    is_move_production_nb  = fields.Integer("Nb mouvements", compute='_compute_is_move_production_nb')

    is_pru_matiere = fields.Float("PRU Matière", readonly=True, copy=False, digits=(14,4))
    is_pru_mo      = fields.Float("PRU MO"     , readonly=True, copy=False, digits=(14,4))
    is_pru_total   = fields.Float("PRU Total"  , readonly=True, copy=False, digits=(14,4))

    is_devis_variante_id        = fields.Many2one("is.devis.parametrable.variante", "Variante devis paramètrable")
    is_devis_matiere_equipement = fields.Float("Montant matière + équipement", readonly=True, copy=False, digits=(14,4))
    is_devis_mo_option          = fields.Float("Montant MO + options"        , readonly=True, copy=False, digits=(14,4))
    is_devis_montant_total      = fields.Float("Montant total variante"      , readonly=True, copy=False, digits=(14,4))
    is_devis_ecart_pru          = fields.Float("Écart avec PRU "             , readonly=True, copy=False, digits=(14,4))
    is_workcenter_id            = fields.Many2one('mrp.workcenter', string="Poste de charge", help="Utilisé pour la gestion des tâches ")
    is_employe_ids              = fields.Many2many('hr.employee', 'is_mrp_production_employe_rel', 'production_id', 'employe_id', 'Opérateurs')
    is_employe_ids_txt          = fields.Char(string="Opérateurs (texte)", compute='_compute_is_employe_ids_txt', store=True, readonly=True)


    @api.depends('is_employe_ids')
    def _compute_is_employe_ids_txt(self):
        for obj in self:
            employes_names = []
            for employe in obj.is_employe_ids:
                employes_names.append(employe.name)
            obj.is_employe_ids_txt = ', '.join(employes_names)


    @api.depends('is_move_production_ids')
    def _compute_is_move_production_nb(self):
        for obj in self:
            obj.is_move_production_nb = len(obj.is_move_production_ids)

    
    def write(self, vals):
        if "date_planned_start" in vals:
            if type(vals["date_planned_start"]) is str:
                dt=datetime.strptime(vals["date_planned_start"], "%Y-%m-%d %H:%M:%S")
            else:
                dt=vals["date_planned_start"]
            vals["is_semaine_prevue"] = dt.strftime("%Y-S%V")
            vals["is_mois_prevu"]     = dt.strftime("%Y-%m")
        else:
            for obj in self:
                if "is_semaine_prevue" in vals:
                    AA1=int(obj.is_semaine_prevue[0:4])
                    AA2=int(vals["is_semaine_prevue"][0:4])
                    S1=int(obj.is_semaine_prevue[6:8])
                    S2=int(vals["is_semaine_prevue"][6:8])
                    dt=obj.date_planned_start + relativedelta(years=AA2-AA1, days=(S2-S1)*7)
                    vals["date_planned_start"] = dt
                if "is_mois_prevu" in vals:
                    AA1=int(obj.is_mois_prevu[0:4])
                    AA2=int(vals["is_mois_prevu"][0:4])
                    MM1=int(obj.is_mois_prevu[5:7])
                    MM2=int(vals["is_mois_prevu"][5:7])
                    years=AA2-AA1
                    months=MM2-MM1
                    if months<1:
                        months=months+12
                        years=years-1
                    dt=obj.date_planned_start + relativedelta(years=years, months=months)
                    vals["date_planned_start"] = dt
        if "date_planned_start" in vals and not "is_date_planifiee" in vals:
            vals["is_planification"]="date_fixee"
        res = super(mrp_production, self).write(vals)
        if "date_planned_start" in vals or "is_planification" in vals:
            #Ne pas lancer le calcul en récursif
            if not "is_date_planifiee" in vals:
                self.calculer_charge_ordre_travail()
        return res


    def creer_ordre_travail_ir_cron(self):
        domain=[
            ("is_ordre_travail_id","=",False),
            ("state","not in",['cancel','done']),
        ]
        productions = self.env["mrp.production"].search(domain)
        productions.creer_ordre_travail_action()



    def creer_ordre_travail_action(self):
        nb=len(self)
        ct=1
        for obj in self:
            _logger.info("creer_ordre_travail_action : %s/%s : %s"%(ct,nb,obj.name))



            #** Recherche de la qty à fabriquer de tous les backorders *******
            qty=0
            filtre=[
                ("procurement_group_id","=",obj.procurement_group_id.id),
                ("state","!=",'cancel'),
                #("state","not in",['cancel','done']),
            ]
            productions = self.env["mrp.production"].search(filtre)
            for production in productions:
                qty+=production.product_qty
            #******************************************************************

            ordre=False
            if obj.state!='cancel' and obj.bom_id.operation_ids:
                filtre=[
                    ("procurement_group_id","=",obj.procurement_group_id.id),
                ]
                ordres = self.env["is.ordre.travail"].search(filtre)
                if len(ordres)>0:
                    ordre=ordres[0]
                else:
                    filtre=[
                        ("production_id","=",obj.id),
                    ]
                    ordres = self.env["is.ordre.travail"].search(filtre)
                    if len(ordres)==0:
                        line_ids=[]
                        for line in obj.bom_id.operation_ids:
                            vals={
                                'sequence'          : line.sequence,
                                'name'              : line.name,
                                'workcenter_id'     : line.workcenter_id.id,
                                'libre'             : line.is_libre,
                                'modele_controle_id': line.is_modele_controle_id.id,
                                'recouvrement'      : line.is_recouvrement,
                                'tps_apres'         : line.is_tps_apres,
                                'duree_unitaire'    : line.is_duree_heure,
                                'duree_totale'      : line.is_duree_heure*obj.product_qty,
                                'heure_debut'       : obj.date_planned_start,
                                'heure_fin'         : obj.date_planned_start,
                            }
                            line_ids.append((0, 0, vals))
                        vals = {
                            'production_id'       : obj.id,
                            'procurement_group_id': obj.procurement_group_id.id,
                            'quantite'            : obj.product_qty,
                            'line_ids'            : line_ids,
                        }
                        ordre = self.env['is.ordre.travail'].create(vals)
                        if not ordre.production_id.is_workcenter_id:
                            for line in ordre.line_ids:
                                ordre.production_id.is_workcenter_id = line.workcenter_id.id
                                break
                        _logger.info("creer_ordre_travail_action : %s/%s : %s : create %s"%(ct,nb,obj.name,ordre.name))
            if ordre:
                obj.is_ordre_travail_id=ordre.id
                ordre.quantite = qty
                ordre.calculer_charge_ordre_travail()
                if obj.state!='done':
                    ordre.production_id = obj.id
            ct+=1



    def _pre_button_mark_done(self):
        productions_to_immediate = self._check_immediate()
        if productions_to_immediate:
            return productions_to_immediate._action_generate_immediate_wizard()

        #for production in self:
        #    if float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
        #        raise UserError(_('The quantity to produce must be positive!'))
        #    if not any(production.move_raw_ids.mapped('quantity_done')):
        #        raise UserError(_("You must indicate a non-zero amount consumed for at least one of your components"))


        #TODO : J'ai commenté ces lignes le 04/10/2023 pour désactver le wizard qui d'affiche si la nomenclature a changée
        #consumption_issues = self._get_consumption_issues()
        #if consumption_issues:
        #    return self._action_generate_consumption_wizard(consumption_issues)

        quantity_issues = self._get_quantity_produced_issues()
        if quantity_issues:
            return self._action_generate_backorder_wizard(quantity_issues)
        return True




    def declarer_une_fabrication_action(self,qt=1):
        res=False
        for obj in self:
            #qt=1
            if obj.is_gestion_lot:
                qt=obj.product_qty
            obj.qty_producing=qt
            for move in obj.move_raw_ids:
                move.quantity_done = move.should_consume_qty
            if obj.qty_producing == obj.product_qty:
                res=obj.with_context(skip_backorder=True).button_mark_done()
            else:
                res=obj.with_context(skip_backorder=True, mo_ids_to_backorder=obj.id).button_mark_done()
            obj.calculer_pru_action()
            return res
        return True


    def _generate_backorder_productions(self, close_mo=True):
        res = super(mrp_production, self)._generate_backorder_productions(close_mo=close_mo)
        for etiquette in self.etiquette_ids:
            if not etiquette.fabrique:
                etiquette.production_id = res.id
        return res


    def liste_etiquettes_action(self):
        for obj in self:
            productions = self.env["mrp.production"].search([("procurement_group_id","=", obj.procurement_group_id.id)])
            ids=[]
            for production in productions:
                for etiquette in production.etiquette_ids:
                    ids.append(etiquette.id)
            return {
                "name": "Etiquettes "+obj.procurement_group_id.name,
                "view_mode": "tree,form",
                "view_type": "form",
                "res_model": "is.tracabilite.livraison",
                "domain": [
                    ("id","in",ids),
                ],
                "type": "ir.actions.act_window",
            }


    def action_creer_etiquette_mrp(self):
        for obj in self:
            res = []
            etiquettes=""
            if obj.product_qty:
                qty = obj.product_qty
                lot=1
                if obj.product_id.is_gestion_lot:
                    lot=qty
                while ( qty >= 1):
                    vals = {
                        "production_id": obj.id,
                        "quantity": 1.0,
                        "lot_fabrication": lot,
                    }
                    new_id = self.env["is.tracabilite.livraison"].create(vals)
                    qty = qty - lot
                obj.generer_etiquette=True


    def action_creer_imprimer_etiquette_mrp(self):
        company = self.env.user.company_id
        self.action_creer_etiquette_mrp()
        res=""
        for obj in self:
            for line in obj.etiquette_ids:
                if company.is_type_imprimante=='zebra':
                    res+=line.generer_etiquette_zpl()
                else:
                    res+=line.generer_etiquette_livraison()
                #res+=line.generer_etiquette_livraison()
        self.env['is.tracabilite.reception'].imprimer_etiquette(res)

    
    def get_consume_lines(self, production_id, product_qty):
        prod_obj = self.pool.get("mrp.production")
        uom_obj = self.pool.get("product.uom")
        production = prod_obj.browse(cr, uid, production_id, context=context)
        consume_lines = []
        new_consume_lines = []
        if product_qty > 0.0:
            product_uom_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, product_qty, production.product_id.uom_id.id)
            consume_lines = prod_obj._calculate_qty(cr, uid, production, product_qty=product_uom_qty, context=context)
        
        for consume in consume_lines:
            new_consume_lines.append([0, False, consume])
        return new_consume_lines
    
    
    def get_track(self, cr, uid, product_id, context=None):
        prod_obj = self.pool.get("product.product")
        return product_id and prod_obj.browse(cr, uid, product_id, context=context).track_production or False
    
    
    def get_wizard(self, cr, uid, production, context=None):
        wiz_obj = self.pool.get('mrp.product.produce')
        
        vals = {
            'product_id': production.product_id.id,
            'product_qty': 1.0,
            'mode': 'consume_produce',
            'lot_id': False,
            'consume_lines': self.get_consume_lines(cr, uid, production.id, 1.0, context),
            'track_production': self.get_track(cr, uid, production.product_id.id, context)
        }
        new_id = wiz_obj.create(cr, uid, vals, context=context)
        wiz = wiz_obj.browse(cr, uid, new_id, context=context)
        return wiz
    

    def action_confirm(self):
        self._check_company()
        for production in self:


            _logger.info("action_confirm %s : %s"%(production.name, production.product_id.name))


            if production.bom_id:
                production.consumption = production.bom_id.consumption

            _logger.info("production.bom_id =  %s"% production.bom_id.id)


            if not production.move_raw_ids:
                raise UserError(("Add some materials to consume before marking this MO as to do : %s : %s"%(production.name, production.product_id.name)))
            


            # In case of Serial number tracking, force the UoM to the UoM of product
            if production.product_tracking == 'serial' and production.product_uom_id != production.product_id.uom_id:
                production.write({
                    'product_qty': production.product_uom_id._compute_quantity(production.product_qty, production.product_id.uom_id),
                    'product_uom_id': production.product_id.uom_id
                })
                for move_finish in production.move_finished_ids.filtered(lambda m: m.product_id == production.product_id):
                    move_finish.write({
                        'product_uom_qty': move_finish.product_uom._compute_quantity(move_finish.product_uom_qty, move_finish.product_id.uom_id),
                        'product_uom': move_finish.product_id.uom_id
                    })
            production.move_raw_ids._adjust_procure_method()
            (production.move_raw_ids | production.move_finished_ids)._action_confirm()
            production.workorder_ids._action_confirm()

            # run scheduler for moves forecasted to not have enough in stock
            #production.move_raw_ids._trigger_scheduler()
        return True


    #TODO : Cela permet de désactiver la création des ordres de travaux => A remplacer par du spécifique
    @api.onchange('bom_id')
    def _onchange_workorder_ids(self):
        if self.bom_id:
            print("## TEST ##")
            #self._create_workorder()


    def calculer_charge_action(self):
        debut = datetime.now() 
        _logger.info("calculer_charge_action : ** DEBUT")
        filtre=[
            ('state', 'not in', ['cancel','done'])
        ]
        productions=self.env['mrp.production'].search(filtre)
        nb=len(productions)
        ct=1
        for production in productions:
            _logger.info("calculer_charge_action : %s/%s %s"%(ct,nb,production.name))
            production.creer_ordre_travail_action()
            if production.is_ordre_travail_id:
                production.is_ordre_travail_id.calculer_charge_ordre_travail()
            ct+=1


        duree = (datetime.now() - debut).total_seconds()
        _logger.info("calculer_charge_action : ** FIN en %.1fs"%duree)


    @api.onchange('is_devis_variante_id')
    def _onchange_is_devis_variante_id(self):
        self.calculer_pru_action()
       

    def calculer_pru_action(self):
        for obj in self:
            pru_matiere = pru_mo = 0


            #** PRU des composants ********************************************
            for line in obj.move_raw_ids:
                production= False
                domain=[
                    ('product_id' , '=', line.product_id.id),
                    ('state'      , '=', 'done'),
                    ('write_date' , '<', obj.write_date),
                ]
                productions=self.env['mrp.production'].search(domain, order='id desc', limit=1)
                for p in productions:
                    production=p
                line.is_pru_matiere=1.23
                if production:
                    line.is_pru_production_id = production.id
                    line.is_pru_matiere = production.is_pru_matiere
                    line.is_pru_mo      = production.is_pru_mo
                else:
                    line.is_pru_matiere = line.product_id.standard_price
                line.is_pru_matiere_total = line.is_pru_matiere*line.quantity_done
                line.is_pru_mo_total      = line.is_pru_mo*line.quantity_done
                line.is_pru_total         = line.is_pru_matiere_total + line.is_pru_mo_total
                pru_matiere += line.is_pru_matiere_total
                pru_mo      += line.is_pru_mo_total
            #******************************************************************

            #** PRU ordre de fabrication **************************************
            if obj.is_ordre_travail_id:
                for line in obj.is_ordre_travail_id.line_ids:
                    pru_mo += line.temps_passe*line.workcenter_id.costs_hour
            #******************************************************************

            if obj.product_qty>0:
                obj.is_pru_matiere = pru_matiere / obj.product_qty
                obj.is_pru_mo      = pru_mo / obj.product_qty
                obj.is_pru_total   = obj.is_pru_matiere + obj.is_pru_mo


            #** Devis paramètrable ********************************************
            is_devis_matiere_equipement = is_devis_mo_option = is_devis_montant_total = is_devis_ecart_pru = 0
            if obj.is_devis_variante_id:
                variante = obj.is_devis_variante_id
                qt = variante.quantite or 1
                is_devis_matiere_equipement = (variante.montant_matiere + variante.montant_equipement)/qt
                is_devis_mo_option          = (variante.montant_montage + variante.montant_option)/qt
                is_devis_montant_total      = variante.montant_total/qt
            obj.is_devis_matiere_equipement = is_devis_matiere_equipement
            obj.is_devis_mo_option          = is_devis_mo_option
            obj.is_devis_montant_total      = is_devis_montant_total
            obj.is_devis_ecart_pru = obj.is_pru_total - is_devis_montant_total
            #******************************************************************


    def vue_gantt_ordre_production_action(self):
        for obj in self:
            return {
                "name": "Gantt",
                "view_mode": "dhtmlx_gantt_ot,timeline,tree,form",
                "res_model": "is.ordre.travail.line",
                "domain": [
                    ("ordre_id" ,"=",obj.is_ordre_travail_id.id),
                ],
                "type": "ir.actions.act_window",
                "context": {"vue_gantt":"production"},
            }


    def vue_gantt_commande_action(self):
        for obj in self:
            filtre=[
                ("is_sale_order_id","=",obj.is_sale_order_id.id),
                ("state","not in",['cancel','done']),
            ]
            productions = self.env["mrp.production"].search(filtre)
            ids=[]
            for production in productions:
                ids.append(production.is_ordre_travail_id.id)
            return {
                "name": "Gantt",
                "view_mode": "dhtmlx_gantt_ot,tree,form",
                "res_model": "is.ordre.travail.line",
                "domain": [
                    ("ordre_id" ,"in",ids),
                ],
                "type": "ir.actions.act_window",
                "context": {"vue_gantt":"production"},
            }


    def calculer_charge_ordre_travail(self):
        for obj in self:
            obj.is_ordre_travail_id.calculer_charge_ordre_travail()


    def scan_declaration_of1_action(self,TL=False):
        res={}
        err=[]
        if TL:
            etiquettes = self.env["is.tracabilite.livraison"].search([("name","=",TL)])
            for etiquette in etiquettes:
                for move in etiquette.production_id.move_raw_ids:
                    msg="scan_declaration_of1_action : stock=%s sur article %s"%(move.product_id.qty_available,move.product_id.name)
                    _logger.info(msg)
                    if move.product_id.qty_available<=0:
                        err.append("stock=%s sur article %s"%(move.product_id.qty_available,move.product_id.name))
                        #break
        res={
            'TL'  : TL,
            'test': 'toto et tutu',
            'err' : '\n'.join(err),
        }
        return res
    



    def voir_of_action(self):
        for obj in self:
            res={
                'name': 'OF',
                'view_mode': 'form',
                'res_model': 'mrp.production',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res
