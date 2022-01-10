# -*- coding: utf-8 -*-
from odoo import models,fields,api


class stock_picking(models.Model):
    _inherit = "stock.picking"

    @api.depends("move_lines")
    def compute_montant_total(self):
        for obj in self:
            montant = 0
            # for line in obj.move_lines:
            #     price_unit = line.procurement_id.sale_line_id.price_unit
            #     if price_unit:
            #         montant+=price_unit*line.product_uom_qty
            obj.is_montant_total = montant


    @api.depends("move_lines")
    def compute_trace_reception(self):
        for obj in self:
            trace = False
            if obj.picking_type_code=="incoming":
                for line in obj.move_lines:
                    if line.product_id.is_trace_reception:
                        trace = True
            obj.is_trace_reception = trace


    is_commentaire     = fields.Text(string="Commentaire pour le client")
    is_date_bl         = fields.Date("Date BL")
    is_montant_total   = fields.Float("Montant Total HT"           , compute="compute_montant_total"  , readonly=True, store=False)
    is_trace_reception = fields.Boolean("Traçabilité en réception", compute="compute_trace_reception", readonly=True, store=False)

    etiquette_reception_ids = fields.Many2many('is.tracabilite.reception', 'stock_picking_tacabilite_reception_rel', 'picking_id', 'etiquette_id', 'Etiquettes réception', readonly=True, copy=False)
    etiquette_livraison_ids = fields.Many2many('is.tracabilite.livraison', 'stock_picking_tacabilite_livraison_rel', 'picking_id', 'etiquette_id', 'Etiquettes livraison', readonly=True, copy=False)
    
 
    def write(self, vals):
        res=super(stock_picking, self).write(vals)
        if self.date_done and not self.is_date_bl:
            self.is_date_bl=self.date_done
        return res


    def f(self,x):
        return x.replace("\n","<br />")