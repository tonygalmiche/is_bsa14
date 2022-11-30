# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import Warning
import datetime


class is_ordre_travail(models.Model):
    _name='is.ordre.travail'
    _description='Ordre de travail'
    _inherit = ['mail.thread']
    _order='name desc'

    name                = fields.Char("N°", readonly=True)
    createur_id         = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation       = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    production_id       = fields.Many2one('mrp.production', 'Ordre de production', required=True)
    quantite            = fields.Float('Qt prévue', digits=(14,2))
    date_prevue         = fields.Datetime('Date prévue' , related='production_id.date_planned_start')
    bom_id              = fields.Many2one('mrp.bom', 'Nomenclature', related='production_id.bom_id')
    state               = fields.Selection([
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
        ], "État", default='encours')
    line_ids            = fields.One2many('is.ordre.travail.line', 'ordre_id', 'Lignes')
    planning            = fields.Char("Planning", store=True, readonly=True, compute='_compute_planning')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.ordre.travail')
        res = super(is_ordre_travail, self).create(vals)
        return res


    @api.onchange('quantite')
    def onchange_quantite(self):
        for obj in self:
            for line in obj.line_ids:
                line.duree_totale=obj.quantite*line.duree_unitaire


    @api.depends('line_ids')
    def _compute_planning(self):
        for obj in self:
            html='<div style="height:2000px"/>'
            height=22
            top=left=0
            color=""
            for line in obj.line_ids:
                if color=="orange":
                    color="LightGreen"
                else:
                    color="orange"
                height
                width=line.duree_totale*50
                name=line.name
                title="Durée: %sH, Début: %s, Fin: %s"%(
                    round(line.duree_totale,1),
                    line.heure_debut.strftime("%m/%d/%Y, %HH"),
                    line.heure_fin.strftime("%m/%d/%Y, %HH")
                )
                html+="""
                    <div style="
                        background-color:%s;
                        width:%spx;
                        height:%spx;
                        position:absolute;left:%spx;top:%spx;
                        border-top: 1px solid gray;
                        border-bottom: 1px solid gray;
                    "/>
                """%(color,width,height,left,top)

                html+="""
                    <div 
                        title="%s"
                        style="
                            height:%spx;
                            position:absolute;left:%spx;top:%spx;
                            font-weight:bold;
                        ">
                        %s
                    </div>
                """%(title,height,(left+2),top,name)


                left+=width
                top+=height

            obj.planning=html




class is_ordre_travail_line(models.Model):
    _name='is.ordre.travail.line'
    _description='Ligne Ordre de travail'
    _order='sequence'

    ordre_id       = fields.Many2one('is.ordre.travail', 'Ordre de travail', required=True, ondelete='cascade')
    name           = fields.Char("Opération"                               , required=True)
    sequence       = fields.Integer("Séquence"                             , required=True)
    workcenter_id  = fields.Many2one('mrp.workcenter', 'Poste de Travail'  , required=True)
    duree_unitaire = fields.Float("Durée unitaire (H)"                     , required=True)
    duree_totale   = fields.Float("Durée totale (H)"                       , required=True)
    heure_debut    = fields.Datetime("Heure début"                         , required=False)
    heure_fin      = fields.Datetime("Heure fin"                           , required=False)
