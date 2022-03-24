from odoo import models,fields,api,tools, SUPERUSER_ID


class mrp_production(models.Model):
    _inherit = "mrp.production"
    _order = "id desc"

    date_planned          = fields.Datetime("Date plannifiée", required=False, index=True, readonly=False, states={}, copy=False)
    is_date_prevue        = fields.Date("Date prévue commande client", related="is_sale_order_line_id.is_date_prevue", readonly=True, help="Date de prévue sur la ligne de commande client")
    is_date_planifiee     = fields.Date("Date planifiée début")
    is_date_planifiee_fin = fields.Date("Date planifiée fin", readonly=True)
    is_ecart_date         = fields.Integer("Ecart date", readonly=True)
    is_gabarit_id         = fields.Many2one("is.gabarit", "Gabarit")
    is_sale_order_line_id = fields.Many2one("sale.order.line", "Ligne de commande")
    is_sale_order_id      = fields.Many2one("sale.order", "Commande", related="is_sale_order_line_id.order_id", readonly=True)
    generer_etiquette     = fields.Boolean('Etiquettes générées', default=False, copy=False)
    #etiquette_ids        = fields.Many2many('is.tracabilite.livraison', 'mrp_production_tacabilite_livraison_rel', 'production_id', 'etiquette_id', 'Etiquettes', readonly=True, copy=False)
    etiquette_ids         = fields.One2many('is.tracabilite.livraison', 'production_id', 'Etiquettes', copy=False)
    is_gestion_lot        = fields.Boolean('Gestion par lots')
    

    def declarer_une_fabrication_action(self):
        err=""
        for obj in self:
            qt=1
            if obj.is_gestion_lot:
                qt=obj.product_qty
            obj.qty_producing=qt
            for move in obj.move_raw_ids:
                move.quantity_done = move.should_consume_qty
            if obj.qty_producing == obj.product_qty:
                obj.with_context(skip_backorder=True).button_mark_done()
            else:
                obj.with_context(skip_backorder=True, mo_ids_to_backorder=obj.id).button_mark_done()

        if err!="":
            return {"err": err}
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



    def planifier_operation_action(self):
        for obj in self:
            if obj.state in ["confirmed","ready","in_production"]:
                ops = self.env["mrp.production.workcenter.line"].search([("production_id","=",obj.id),("state","in",["draft","pause","startworking"])],order="production_id,sequence")
                if ops:
                    ops[0].is_date_debut = obj.is_date_planifiee
                    ops[0].planifier_operation_action()


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
    



    # def action_close_mo(self):
    #     return self.mrp_production_ids.with_context(skip_backorder=True).button_mark_done()

    # def action_backorder(self):
    #     mo_ids_to_backorder = self.mrp_production_backorder_line_ids.filtered(lambda l: l.to_backorder).mrp_production_id.ids
    #     return self.mrp_production_ids.with_context(skip_backorder=True, mo_ids_to_backorder=mo_ids_to_backorder).button_mark_done()


    # def is_act_mrp_declarer_produit(self):
    #     err=""
    #     for obj in self:
    #         qt=1
    #         if obj.is_gestion_lot:
    #             qt=obj.product_qty
    #         obj.qty_producing=qt

    #         #res=obj.button_mark_done()
    #         print(obj,obj.qty_producing)

    #         for move in obj.move_raw_ids:
    #             move.quantity_done = move.should_consume_qty
    #             print(move, move.product_uom_qty, move.product_qty, move.quantity_done, move.should_consume_qty)

    #         #Sans créer de relicat
    #         res=obj.with_context(skip_backorder=True).button_mark_done()

    #         #Avec un relicat
    #         #mo_ids_to_backorder = self.mrp_production_backorder_line_ids.filtered(lambda l: l.to_backorder).mrp_production_id.ids
    #         #return self.mrp_production_ids.with_context(skip_backorder=True, mo_ids_to_backorder=mo_ids_to_backorder).button_mark_done()

    #         #res=obj.with_context(skip_backorder=True, mo_ids_to_backorder=[obj.id]).button_mark_done()

    #         #res=obj.with_context(skip_backorder=True).button_mark_done()
    #         #print("res=",res)

    #     if err!="":
    #         return {"err": err}
    #     return True



        # production = self.browse(cr, uid, ids[0], context=context)
        # if production.state == 'confirmed':
        #     self.force_production(cr, uid, ids, {})
        
        # wiz = self.get_wizard(cr, uid, production, context)
        # qt=1
        # if production.is_gestion_lot:
        #     qt=production.product_qty

        # self.action_produce(cr, uid, ids[0], qt, 'consume_produce', wiz, context=context)
        # return {}
    




# class mrp_production_workcenter_line(models.Model):
#     _inherit = "mrp.production.workcenter.line"

#     @api.depends("is_temps_passe_ids")
#     def compute_temps_passe(self):
#         for obj in self:
#             temps_passe = 0
#             ecart = 0
#             for line in obj.is_temps_passe_ids:
#                 temps_passe+=line.temps_passe
#             obj.is_temps_passe = temps_passe
#             obj.is_ecart       = obj.hour - temps_passe


#     @api.depends("is_date_debut")
#     def compute_charge(self):
#         for obj in self:
#             lines = self.env["is.mrp.workcenter.temps.ouverture"].search([("workcenter_id","=",obj.workcenter_id.id),("date_ouverture","=",obj.is_date_debut)])
#             charge = 0
#             for line in lines:
#                 charge = line.charge
#             obj.is_charge = charge


#     @api.depends("production_id")
#     def compute_product_id(self):
#         for obj in self:
#             obj.is_product_id = obj.production_id.product_id.id


#     is_product_id      = fields.Many2one("product.product", "Article", compute="compute_product_id", readonly=True, store=True)
#     is_commentaire     = fields.Text("Commentaire")
#     is_temps_passe_ids = fields.One2many("is.workcenter.line.temps.passe"  , "workcenter_line_id", u"Temps passé")
#     is_temps_passe     = fields.Float("Temps passé", compute="compute_temps_passe", readonly=True, store=True)
#     is_ecart           = fields.Float("Ecart", compute="compute_temps_passe", readonly=True, store=True)
#     is_offset          = fields.Integer("Offset (jour)", help="Offset en jours par rapport à l'opération précédente pour le calcul du planning")
#     is_date_debut      = fields.Date("Date de début opération", index=True)
#     is_date_fin        = fields.Date("Date de fin opération")

#     is_date_prevue_cde    = fields.Date("Date prévue commande client", related="production_id.is_date_prevue"    , readonly=True)
#     is_date_planifiee_fin = fields.Date("Date planifiée fin"         , related="production_id.is_date_planifiee_fin", readonly=True)
#     is_ecart_date         = fields.Integer("Ecart date"              , related="production_id.is_ecart_date"        , readonly=True)
#     is_charge             = fields.Float(u"Charge (%)"         , compute="compute_charge", readonly=True, store=False, help="Charge pour la date de début de l'opération")


#     def write(self, vals, update=True):
#         if len(vals)==2 and "date_finished" in vals and "date_start" in vals:
#             d = datetime.strptime(vals["date_start"], "%Y-%m-%d %H:%M:%S")
#             vals["is_date_debut"] =  str(d)[:10]
#             if self.is_offset:
#                 offset = self.is_offset
#                 d = d + timedelta(days=offset)
#             vals["is_date_fin"] =  str(d)[:10]




#         res=super(mrp_production_workcenter_line, self).write(vals, update=update)


#         if "is_date_debut" in vals:
#             self.workcenter_id.calculer_charge_action()


#         return res



#     def planifier_operation_action(self):
#         for obj in self:
#             date_debut = False
#             date_fin=False
#             if obj.is_date_debut:
#                 filtre=[
#                     ("production_id","=",obj.production_id.id),
#                     ("sequence",">",obj.sequence),
#                     ("id","!=",obj.id),
#                 ]
#                 ops = self.env["mrp.production.workcenter.line"].search(filtre,order="sequence")
#                 d = datetime.strptime(obj.is_date_debut, "%Y-%m-%d")
#                 if str(d)[:10]<str(date.today()):
#                     d = datetime.now()
#                 for op in ops:
#                     date_debut = str(d)[:10]
#                     offset = op.is_offset
#                     d = d + timedelta(days=offset)
#                     dates=[]
#                     for line in op.workcenter_id.is_temps_ouverture_ids:
#                         dates.append(str(line.date_ouverture))
#                     date_fin=False
#                     d2=d
#                     for x in range(50):
#                         if str(d2)[:10] in dates:
#                             date_fin = str(d2)[:10]
#                             break
#                         else:
#                             d2 = d2 + timedelta(days=1)
#                     if not date_fin:
#                         raise Warning("Aucune date d'ouverture disponible pour le poste de charge "+op.workcenter_id.name+" et pour le "+d.strftime("%d/%m/%Y"))
#                     d=d2
#                     vals={
#                         "is_date_debut": date_debut,
#                         "is_date_fin"  : date_fin,
#                         "date_start"   : str(date_debut) + " 07:00:00",
#                         "date_finished": str(date_debut) + " 16:00:00",
#                     }
#                     op.write(vals)


#             if date_fin:
#                 obj.production_id.is_date_planifiee_fin = date_fin
#                 if date_fin and obj.production_id.is_date_prevue:
#                     d1 = datetime.strptime(date_fin, "%Y-%m-%d")
#                     d2 = datetime.strptime(obj.production_id.is_date_prevue, "%Y-%m-%d")
#                     ecart = (d2-d1).days
#                     obj.production_id.is_ecart_date = ecart

