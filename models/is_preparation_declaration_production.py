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
        required=True,
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

    @api.constrains('etiquette_tracabilite_id')
    def _check_etiquette_of_not_done(self):
        # Ne pas vérifier si on est en train de copier pour le reliquat
        if self.env.context.get('skip_check_of_done'):
            return
        
        for record in self:
            if record.etiquette_tracabilite_id and record.etiquette_tracabilite_id.production_id:
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

    def action_terminer(self):
        """Passer l'état à Terminé"""
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
            # Mettre à jour les quantités des mouvements de matière première
            for ligne in self.ligne_ids:
                if ligne.product_id and ligne.quantite_saisie > 0:
                    # Trouver le move correspondant dans la production
                    moves = production.move_raw_ids.filtered(
                        lambda m: m.product_id.product_tmpl_id == ligne.product_id and m.state not in ('cancel', 'done')
                    )
                    for move in moves:
                        move.product_uom_qty = ligne.quantite_saisie
                        if move.state == 'draft':
                            move._action_confirm()
                        if move.state in ('confirmed', 'waiting', 'partially_available'):
                            move._action_assign()
                        move.quantity_done = ligne.quantite_saisie
                        if move.state == 'assigned':
                            move._action_done()
            
            # Déclarer la production du produit fini
            for move in production.move_finished_ids.filtered(lambda m: m.state not in ('cancel', 'done')):
                move.product_uom_qty = self.quantite_a_declarer
                if move.state == 'draft':
                    move._action_confirm()
                if move.state in ('confirmed', 'waiting', 'partially_available'):
                    move._action_assign()
                move.quantity_done = self.quantite_a_declarer
                if move.state == 'assigned':
                    move._action_done()
            
            # Créer un reliquat si la quantité déclarée est inférieure à la quantité prévue
            if self.quantite_a_declarer < production.product_qty:
                reliquat_qty = production.product_qty - self.quantite_a_declarer
                # Créer une nouvelle préparation pour le reliquat
                self.with_context(skip_check_of_done=True).copy({
                    'quantite_a_declarer': reliquat_qty,
                    'state': 'en_cours',
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
