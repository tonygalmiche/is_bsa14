# -*- coding: utf-8 -*-
from odoo import models,fields,api


class stock_picking(models.Model):
    _inherit = "stock.picking"

    @api.depends("move_lines")
    def compute_montant_total(self):
        for obj in self:
            montant = 0
            for line in obj.move_lines:
                if line.sale_line_id:
                    price_unit = line.sale_line_id.price_unit or 0
                    discount = line.sale_line_id.discount or 0
                    montant+=(price_unit-(discount/100)*price_unit)*line.product_uom_qty
                if line.purchase_line_id:
                    price_unit = line.purchase_line_id.price_unit or 0
                    montant+=price_unit*line.purchase_line_id.product_qty
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
    
 
    def f(self,x):
        return x.replace("\n","<br />")


    def livraisons_a_facturer_action(self):
        filtre=[
            ('picking_type_id', '=', 2),
            ('state'          , '=', 'done')
        ]
        pickings=self.env['stock.picking'].search(filtre)
        picking_ids=[]
        for picking in pickings:
            for move in picking.move_ids_without_package:
                if move.state=='done':
                    if not move.is_account_move_line_id:
                        if move.picking_id.id not in picking_ids:
                            picking_ids.append(move.picking_id.id)
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action['domain'] = [('id', 'in',picking_ids)]
        return action


    def receptions_a_facturer_action(self):
        filtre=[
            ('picking_type_id', '=', 1),
            ('state'          , '=', 'done')
        ]
        pickings=self.env['stock.picking'].search(filtre)
        picking_ids=[]
        for picking in pickings:
            for move in picking.move_ids_without_package:
                if not move.is_account_move_line_id:
                    if move.picking_id.id not in picking_ids:
                        picking_ids.append(move.picking_id.id)
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action['domain'] = [('id', 'in',picking_ids)]
        return action


    def facturation_picking_action(self):
        action=False
        picking_type_id=False
        for obj in self:
            picking_type_id = obj.picking_type_id.id
        if picking_type_id==1:
            action = self.facturation_reception_action()
        if picking_type_id==2:
            action = self.facturation_livraison_action()
        return action


    def facturation_reception_action(self):
        cr=self._cr
        partners=[]
        invoice_ids=[]
        for obj in self:
            for move in obj.move_ids_without_package:
                if not move.is_account_move_line_id:
                    partner = move.picking_id.partner_id
                    if partner not in partners:
                        partners.append(partner)
 
        for partner in partners:
            lines=[]
            for obj in self:
                for move in obj.move_ids_without_package:
                    if not move.is_account_move_line_id and move.state=="done" and partner == move.picking_id.partner_id:
                        account_id = move.product_id.property_account_income_id.id or move.product_id.categ_id.property_account_income_categ_id.id
                        vals={
                            "product_id"       : move.product_id.id,
                            "name"             : move.purchase_line_id.name,
                            "display_type"     : False,
                            "account_id"       : account_id,
                            "quantity"         : move.product_uom_qty,
                            "tax_ids"          : move.purchase_line_id.taxes_id,
                            "price_unit"       : move.purchase_line_id.price_unit,
                            "is_stock_move_id" : move.id, 
                            "product_uom_id"   : move.product_uom.id,
                            "purchase_line_id" : move.purchase_line_id.id,
                            "purchase_order_id": move.purchase_line_id.order_id.id,
                        }


                        
                        lines.append((0, 0, vals))
            vals={
                "partner_id": partner.id,
                "move_type" : "in_invoice",
                "journal_id": 2,
                "invoice_line_ids": lines,
            }
            if len(lines)>0:
                invoice = self.env['account.move'].create(vals)
                invoice._onchange_partner_id()
                invoice_ids.append(invoice.id)
                for line in invoice.invoice_line_ids:
                    line.is_stock_move_id.is_account_move_line_id = line.id
                #     order_id   = line.is_stock_move_id.purchase_line_id.order_id.id
                #     invoice_id = line.move_id.id
                #     SQL="""
                #         INSERT INTO account_move_purchase_order_rel (purchase_order_id, account_move_id) VALUES (%s, %s)
                #         ON CONFLICT DO NOTHING
                #     """
                #     res = cr.execute(SQL,[order_id, invoice_id])
                for line in invoice.invoice_line_ids:
                    line.is_stock_move_id.purchase_line_id._compute_qty_invoiced()



        # Affichage des factures **********************************************
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in',invoice_ids)]
        elif len(invoice_ids) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'in_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': invoice.partner_id.id,
                'default_partner_shipping_id': invoice.partner_shipping_id.id,
                'default_invoice_payment_term_id': invoice.invoice_payment_term_id.id or invoice.partner_id.property_payment_term_id.id or invoice.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
                'default_invoice_origin': invoice.mapped('name'),
                'default_user_id': invoice.user_id.id,
            })
        action['context'] = context
        return action









    def facturation_livraison_action(self):
        cr=self._cr
        partners=[]
        invoice_ids=[]
        for obj in self:
            for move in obj.move_ids_without_package:
                if not move.is_account_move_line_id:
                    #partner = move.picking_id.partner_id
                    partner = move.sale_line_id.order_id.partner_invoice_id or move.picking_id.partner_id
                    if partner not in partners:
                        partners.append(partner)
 
        for partner in partners:
            lines=[]
            partner_shipping_id=partner
            for obj in self:
                for move in obj.move_ids_without_package:
                    partner_shipping_id = move.sale_line_id.order_id.partner_shipping_id
                    partner_invoice = move.sale_line_id.order_id.partner_invoice_id or move.picking_id.partner_id

                    #if not move.is_account_move_line_id and move.state=="done" and partner == move.picking_id.partner_id:
                    if not move.is_account_move_line_id and move.state=="done" and partner == partner_invoice:

                        partner_shipping_id = obj.partner_id

                        account_id = move.product_id.property_account_income_id.id or move.product_id.categ_id.property_account_income_categ_id.id
                        vals={
                            "product_id"      : move.product_id.id,
                            "name"            : move.sale_line_id.name,
                            "display_type"    : False,
                            "account_id"      : account_id,
                            "quantity"        : move.product_uom_qty,
                            "tax_ids"         : move.sale_line_id.tax_id,
                            "price_unit"      : move.sale_line_id.price_unit,
                            "discount"        : move.sale_line_id.discount,
                            "is_stock_move_id": move.id, 
                            "product_uom_id"  : move.product_uom.id,
                        }
                        lines.append((0, 0, vals))
            vals={
                "partner_id"         : partner.id,
                #"partner_shipping_id": partner_shipping_id.id,
                "move_type"          : "out_invoice",
                "journal_id"         : 1,
                "invoice_line_ids"   : lines,
            }
            if len(lines)>0:
                invoice = self.env['account.move'].create(vals)
                invoice._onchange_partner_id()
                invoice_ids.append(invoice.id)
                for line in invoice.invoice_line_ids:
                    line.is_stock_move_id.is_account_move_line_id = line.id
                    order_line_id   = line.is_stock_move_id.sale_line_id.id
                    invoice_line_id = line.id
                    SQL="""
                        INSERT INTO sale_order_line_invoice_rel (invoice_line_id, order_line_id) VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """
                    res = cr.execute(SQL,[invoice_line_id, order_line_id])
                for line in invoice.invoice_line_ids:
                    line.is_stock_move_id.sale_line_id._get_invoice_qty()
                invoice.partner_shipping_id = partner_shipping_id.id



        # Affichage des factures **********************************************
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in',invoice_ids)]
        elif len(invoice_ids) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': invoice.partner_id.id,
                'default_partner_shipping_id': invoice.partner_shipping_id.id,
                'default_invoice_payment_term_id': invoice.invoice_payment_term_id.id or invoice.partner_id.property_payment_term_id.id or invoice.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
                'default_invoice_origin': invoice.mapped('name'),
                'default_user_id': invoice.user_id.id,
            })
        action['context'] = context
        return action







