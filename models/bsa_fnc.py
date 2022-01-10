# -*- coding: utf-8 -*-

from odoo import models,fields,api
from odoo.exceptions import Warning
import datetime
import html2text


class bsa_fnc_categorie(models.Model):
    _name='bsa.fnc.categorie'
    _description='bsa.fnc.categorie'
    _order='name'

    name = fields.Char(u"Catégorie", required=True)


class bsa_fnc(models.Model):
    _name='bsa.fnc'
    _description='bsa.fnc'
    _inherit = ['mail.thread']
    _order='name desc'

    name            = fields.Char("N°", readonly=True)
    createur_id     = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation   = fields.Date("Date de création", required=True, default=lambda *a: fields.Date.today())
    type_fnc            = fields.Selection([
                        ('interne'     , 'Interne'),
                        ('client'      , 'Client'),
                        ('fournisseur' , 'Fournisseur'),
                        ('amelioration', 'Amélioration'),
                    ], "Type", required=True)
    partner_id          = fields.Many2one('res.partner', u'Partenaire', help='Client ou Fournisseur', required=True)
    ref_partenaire      = fields.Char(u"Référence partenaire")
    categorie_id        = fields.Many2one('bsa.fnc.categorie', u'Catégorie')
    product_id          = fields.Many2one('product.product', u'Article')
    rsp_projet_id       = fields.Many2one('res.users', u'Responsable de projet')
    date_projet         = fields.Date(u"Date du projet")
    description         = fields.Text(u"Description du problème")
    demande_bsa         = fields.Text(u"Demande de BSA")
    action              = fields.Text(u"Action immédiate")
    analyse             = fields.Text(u"Analyse")
    resolution          = fields.Text(u"Action corrective")
    date_reponse        = fields.Date(u"Date de réponse")
    evaluation          = fields.Text(u"Évaluation")
    date_evaluation     = fields.Date(u"Date évaluation")
    evaluateur_id       = fields.Many2one('res.users', u'Evaluateur')
    cout                = fields.Integer(u"Avoir")
    attachment_ids      = fields.Many2many('ir.attachment', 'bsa_fnc_attachment_rel', 'bsa_fnc_id', 'attachment_id', u'Pièces jointes')
    state               = fields.Selection([
                        ('ouverte', 'Ouverte'),
                        ('encours', 'En cours'),
                        ('fermee' , 'Fermée'),
                    ], "État", default='ouverte')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('bsa.fnc')
        res = super(bsa_fnc, self).create(vals)
        return res


    def action_send_mail(self):
        cr=self._cr
        uid=self._uid
        ids=self._ids

        for obj in self:
            ir_model_data = self.pool.get('ir.model.data')
            try:
                template_id = ir_model_data.get_object_reference(cr, uid, 'is_bsa', 'bsa_fnc_email_template4')[1]
            except ValueError:
                template_id = False
            try:
                compose_form_id = ir_model_data.get_object_reference(cr, uid, 'is_bsa', 'is_email_compose_message_wizard_form')[1]
            except ValueError:
                compose_form_id = False 
            ctx = dict()

            attachment_ids=[]
            for attachment in obj.attachment_ids:
                attachment_ids.append(attachment.id)
            vals={
                'attachment_ids': [(6, 0, attachment_ids)]
            }
            attachment_selection_ids=[]
            attachment_selection_ids.append(vals)
            ctx.update({
                'default_model': 'bsa.fnc',
                'default_res_id': obj.id,
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_attachment_selection_ids': attachment_selection_ids,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True
            })
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(compose_form_id, 'form')],
                'view_id': compose_form_id,
                'target': 'new',
                'context': ctx,
            }


    def message_new(self, cr, uid, msg_dict, custom_values=None, context=None):
        """Méthode provenant par surcharge de mail.tread permettant de personnaliser la création de la fnc lors de la réception d'un mail avec le serveur de courrier entrant créé"""
        if context is None:
            context = {}
        data = {}
        if isinstance(custom_values, dict):
            data = custom_values.copy()
        model = context.get('thread_model') or self._name
        model_pool = self.pool[model]
        fields = model_pool.fields_get(cr, uid, context=context)
        if 'name' in fields and not data.get('name'):
            data['name'] = msg_dict.get('subject', '')

        ref_partenaire = msg_dict.get('email_from', '')

        description = ''
        if msg_dict.get('body'):
            html = msg_dict.get('body')
            description = html2text.html2text(html)

        data['type_fnc']       = 'interne'
        data['partner_id']     = 1
        data['ref_partenaire'] = ref_partenaire
        data['description']    = description

        res_id = model_pool.create(cr, uid, data, context=context)
        return res_id

