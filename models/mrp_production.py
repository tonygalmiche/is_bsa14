from odoo import models,fields,api,tools, SUPERUSER_ID
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from math import ceil
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)



class mrp_production(models.Model):
    _inherit = "mrp.production"
    _order = "id desc"

    @api.depends('is_sale_order_line_id','is_sale_order_line_id.order_id.client_order_ref')
    def _compute_is_sale_order_id(self):
        for obj in self:
            obj.is_sale_order_id    = obj.is_sale_order_line_id.order_id.id
            obj.is_client_order_ref = obj.is_sale_order_line_id.order_id.client_order_ref or "??"


    @api.depends('is_sale_order_line_id','is_sale_order_line_id.is_date_prevue')
    def _compute_is_date_prevue(self):
        for obj in self:
            obj.is_date_prevue = obj.is_sale_order_line_id.is_date_prevue # or obj.date_planned_start


    # @api.depends('date_planned_start')
    # def _compute_is_semaine_prevue(self):
    #     for obj in self:
    #         obj.is_semaine_prevue = obj.date_planned_start.strftime("%Y-S%V")
    #         obj.is_mois_prevu = obj.date_planned_start.strftime("%Y-%m")


    date_planned          = fields.Datetime("Date plannifiée", required=False, index=True, readonly=False, states={}, copy=False)
    is_date_prevue        = fields.Date(string="Date client" , compute='_compute_is_date_prevue'  , store=True, readonly=True, help="Date prévue sur la ligne de commande client")
    is_client_order_ref   = fields.Char(string="Référence client", compute='_compute_is_sale_order_id', store=True, readonly=True)
    is_date_planifiee     = fields.Datetime("Date planifiée début")
    is_date_planifiee_fin = fields.Datetime("Date planifiée fin", readonly=True)
    is_ecart_date         = fields.Integer("Ecart date", readonly=True)
    is_gabarit_id         = fields.Many2one("is.gabarit", "Gabarit")
    is_sale_order_line_id = fields.Many2one("sale.order.line", "Ligne de commande")
    is_sale_order_id      = fields.Many2one("sale.order", "Commande", compute='_compute_is_sale_order_id', store=True, readonly=True)
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


    def name_get(self):
        result = []
        for obj in self:
            t=[]
            if obj.name:
                t.append(obj.name)
            if obj.is_client_order_ref:
                t.append(obj.is_client_order_ref)
            name=" / ".join(t)
            result.append((obj.id, name))
        return result





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
                    print(obj.date_planned_start, dt, years, months)
                    vals["date_planned_start"] = dt
        if "date_planned_start" in vals and not "is_date_planifiee" in vals:
            vals["is_planification"]="date_fixee"
        res = super(mrp_production, self).write(vals)
        if "date_planned_start" in vals or "is_planification" in vals:
            #Ne pas lancer le calcul en récursif
            if not "is_date_planifiee" in vals:
                self.calculer_charge_ordre_travail()
        return res


    def creer_ordre_travail_action(self):
        for obj in self:
            #** Recherche de la qty restant à fabriquer ***********************
            qty=0
            filtre=[
                ("procurement_group_id","=",obj.procurement_group_id.id),
                ("state","not in",['cancel','done']),
            ]
            productions = self.env["mrp.production"].search(filtre)
            for production in productions:
                qty=production.product_qty
            #******************************************************************

            if obj.state not in ['cancel','done'] and obj.bom_id.operation_ids:
                ordre=False
                filtre=[
                    ("procurement_group_id","=",obj.procurement_group_id.id),
                ]
                ordres = self.env["is.ordre.travail"].search(filtre)
                if len(ordres)>0:
                    ordre=ordres[0]
                    #obj.is_ordre_travail_id=ordres[0].id
                    #ordres[0].quantite = qty
                else:
                    filtre=[
                        ("production_id","=",obj.id),
                    ]
                    ordres = self.env["is.ordre.travail"].search(filtre)
                    if len(ordres)==0:
                        line_ids=[]
                        for line in obj.bom_id.operation_ids:
                            vals={
                                'sequence'      : line.sequence,
                                'name'          : line.name,
                                'workcenter_id' : line.workcenter_id.id,
                                'recouvrement'  : line.is_recouvrement,
                                'tps_apres'     : line.is_tps_apres,
                                'duree_unitaire': line.is_duree_heure,
                                'duree_totale'  : line.is_duree_heure*obj.product_qty,
                                'heure_debut'   : obj.date_planned_start,
                                'heure_fin'     : obj.date_planned_start,
                            }
                            line_ids.append((0, 0, vals))
                        vals = {
                            'production_id'       : obj.id,
                            'procurement_group_id': obj.procurement_group_id.id,
                            'quantite'            : obj.product_qty,
                            'line_ids'            : line_ids,
                        }
                        ordre = self.env['is.ordre.travail'].create(vals)
                if ordre:
                    obj.is_ordre_travail_id=ordre.id
                    ordre.quantite = qty
                    ordre.calculer_charge_ordre_travail()





    def _pre_button_mark_done(self):
        productions_to_immediate = self._check_immediate()
        if productions_to_immediate:
            return productions_to_immediate._action_generate_immediate_wizard()

        for production in self:
            if float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
                raise UserError(_('The quantity to produce must be positive!'))
            if not any(production.move_raw_ids.mapped('quantity_done')):
                raise UserError(_("You must indicate a non-zero amount consumed for at least one of your components"))

        #TODO : J'ai commenté ces lignes le 04/10/2023 pour désactver le wizard qui d'affiche si la nomenclature a changée
        #consumption_issues = self._get_consumption_issues()
        #if consumption_issues:
        #    return self._action_generate_consumption_wizard(consumption_issues)

        quantity_issues = self._get_quantity_produced_issues()
        if quantity_issues:
            return self._action_generate_backorder_wizard(quantity_issues)
        return True






    def declarer_une_fabrication_action(self):
        res=False
        for obj in self:
            qt=1
            if obj.is_gestion_lot:
                qt=obj.product_qty
            obj.qty_producing=qt
            for move in obj.move_raw_ids:
                move.quantity_done = move.should_consume_qty
            if obj.qty_producing == obj.product_qty:
                res=obj.with_context(skip_backorder=True).button_mark_done()
            else:
                res=obj.with_context(skip_backorder=True, mo_ids_to_backorder=obj.id).button_mark_done()
            return res
            # if res!=True and 'name' in res:
            #     obj.qty_producing=0
            #     err="La nomenclature de l'article ne correspond plus a la nomenclature de l'OF"
            #     return err
            #     #res["err"]=err
            #     #return {"err": err}
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
        self.action_creer_etiquette_mrp()
        res=""
        for obj in self:
            for line in obj.etiquette_ids:
                res+=line.generer_etiquette_livraison()
        self.env['is.tracabilite.reception'].imprimer_etiquette(res)



    # def planifier_operation_action(self):
    #     for obj in self:
    #         if obj.state in ["confirmed","ready","in_production"]:
    #             ops = self.env["mrp.production.workcenter.line"].search([("production_id","=",obj.id),("state","in",["draft","pause","startworking"])],order="production_id,sequence")
    #             if ops:
    #                 ops[0].is_date_debut = obj.is_date_planifiee
    #                 ops[0].planifier_operation_action()


    # def copy(self):
    #     if default is None:
    #         default = {}
    #     default.update(generer_etiquette=False)
    #     return super(mrp_production, self).copy(cr, uid, id, default, context)
    
    
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
            if production.bom_id:
                production.consumption = production.bom_id.consumption
            if not production.move_raw_ids:
                raise UserError(_("Add some materials to consume before marking this MO as to do."))
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

            #print("## desactivation _trigger_scheduler => Ne pas générer de commande d'achat lors de la validation => Fait le 15/06/22")
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





