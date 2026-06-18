# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class IsPreparationDeclarationProduction(models.Model):
    _name = 'is.preparation.declaration.production'
    _description = 'Préparation de déclaration de production'
    _order = 'id desc'
    _rec_name = 'id'
    _inherit = ['mail.thread']

    # Champs
    state = fields.Selection(
        [('en_cours', 'En cours'), ('termine', 'Terminé')],
        string="État",
        default='en_cours',
        tracking=True
    )

    etiquette_tracabilite_id = fields.Many2one(
        'is.tracabilite.livraison',
        string="Étiquette de traçabilité en livraison",
        domain=[('fabrique', '=', False), ('production_id', '!=', False)],
        tracking=True
    )
    
    production_id = fields.Many2one(
        'mrp.production',
        string="OF",
        related='etiquette_tracabilite_id.production_id',
        store=True,
        readonly=True,
        tracking=True
    )

    article_id = fields.Many2one(
        'product.template',
        string="Article",
        related='etiquette_tracabilite_id.product_id',
        store=True,
        readonly=True,
        tracking=True
    )

    is_gestion_lot = fields.Boolean(
        string="Gestion par lots",
        readonly=True,
        tracking=True
    )
    
    quantite_a_declarer = fields.Float(
        string="Quantité à déclarer",
        required=True,
        digits=(14, 2),
        default=1.0,
        tracking=True
    )
    
    operateurs_ids = fields.Many2many(
        'hr.employee',
        'is_preparation_declaration_production_operateurs_rel',
        'preparation_id',
        'operateur_id',
        string="Opérateurs",
        tracking=True
    )

    ligne_ids = fields.One2many(
        'is.preparation.declaration.production.line',
        'preparation_id',
        string="Lignes"
    )

    composant_ids = fields.One2many(
        'is.preparation.declaration.production.composant',
        'preparation_id',
        string="Composants de l'OF",
        copy=True
    )

    affichage_mobile_html = fields.Html(
        string="Affichage mobile",
        compute='_compute_affichage_mobile_html',
        readonly=True,
        sanitize=False,
    )

    @api.onchange('etiquette_tracabilite_id')
    def _onchange_etiquette_tracabilite(self):
        if self.etiquette_tracabilite_id and self.etiquette_tracabilite_id.product_id:
            self.is_gestion_lot = self.etiquette_tracabilite_id.product_id.is_gestion_lot
        else:
            self.is_gestion_lot = False
        # Effacer les lignes et composants si l'étiquette est modifiée
        self.ligne_ids = [(5, 0, 0)]
        self.composant_ids = [(5, 0, 0)]
        
        # Remplir les composants de l'OF
        if self.etiquette_tracabilite_id and self.etiquette_tracabilite_id.production_id:
            composants = []
            production = self.etiquette_tracabilite_id.production_id
            for move in production.move_raw_ids:
                if move.state not in ('cancel', 'draft'):
                    # Diviser par la quantité prévue de l'OF pour obtenir la quantité unitaire
                    quantite_unitaire = move.product_qty / production.product_qty if production.product_qty else 0.0
                    composants.append((0, 0, {
                        'product_id': move.product_id.id,
                        'quantite_prevue_unitaire': quantite_unitaire,
                    }))
            self.composant_ids = composants

    @api.depends('production_id', 'article_id', 'quantite_a_declarer', 'composant_ids',
                 'composant_ids.total_quantite_scanee', 'composant_ids.quantite_prevue',
                 'composant_ids.stock_disponible', 'operateurs_ids')
    def _compute_affichage_mobile_html(self):
        for record in self:
            html = ""

            # Section opérateurs (toujours affichée si présents)
            if record.operateurs_ids:
                noms = ", ".join(record.operateurs_ids.mapped('name'))
                html += "<div style='padding:8px; background:#e8f4f8; border-bottom:1px solid #bee5eb; margin-bottom:4px;'>"
                html += f"<strong>Opérateurs :</strong> {noms}"
                html += "</div>"

            if record.production_id and record.article_id:
                # En-tête avec OF, article et quantité
                html += "<div style='padding: 10px; background-color: #f5f5f5; border-bottom: 1px solid #ddd;'>"
                html += f"<p style='margin: 5px 0; font-weight: bold;'><strong>OF:</strong> {record.production_id.name}</p>"
                html += f"<p style='margin: 5px 0;'><strong>Article:</strong> {record.article_id.name}</p>"
                html += f"<p style='margin: 5px 0;'><strong>Quantité à déclarer:</strong> {record.quantite_a_declarer}</p>"
                html += "</div>"
                
                # Liste des composants
                html += "<div style='padding: 5px;'>"
                for composant in record.composant_ids:
                    # 4 cas de couleur
                    if composant.total_quantite_scanee == 0:
                        # Gris - Pas de scan
                        couleur_barre = '#e9ecef'
                        couleur_fond = '#f8f9fa'
                        couleur_texte = 'black'
                    elif composant.total_quantite_scanee > composant.stock_disponible:
                        # Rouge - Scan > stock
                        couleur_barre = '#dc3545'
                        couleur_fond = '#f8d7da'
                        couleur_texte = 'white'
                    elif composant.total_quantite_scanee == composant.quantite_prevue:
                        # Vert - Scan = prévu
                        couleur_barre = '#28a745'
                        couleur_fond = '#d4edda'
                        couleur_texte = 'white'
                    else:
                        # Orange - Scan < prévu
                        couleur_barre = '#ffc107'
                        couleur_fond = '#fff3cd'
                        couleur_texte = 'white'
                    
                    pourcentage = 0
                    if composant.quantite_prevue > 0:
                        pourcentage = (composant.total_quantite_scanee / composant.quantite_prevue) * 100
                    
                    pourcentage_barre = min(100, pourcentage)
                    
                    scan_str = f"{int(composant.total_quantite_scanee)}"
                    prev_str = f"{int(composant.quantite_prevue)}"
                    stock_str = f"{int(composant.stock_disponible)}"
                    
                    html += f"<div style='margin-bottom: 8px; padding: 8px; background-color: {couleur_fond}; border-radius: 5px;'>"
                    html += f"<p style='margin: 0 0 5px 0; font-weight: bold; font-size: 13px;'>{composant.product_id.name}</p>"
                    
                    # Barre de progression avec toutes les infos
                    html += f"<div style='width: 100%; background-color: #e9ecef; border-radius: 4px; overflow: visible; margin: 0;'>"
                    html += f"<div style='width: {pourcentage_barre}%; background-color: {couleur_barre}; height: 24px; display: flex; align-items: center; justify-content: flex-start; padding-left: 5px; color: {couleur_texte}; font-size: 11px; font-weight: bold; white-space: nowrap;'>"
                    html += f"{int(pourcentage)}% - Scan:{scan_str}/{prev_str} - Stock:{stock_str}</div>"
                    html += "</div>"
                    
                    html += "</div>"
                html += "</div>"

                # Lignes scannées avec bouton suppression
                if record.ligne_ids:
                    html += "<div style='padding:5px;'>"
                    html += "<p style='margin:4px 0;font-weight:bold;font-size:12px;color:#555;'>Lignes scannées :</p>"
                    for ligne in record.ligne_ids:
                        etiquette_name = ''
                        if ligne.etiquette_reception_id:
                            etiquette_name = ligne.etiquette_reception_id.name
                        elif ligne.etiquette_livraison_id:
                            etiquette_name = ligne.etiquette_livraison_id.name
                        product_name = ligne.product_id.name if ligne.product_id else ''
                        dbname = record.env.cr.dbname
                        url_suppr = (
                            "/declaration-fin-of.php?dbname=" + dbname
                            + "&preparation_id=" + str(record.id)
                            + "&action=supprimer-ligne&scan=&quantite=0"
                            + "&ligne_id=" + str(ligne.id)
                        )
                        html += (
                            f"<div style='display:flex;justify-content:space-between;"
                            f"align-items:center;padding:4px 6px;margin-bottom:3px;"
                            f"background:#fff;border:1px solid #ddd;border-radius:4px;'>"
                            f"<span style='font-size:12px;'>"
                            f"<strong>{etiquette_name}</strong> {product_name} "
                            f"| qté : {ligne.quantite_saisie:g}</span>"
                            "<a href='" + url_suppr + "' "
                            "style='color:#dc3545;font-size:1.3em;font-weight:bold;"
                            "text-decoration:none;padding:0 6px;'>&times;</a>"
                            f"</div>"
                        )
                    html += "</div>"

            record.affichage_mobile_html = html


    @api.constrains('etiquette_tracabilite_id')
    def _check_etiquette_of_not_done(self):
        # Ne pas vérifier si on est en train de copier pour le reliquat
        if self.env.context.get('skip_check_of_done'):
            return

        for record in self:
            # L'étiquette est optionnelle à la création (elle peut être renseignée plus tard)
            if not record.etiquette_tracabilite_id:
                continue
            if record.etiquette_tracabilite_id.production_id:
                production = record.etiquette_tracabilite_id.production_id
                if production.state == 'done':
                    raise ValidationError(
                        f"Impossible d'utiliser cette étiquette : l'OF {production.name} est déjà terminé."
                    )

    def action_actualiser_stocks(self):
        """Actualiser les stocks de tous les composants"""
        for composant in self.composant_ids:
            if composant.product_id:
                composant.stock_disponible = composant.product_id.qty_available
        return True

    def _fill_composants_from_etiquette(self):
        """Remplir les composants depuis l'OF de l'étiquette (appelé via mobile ou onchange)."""
        for record in self:
            if record.etiquette_tracabilite_id and record.etiquette_tracabilite_id.product_id:
                record.is_gestion_lot = record.etiquette_tracabilite_id.product_id.is_gestion_lot
            else:
                record.is_gestion_lot = False
            record.ligne_ids = [(5, 0, 0)]
            record.composant_ids = [(5, 0, 0)]
            if record.etiquette_tracabilite_id and record.etiquette_tracabilite_id.production_id:
                production = record.etiquette_tracabilite_id.production_id
                # Mettre à jour la quantité à déclarer depuis le lot de fabrication
                if record.etiquette_tracabilite_id.lot_fabrication:
                    record.quantite_a_declarer = record.etiquette_tracabilite_id.lot_fabrication
                composants = []
                for move in production.move_raw_ids:
                    if move.state not in ('cancel', 'draft'):
                        quantite_unitaire = (
                            move.product_qty / production.product_qty
                            if production.product_qty else 0.0
                        )
                        composants.append((0, 0, {
                            'product_id': move.product_id.id,
                            'quantite_prevue_unitaire': quantite_unitaire,
                        }))
                record.composant_ids = composants

    @api.model
    def mobile_scan(self, preparation_id, action, scan_value, quantite=0.0, ligne_id=0):
        """
        Point d'entrée unique pour les scans mobiles (application PHP).
        Retourne un dict : preparation_id, next_action, html, error, message, composant_code
        """
        result = {
            'preparation_id': preparation_id,
            'next_action': action,
            'html': '',
            'error': '',
            'message': '',
            'composant_code': '',
        }

        # --- SCAN ÉTIQUETTE LIVRAISON (1re étape) ---
        if action == 'scan-etiquette-livraison':
            etiquette = self.env['is.tracabilite.livraison'].search(
                [('name', '=', scan_value)], limit=1)
            if not etiquette:
                result['error'] = f"Étiquette '{scan_value}' non trouvée"
                result['next_action'] = 'scan-etiquette-livraison'
            elif not etiquette.production_id:
                result['error'] = f"L'étiquette {etiquette.name} n'est pas liée à un OF"
                result['next_action'] = 'scan-etiquette-livraison'
            elif etiquette.production_id.state == 'done':
                result['error'] = f"L'OF {etiquette.production_id.name} est déjà clôturé"
                result['next_action'] = 'scan-etiquette-livraison'
            else:
                # Chercher une déclaration en cours pour cette étiquette
                existing = self.search([
                    ('etiquette_tracabilite_id', '=', etiquette.id),
                    ('state', '=', 'en_cours'),
                ], limit=1)
                if existing:
                    prep = existing
                    result['message'] = (
                        f"Déclaration existante récupérée | "
                        f"OF {etiquette.production_id.name} | {etiquette.product_id.name}"
                    )
                else:
                    prep = self.create({'etiquette_tracabilite_id': etiquette.id})
                    prep._fill_composants_from_etiquette()
                    result['message'] = (
                        f"OF {etiquette.production_id.name} | {etiquette.product_id.name}"
                    )
                result['preparation_id'] = prep.id
                result['next_action'] = 'saisie-quantite-declarer'
                result['html'] = str(prep.affichage_mobile_html or '')

        # --- SAISIE QUANTITÉ À DÉCLARER ---
        elif action == 'saisir-quantite-declarer':
            prep = self.browse(preparation_id)
            if quantite <= 0:
                result['error'] = "La quantité à déclarer doit être supérieure à 0"
                result['next_action'] = 'saisie-quantite-declarer'
            else:
                prep.write({'quantite_a_declarer': quantite})
                self.env.cache.invalidate()
                prep = self.browse(preparation_id)
                result['message'] = f"Quantité à déclarer : {quantite:g}"
                result['next_action'] = 'scan-operateur'
            result['html'] = str(prep.affichage_mobile_html or '')

        # --- SCAN OPÉRATEUR (2e étape) ---
        elif action == 'scan-operateur':
            employee = self.env['hr.employee'].search(
                [('is_matricule', 'like', scan_value)], limit=1)
            if not employee:
                result['error'] = f"Opérateur '{scan_value}' non trouvé"
                result['next_action'] = 'scan-operateur'
            else:
                prep = self.browse(preparation_id)
                prep.write({'operateurs_ids': [(4, employee.id)]})
                result['message'] = f"Opérateur {employee.name} ajouté"
                result['next_action'] = 'scan-operateur'
                result['html'] = str(prep.affichage_mobile_html or '')

        # --- PASSER AUX COMPOSANTS ---
        elif action == 'suivant-composant':
            prep = self.browse(preparation_id)
            if not prep.operateurs_ids:
                result['error'] = "Veuillez scanner au moins un opérateur"
                result['next_action'] = 'scan-operateur'
            else:
                result['next_action'] = 'scan-composant'
            result['html'] = str(prep.affichage_mobile_html or '')

        # --- SCAN COMPOSANT (vérification avant saisie quantité) ---
        elif action == 'scan-composant':
            prep = self.browse(preparation_id)
            if not prep.etiquette_tracabilite_id:
                result['error'] = "L'étiquette de livraison doit être scannée en premier"
                result['next_action'] = 'scan-etiquette-livraison'
            elif scan_value.startswith('TR'):
                etiquette = self.env['is.tracabilite.reception'].search(
                    [('name', '=', scan_value)], limit=1)
                if not etiquette:
                    result['error'] = f"Étiquette réception '{scan_value}' non trouvée"
                    result['next_action'] = 'scan-composant'
                else:
                    result['composant_code'] = scan_value
                    result['next_action'] = 'saisie-quantite'
            elif scan_value.startswith('TL'):
                etiquette = self.env['is.tracabilite.livraison'].search(
                    [('name', '=', scan_value)], limit=1)
                if not etiquette:
                    result['error'] = f"Étiquette semi-fini '{scan_value}' non trouvée"
                    result['next_action'] = 'scan-composant'
                else:
                    result['composant_code'] = scan_value
                    result['next_action'] = 'saisie-quantite'
            else:
                result['error'] = (
                    f"Code '{scan_value}' non reconnu (doit commencer par TR ou TL)"
                )
                result['next_action'] = 'scan-composant'
            result['html'] = str(prep.affichage_mobile_html or '')

        # --- AJOUTER COMPOSANT (après saisie quantité clavier) ---
        elif action == 'ajouter-composant':
            prep = self.browse(preparation_id)
            vals = {'preparation_id': prep.id, 'quantite_saisie': quantite}
            article_name = ''
            ok = False

            if scan_value.startswith('TR'):
                etiquette = self.env['is.tracabilite.reception'].search(
                    [('name', '=', scan_value)], limit=1)
                if not etiquette:
                    result['error'] = f"Étiquette '{scan_value}' non trouvée"
                else:
                    composants_tmpl_ids = prep.composant_ids.mapped(
                        'product_id.product_tmpl_id.id')
                    if etiquette.product_id.id not in composants_tmpl_ids:
                        result['error'] = (
                            f"'{etiquette.product_id.name}' "
                            f"ne fait pas partie des composants de l'OF"
                        )
                    else:
                        try:
                            vals['etiquette_reception_id'] = etiquette.id
                            self.env[
                                'is.preparation.declaration.production.line'
                            ].create(vals)
                            article_name = etiquette.product_id.name
                            ok = True
                        except ValidationError as e:
                            result['error'] = str(e)

            elif scan_value.startswith('TL'):
                etiquette = self.env['is.tracabilite.livraison'].search(
                    [('name', '=', scan_value)], limit=1)
                if not etiquette:
                    result['error'] = f"Étiquette '{scan_value}' non trouvée"
                else:
                    composants_tmpl_ids = prep.composant_ids.mapped(
                        'product_id.product_tmpl_id.id')
                    if etiquette.product_id.id not in composants_tmpl_ids:
                        result['error'] = (
                            f"'{etiquette.product_id.name}' "
                            f"ne fait pas partie des composants de l'OF"
                        )
                    else:
                        try:
                            vals['etiquette_livraison_id'] = etiquette.id
                            self.env[
                                'is.preparation.declaration.production.line'
                            ].create(vals)
                            article_name = etiquette.product_id.name
                            ok = True
                        except ValidationError as e:
                            result['error'] = str(e)
            else:
                result['error'] = f"Code '{scan_value}' non reconnu"

            if ok:
                result['message'] = f"{article_name} | qté : {quantite}"
            result['next_action'] = 'scan-composant'
            result['html'] = str(prep.affichage_mobile_html or '')

        # --- SUPPRIMER UNE LIGNE ---
        elif action == 'supprimer-ligne':
            prep = self.browse(preparation_id)
            if ligne_id:
                ligne = self.env['is.preparation.declaration.production.line'].browse(ligne_id)
                if ligne.exists() and ligne.preparation_id.id == preparation_id:
                    ligne.unlink()
                    result['message'] = "Ligne supprimée"
                else:
                    result['error'] = "Ligne introuvable"
            # Invalider le cache pour forcer le recalcul du HTML
            self.env.cache.invalidate()
            prep = self.browse(preparation_id)
            result['next_action'] = 'scan-composant'
            result['html'] = str(prep.affichage_mobile_html or '')

        # --- CONFIRMATION AVANT VALIDATION ---
        elif action == 'confirmer-validation':
            prep = self.browse(preparation_id)
            result['next_action'] = 'confirmer-validation'
            result['html'] = str(prep.affichage_mobile_html or '')

        # --- VALIDER ---
        elif action == 'valider':
            prep = self.browse(preparation_id)
            try:
                prep.action_terminer()
                result['next_action'] = 'termine'
                result['html'] = str(prep.affichage_mobile_html or '')
            except ValidationError as e:
                result['error'] = str(e)
                result['next_action'] = 'scan-composant'
                result['html'] = str(prep.affichage_mobile_html or '')

        return result

    def action_terminer(self):
        """Passer l'état à Terminé"""
        # Vérifier qu'au moins un opérateur est renseigné
        if not self.operateurs_ids:
            raise ValidationError(
                "Vous devez renseigner au moins un opérateur avant de terminer la préparation."
            )

        # Vérifier qu'il n'y a pas d'écart
        for composant in self.composant_ids:
            if composant.ecart != 0:
                raise ValidationError(
                    f"Impossible de terminer: l'article {composant.product_id.name} a un écart de {composant.ecart}. "
                    f"Prévu: {composant.quantite_prevue}, Scanné: {composant.total_quantite_scanee}"
                )
        
        # Vérifier le stock disponible
        for composant in self.composant_ids:
            if composant.stock_disponible < composant.total_quantite_scanee:
                raise ValidationError(
                    f"Impossible de terminer: l'article {composant.product_id.name} n'a pas assez de stock. "
                    f"Stock disponible: {composant.stock_disponible}, Quantité scanée: {composant.total_quantite_scanee}"
                )
        
        # Déclaration de la production avec les quantités indiquées
        production = self.production_id
        if production:
            # Mémoriser la quantité prévue avant validation (product_qty peut changer après backorder)
            quantite_prevue = production.product_qty

            # Mettre à jour les quantités des mouvements de matière première
            # Regrouper les quantités par product_id pour éviter l'écrasement
            quantites_par_produit = {}
            for ligne in self.ligne_ids:
                if ligne.product_id and ligne.quantite_saisie > 0:
                    if ligne.product_id not in quantites_par_produit:
                        quantites_par_produit[ligne.product_id] = 0.0
                    quantites_par_produit[ligne.product_id] += ligne.quantite_saisie

            for product_tmpl, quantite_totale in quantites_par_produit.items():
                moves = production.move_raw_ids.filtered(
                    lambda m: m.product_id.product_tmpl_id == product_tmpl and m.state not in ('cancel', 'done')
                )
                for move in moves:
                    move.quantity_done = quantite_totale

            # Définir la quantité produite sur l'OF
            production.qty_producing = self.quantite_a_declarer

            # Mettre à jour explicitement la quantité faite sur le mouvement du produit fini
            # (les move_finished_ids sont des mouvements de sortie, ils ne passent pas par 'assigned')
            for move in production.move_finished_ids.filtered(lambda m: m.state not in ('cancel', 'done')):
                move.quantity_done = self.quantite_a_declarer

            # Valider l'OF via l'API standard (gère le produit fini et le reliquat MRP)
            action = production.button_mark_done()

            # Si un wizard de backorder est retourné, l'exécuter automatiquement
            if isinstance(action, dict) and action.get('res_model') == 'mrp.production.backorder':
                backorder_wizard = self.env['mrp.production.backorder'].with_context(
                    **action.get('context', {})
                ).create({})
                backorder_wizard.action_backorder()

            # _generate_backorder_productions déplace les étiquettes non fabriquées vers le reliquat.
            # On force le rattachement de l'étiquette de cette préparation à la production déclarée.
            if self.etiquette_tracabilite_id:
                operateur_ids = [(4, op.id) for op in self.operateurs_ids]
                self.etiquette_tracabilite_id.write({
                    'production_id': production.id,
                    'fabrique': fields.Datetime.now(),
                    'operateur_ids': operateur_ids,
                    'lot_fabrication': int(self.quantite_a_declarer),
                })

                # Lier les étiquettes composants (réception et semi-fini) à l'étiquette de livraison
                for ligne in self.ligne_ids:
                    if ligne.etiquette_reception_id:
                        self.env['is.tracabilite.reception.line'].create({
                            'etiquette_id': ligne.etiquette_reception_id.id,
                            'quantity': ligne.quantite_saisie,
                            'livraison_id': self.etiquette_tracabilite_id.id,
                        })
                    elif ligne.etiquette_livraison_id:
                        self.env['is.tracabilite.livraison.line'].create({
                            'etiquette_id': ligne.etiquette_livraison_id.id,
                            'quantity': ligne.quantite_saisie,
                            'livraison_id': self.etiquette_tracabilite_id.id,
                        })

            # Créer un reliquat de préparation si la quantité déclarée est inférieure à la quantité prévue
            if self.quantite_a_declarer < quantite_prevue:
                reliquat_qty = quantite_prevue - self.quantite_a_declarer
                self.with_context(skip_check_of_done=True).copy({
                    'quantite_a_declarer': reliquat_qty,
                    'state': 'en_cours',
                    'etiquette_tracabilite_id': False,
                    'ligne_ids': [(5, 0, 0)],  # Effacer les lignes
                })
        
        self.state = 'termine'
        return True


class IsPreparationDeclarationProductionLine(models.Model):
    _name = 'is.preparation.declaration.production.line'
    _description = 'Ligne de préparation de déclaration de production'
    _order = 'id'

    preparation_id = fields.Many2one(
        'is.preparation.declaration.production',
        string="Préparation",
        required=True,
        ondelete='cascade'
    )

    etiquette_reception_id = fields.Many2one(
        'is.tracabilite.reception',
        string="Étiquette de traçabilité en réception"
    )

    etiquette_livraison_id = fields.Many2one(
        'is.tracabilite.livraison',
        string="Étiquette de traçabilité en livraison (semi-fini)"
    )

    product_id = fields.Many2one(
        'product.template',
        string="Article",
        compute='_compute_product_id',
        store=True,
        readonly=True
    )

    quantite_saisie = fields.Float(
        string="Quantité saisie",
        required=True,
        default=1.0,
        digits=(14, 2)
    )

    @api.depends('etiquette_reception_id', 'etiquette_livraison_id')
    def _compute_product_id(self):
        for line in self:
            if line.etiquette_reception_id:
                line.product_id = line.etiquette_reception_id.product_id
            elif line.etiquette_livraison_id:
                line.product_id = line.etiquette_livraison_id.product_id
            else:
                line.product_id = False

    @api.constrains('etiquette_reception_id', 'etiquette_livraison_id')
    def _check_etiquette_constraint(self):
        for line in self:
            # Vérifier qu'une des deux étiquettes est renseignée
            if not line.etiquette_reception_id and not line.etiquette_livraison_id:
                raise ValidationError(
                    "Vous devez saisir une Étiquette de traçabilité en réception "
                    "ou une Étiquette de traçabilité en livraison."
                )
            
            # Vérifier que les deux ne sont pas renseignées en même temps
            if line.etiquette_reception_id and line.etiquette_livraison_id:
                raise ValidationError(
                    "Vous ne pouvez pas saisir à la fois une Étiquette de traçabilité "
                    "en réception ET une Étiquette de traçabilité en livraison."
                )

    @api.constrains('etiquette_reception_id', 'etiquette_livraison_id')
    def _check_etiquette_composant(self):
        for line in self:
            if not line.preparation_id or not line.preparation_id.composant_ids:
                continue
            # Récupérer les IDs des product.template des composants de la préparation
            composants_tmpl_ids = line.preparation_id.composant_ids.mapped('product_id.product_tmpl_id.id')
            product_tmpl = False
            if line.etiquette_reception_id:
                product_tmpl = line.etiquette_reception_id.product_id
            elif line.etiquette_livraison_id:
                product_tmpl = line.etiquette_livraison_id.product_id
            if product_tmpl and product_tmpl.id not in composants_tmpl_ids:
                raise ValidationError(
                    f"L'article '{product_tmpl.name}' ne fait pas partie des composants de cet OF."
                )

    @api.constrains('etiquette_reception_id', 'etiquette_livraison_id')
    def _check_etiquette_doublon(self):
        for line in self:
            if not line.preparation_id:
                continue
            
            # Vérifier les doublons d'étiquette de réception
            if line.etiquette_reception_id:
                doublon_reception = self.search([
                    ('preparation_id', '=', line.preparation_id.id),
                    ('etiquette_reception_id', '=', line.etiquette_reception_id.id),
                    ('id', '!=', line.id)
                ])
                if doublon_reception:
                    raise ValidationError(
                        f"Une ligne avec l'Étiquette de traçabilité en réception "
                        f"{line.etiquette_reception_id.name} existe déjà dans cette préparation."
                    )
            
            # Vérifier les doublons d'étiquette de livraison
            if line.etiquette_livraison_id:
                doublon_livraison = self.search([
                    ('preparation_id', '=', line.preparation_id.id),
                    ('etiquette_livraison_id', '=', line.etiquette_livraison_id.id),
                    ('id', '!=', line.id)
                ])
                if doublon_livraison:
                    raise ValidationError(
                        f"Une ligne avec l'Étiquette de traçabilité en livraison "
                        f"{line.etiquette_livraison_id.name} existe déjà dans cette préparation."
                    )

    @api.onchange('etiquette_reception_id')
    def _onchange_etiquette_reception(self):
        if self.etiquette_reception_id:
            self.etiquette_livraison_id = False

    @api.onchange('etiquette_livraison_id')
    def _onchange_etiquette_livraison(self):
        if self.etiquette_livraison_id:
            self.etiquette_reception_id = False


class IsPreparationDeclarationProductionComposant(models.Model):
    _name = 'is.preparation.declaration.production.composant'
    _description = 'Composant OF - Préparation de déclaration de production'
    _order = 'id'

    preparation_id = fields.Many2one(
        'is.preparation.declaration.production',
        string="Préparation",
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string="Article",
        required=True
    )

    quantite_prevue_unitaire = fields.Float(
        string="Quantité prévue unitaire",
        required=True,
        digits=(14, 2)
    )

    quantite_prevue = fields.Float(
        string="Quantité prévue",
        compute='_compute_quantite_prevue',
        store=True,
        readonly=True,
        digits=(14, 2)
    )

    total_quantite_scanee = fields.Float(
        string="Total quantité scanée",
        compute='_compute_total_quantite_scanee',
        store=True,
        readonly=True,
        digits=(14, 2)
    )

    ecart = fields.Float(
        string="Écart",
        compute='_compute_ecart',
        store=True,
        readonly=True,
        digits=(14, 2)
    )

    stock_disponible = fields.Float(
        string="Stock disponible",
        compute='_compute_stock_disponible',
        store=True,
        readonly=True,
        digits=(14, 2)
    )

    @api.depends('preparation_id.ligne_ids.quantite_saisie', 'preparation_id.ligne_ids.product_id')
    def _compute_total_quantite_scanee(self):
        for composant in self:
            total = 0.0
            for ligne in composant.preparation_id.ligne_ids:
                if ligne.product_id == composant.product_id.product_tmpl_id:
                    total += ligne.quantite_saisie
            composant.total_quantite_scanee = total

    @api.depends('quantite_prevue_unitaire', 'preparation_id.quantite_a_declarer')
    def _compute_quantite_prevue(self):
        for composant in self:
            if composant.preparation_id:
                composant.quantite_prevue = composant.quantite_prevue_unitaire * composant.preparation_id.quantite_a_declarer
            else:
                composant.quantite_prevue = 0.0

    @api.depends('quantite_prevue', 'total_quantite_scanee')
    def _compute_ecart(self):
        for composant in self:
            composant.ecart = composant.quantite_prevue - composant.total_quantite_scanee

    @api.depends('product_id')
    def _compute_stock_disponible(self):
        for composant in self:
            if composant.product_id:
                composant.stock_disponible = composant.product_id.qty_available
            else:
                composant.stock_disponible = 0.0
