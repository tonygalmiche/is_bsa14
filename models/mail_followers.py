# -*- coding: utf-8 -*-

from odoo import api, models


class MailFollowers(models.Model):
    _inherit = 'mail.followers'

    @api.model
    def create(self, vals):
        """
        Intercepte la création d'abonnés pour les supprimer automatiquement
        """
        # Ne pas créer d'abonnés du tout
        # Retourner un recordset vide pour simuler la création
        return self.browse([])

    def write(self, vals):
        """
        Intercepte la modification d'abonnés pour les supprimer
        """
        # Supprimer les abonnés au lieu de les modifier
        self.unlink()
        return True

    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     """
    #     Intercepte la recherche d'abonnés pour retourner une liste vide
    #     """
    #     # Toujours retourner une liste vide
    #     if count:
    #         return 0
    #     return self.browse([])

    # def read(self, fields=None, load='_classic_read'):
    #     """
    #     Intercepte la lecture d'abonnés pour retourner une liste vide
    #     """
    #     return []