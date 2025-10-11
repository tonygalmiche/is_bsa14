# -*- coding: utf-8 -*-

from odoo import api, models


class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.model
    def create(self, vals):
        """Intercepte la création des emails pour supprimer les abonnés mais garder les destinataires explicites"""
        # Si on a un modèle et un res_id, gérer intelligemment les destinataires
        if vals.get('model') and vals.get('res_id'):
            model_name = vals['model']
            res_id = vals['res_id']
            
            try:
                document = self.env[model_name].browse(res_id)
                if hasattr(document, 'message_follower_ids'):
                    # Récupérer les IDs des abonnés (à supprimer des destinataires)
                    follower_partner_ids = set()
                    for follower in document.message_follower_ids:
                        if follower.partner_id:
                            follower_partner_ids.add(follower.partner_id.id)
                    
                    # Récupérer le destinataire principal du document (à toujours garder)
                    main_recipient_id = None
                    if hasattr(document, 'partner_id') and document.partner_id:
                        main_recipient_id = document.partner_id.id
                    
                    # Supprimer les abonnés du document
                    followers_to_remove = document.message_follower_ids
                    if followers_to_remove:
                        followers_to_remove.unlink()
                    
                    # Filtrer les destinataires de l'email 
                    if 'recipient_ids' in vals and vals['recipient_ids']:
                        filtered_recipients = []
                        
                        if isinstance(vals['recipient_ids'], list):
                            for cmd in vals['recipient_ids']:
                                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
                                    if cmd[0] == 6:  # (6, 0, [ids])
                                        partner_ids = cmd[2] if cmd[2] else []
                                    elif cmd[0] == 4:  # (4, id)
                                        partner_ids = [cmd[1]]
                                    else:
                                        continue
                                    
                                    # Garder seulement :
                                    # 1. Le destinataire principal du document
                                    # 2. Les destinataires qui ne sont PAS des abonnés
                                    for partner_id in partner_ids:
                                        if (partner_id == main_recipient_id or 
                                            partner_id not in follower_partner_ids):
                                            filtered_recipients.append(partner_id)
                        
                        # Mettre à jour les destinataires filtrés
                        if filtered_recipients:
                            vals['recipient_ids'] = [(6, 0, list(set(filtered_recipients)))]
                        else:
                            vals['recipient_ids'] = [(5, 0, 0)]
                            
            except Exception as e:
                # En cas d'erreur, laisser passer l'email
                pass
        
        return super(MailMail, self).create(vals)

    def send(self, auto_commit=False, raise_exception=False):
        """Intercepte l'envoi d'emails pour s'assurer que les abonnés ne reçoivent pas d'email sauf s'ils sont destinataires explicites"""
        for mail in self:
            # Si on a un modèle et un res_id, vérifier les destinataires
            if mail.model and mail.res_id:
                try:
                    document = self.env[mail.model].browse(mail.res_id)
                    if hasattr(document, 'message_follower_ids'):
                        # Récupérer le destinataire principal
                        main_recipient_id = None
                        if hasattr(document, 'partner_id') and document.partner_id:
                            main_recipient_id = document.partner_id.id
                        
                        # S'il reste des abonnés, les supprimer du document
                        followers_to_remove = document.message_follower_ids
                        if followers_to_remove:
                            followers_to_remove.unlink()
                            
                        # S'assurer qu'au moins le destinataire principal est présent
                        if main_recipient_id and mail.recipient_ids:
                            current_recipients = mail.recipient_ids.ids
                            if main_recipient_id not in current_recipients:
                                # Ajouter le destinataire principal s'il n'est pas là
                                mail.recipient_ids = [(4, main_recipient_id)]
                        elif main_recipient_id and not mail.recipient_ids:
                            # Aucun destinataire, ajouter au moins le principal
                            mail.recipient_ids = [(6, 0, [main_recipient_id])]
                                
                except Exception as e:
                    # En cas d'erreur, laisser passer l'email tel quel
                    pass
        
        return super(MailMail, self).send(auto_commit=auto_commit, raise_exception=raise_exception)