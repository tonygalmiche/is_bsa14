# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    is_destinataires = fields.Text(
        string="Destinataires",
        help="Liste des destinataires avec leurs noms et emails au moment de l'envoi du message"
    )

    @api.model
    def create(self, vals):
        """
        Surcharge pour capturer les destinataires réels au moment de la création du message
        """
        # Récupérer les destinataires avant la création du message
        destinataires_info = self._get_recipients_info(vals)
        
        # Ajouter l'information des destinataires aux valeurs
        if destinataires_info:
            vals['is_destinataires'] = destinataires_info
        
        # Appeler la méthode parent pour créer le message
        return super(MailMessage, self).create(vals)

    def _get_recipients_info(self, vals):
        """
        Récupère les informations complètes des destinataires (nom + email)
        """
        destinataires_list = []
        
        # Récupérer les partner_ids depuis les valeurs en gérant les commandes ORM
        partner_ids = self._extract_ids_from_commands(vals.get('partner_ids', []))
        
        if partner_ids:
            # Récupérer les informations des partenaires
            partners = self.env['res.partner'].browse(partner_ids)
            
            for partner in partners:
                if partner.exists():
                    name = partner.name or 'Sans nom'
                    email = partner.email or 'Pas d\'email'
                    destinataires_list.append(f"{name} <{email}>")
        
        # Récupérer aussi les channel_ids si présents
        channel_ids = self._extract_ids_from_commands(vals.get('channel_ids', []))
        if channel_ids:
            channels = self.env['mail.channel'].browse(channel_ids)
            for channel in channels:
                if channel.exists():
                    destinataires_list.append(f"Canal: {channel.name}")
        
        # Retourner la liste formatée
        if destinataires_list:
            return '\n'.join(destinataires_list)
        else:
            return False

    def _extract_ids_from_commands(self, commands):
        """
        Extrait les IDs depuis les commandes ORM Odoo
        """
        ids = []
        
        if not commands:
            return ids
            
        for command in commands:
            if isinstance(command, int):
                # ID simple
                ids.append(command)
            elif isinstance(command, (list, tuple)) and len(command) >= 2:
                # Commande ORM
                if command[0] == 4:  # (4, id) - add existing record
                    ids.append(command[1])
                elif command[0] == 6 and len(command) >= 3:  # (6, 0, [ids]) - replace all
                    if isinstance(command[2], list):
                        ids.extend(command[2])
                elif command[0] == 5:  # (5,) - remove all
                    ids = []
                elif command[0] == 3:  # (3, id) - remove specific
                    if command[1] in ids:
                        ids.remove(command[1])
        
        return ids

    def action_init_destinataires(self):
        """
        Action serveur pour initialiser le champ is_destinataires 
        avec les partner_ids si le champ est vide
        """
        for message in self:
            # Ne traiter que si le champ is_destinataires est vide
            if not message.is_destinataires and message.partner_ids:
                destinataires_list = []
                
                for partner in message.partner_ids:
                    if partner.exists():
                        name = partner.name or 'Sans nom'
                        email = partner.email or 'Pas d\'email'
                        destinataires_list.append(f"{name} <{email}>")
                
                # Ajouter aussi les canaux si présents
                if message.channel_ids:
                    for channel in message.channel_ids:
                        if channel.exists():
                            destinataires_list.append(f"Canal: {channel.name}")
                
                # Mettre à jour le champ
                if destinataires_list:
                    message.is_destinataires = '\n'.join(destinataires_list)
        
        return True