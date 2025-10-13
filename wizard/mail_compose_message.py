# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    recipients_info = fields.Html(
        string="Information destinataires", 
        compute='_compute_recipients_info',
        help="Affiche la liste des destinataires avec leurs emails"
    )



    @api.model
    def default_get(self, fields_list):
        """Surcharge pour supprimer les abonnés du document"""
        context = self.env.context or {}
        model_name = context.get('default_model')
        res_id = context.get('default_res_id')
        
        # Supprimer les abonnés du document si présent
        if model_name and res_id:
            try:
                document = self.env[model_name].browse(res_id)
                if hasattr(document, 'message_follower_ids'):
                    document.message_follower_ids.unlink()
            except Exception:
                pass
        
        # Appeler la méthode parent
        result = super(MailComposer, self).default_get(fields_list)
        
        # Détecter appel automatique : custom_layout = None pour les appels automatiques
        # Les appels automatiques d'Odoo ont custom_layout: None
        # Les appels manuels ont une valeur dans custom_layout
        is_automatic = context.get('custom_layout') is None
        
        # Gestion des destinataires selon le type d'appel
        if is_automatic:
            # Appel automatique - pas de destinataires
            result['partner_ids'] = []
        else:
            # Appel manuel - ajouter le destinataire principal
            if model_name and res_id:
                try:
                    document = self.env[model_name].browse(res_id)
                    if hasattr(document, 'partner_id') and document.partner_id:
                        result['partner_ids'] = [(6, 0, [document.partner_id.id])]
                except Exception:
                    pass
                
        return result

    @api.model
    def get_record_data(self, values):
        """Surcharge pour supprimer les abonnés automatiques seulement pour les appels automatiques"""
        result = super(MailComposer, self).get_record_data(values)
        
        # Détecter appel automatique via le contexte
        context = self.env.context or {}
        is_automatic = context.get('custom_layout') is None
        
        # Vider les destinataires seulement pour les appels automatiques
        if is_automatic:
            result['partner_ids'] = []
            
        return result

    @api.onchange('template_id')
    def _onchange_template_id_clear_followers(self):
        """Supprime automatiquement les abonnés lors du changement de template"""
        # Supprimer les destinataires ajoutés automatiquement
        if self.template_id:
            # Le template va ajouter les abonnés, on les supprime immédiatement
            self.partner_ids = [(5, 0, 0)]

    @api.onchange('model', 'res_id')
    def _onchange_model_res_id_clear_followers(self):
        """Supprime automatiquement les abonnés du document"""
        if self.model and self.res_id:
            try:
                document = self.env[self.model].browse(self.res_id)
                
                # Supprimer les abonnés du document
                if hasattr(document, 'message_follower_ids'):
                    document.message_follower_ids.unlink()
                
                # Ajouter le destinataire principal pour les appels manuels
                # (les appels automatiques n'arrivent jamais ici)
                if hasattr(document, 'partner_id') and document.partner_id:
                    self.partner_ids = [(6, 0, [document.partner_id.id])]
                else:
                    self.partner_ids = [(5, 0, 0)]
                    
            except Exception:
                self.partner_ids = [(5, 0, 0)]

    @api.depends('partner_ids', 'model', 'res_id')
    def _compute_recipients_info(self):
        """Calcule la liste des destinataires avec leurs emails pour affichage"""
        for wizard in self:
            html_content = []
            
            # Récupérer les abonnés du document si on a un modèle et un ID
            if wizard.model and wizard.res_id:
                document = wizard.env[wizard.model].browse(wizard.res_id)
                if hasattr(document, 'message_follower_ids'):
                    followers = document.message_follower_ids
                    if followers:
                        html_content.append("<div style='margin-bottom: 10px;'>")
                        html_content.append("<strong>👥  Abonnés du document :</strong>")
                        html_content.append("<ul style='margin: 5px 0; padding-left: 20px;'>")
                        
                        for follower in followers:
                            partner = follower.partner_id
                            if partner:
                                html_content.append(f"<li>")
                                html_content.append(f"<strong>{partner.name}</strong>")
                                if partner.email:
                                    html_content.append(f" - <span style='color: #28a745;'>{partner.email}</span>")
                                else:
                                    html_content.append(f" - <span style='color: #dc3545;'>❌ Pas d'email</span>")
                                html_content.append("</li>")
                        
                        html_content.append("</ul>")
                        html_content.append("</div>")
            
            # Afficher les destinataires supplémentaires sélectionnés
            if wizard.partner_ids:
                html_content.append("<div style='margin-bottom: 10px;'>")
                html_content.append("<strong>👥  Destinataires :</strong>")
                html_content.append("<ul style='margin: 5px 0; padding-left: 20px;'>")
                
                for partner in wizard.partner_ids:
                    html_content.append(f"<li>")
                    html_content.append(f"<strong>{partner.name}</strong>")
                    if partner.email:
                        html_content.append(f" - <span style='color: #28a745;'>{partner.email}</span>")
                    else:
                        html_content.append(f" - <span style='color: #dc3545;'>❌ Pas d'email</span>")
                    html_content.append("</li>")
                
                html_content.append("</ul>")
                html_content.append("</div>")
            
            # Si aucun destinataire
            if not html_content:
                html_content.append("<div style='color: #6c757d; font-style: italic;'>")
                html_content.append("📭 Aucun destinataire sélectionné")
                html_content.append("</div>")
            
            wizard.recipients_info = "".join(html_content)

    def action_add_all_followers(self):
        """Ajoute tous les abonnés du document comme destinataires"""
        if self.model and self.res_id:
            document = self.env[self.model].browse(self.res_id)
            if hasattr(document, 'message_follower_ids'):
                # Récupérer les partners des abonnés qui ont un email
                follower_partners = document.message_follower_ids.mapped('partner_id').filtered('email')
                # Ajouter ces partners aux destinataires existants
                current_partners = self.partner_ids.ids
                new_partners = list(set(current_partners + follower_partners.ids))
                self.partner_ids = [(6, 0, new_partners)]
        return True

    def action_clear_recipients(self):
        """Supprime tous les destinataires supplémentaires"""
        self.partner_ids = [(5, 0, 0)]
        return True