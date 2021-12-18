# -*- coding: utf-8 -*-
from odoo import models,fields,api


class account_move_line(models.Model):
    _inherit = "account.move.line"
    _order='is_stock_move_id,sequence,id'


    @api.depends('debit','credit')
    def _compute_is_solde(self):
        for obj in self:
            obj.is_solde = obj.credit - obj.debit

    is_solde         = fields.Float("Solde", store=True, readonly=True, compute='_compute_is_solde')
    is_stock_move_id = fields.Many2one('stock.move', string='Stock Move')

