# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import Warning
from math import ceil
from datetime import datetime, timedelta


class is_ordre_travail(models.Model):
    _name='is.ordre.travail'
    _description='Ordre de travail'
    _inherit = ['mail.thread']
    _order='name desc'


    @api.depends('production_id','production_id.is_planification','production_id.is_date_prevue','production_id.date_planned_start')
    def _compute_date_prevue(self):
        for obj in self:
            date_prevue=obj.production_id.date_planned_start
            if obj.production_id.is_planification!="date_fixee":
                if obj.production_id.is_date_prevue:
                    date_prevue=obj.production_id.is_date_prevue # Date prévue sur la ligne de commande client
            obj.date_prevue = date_prevue


    name                 = fields.Char("N°", readonly=True)
    createur_id          = fields.Many2one('res.users', 'Créateur', required=True, default=lambda self: self.env.user.id)
    date_creation        = fields.Date("Date de création"         , required=True, default=lambda *a: fields.Date.today())
    production_id        = fields.Many2one('mrp.production', 'Ordre de production', required=True)
    procurement_group_id = fields.Many2one('procurement.group', "Groupe d'approvisionnement")
    quantite             = fields.Float('Qt prévue', digits=(14,2), readonly=True)
    #date_prevue          = fields.Datetime('Date prévue' , related='production_id.date_planned_start')
    #date_prevue          = fields.Datetime('Date client', related='production_id.is_date_prevue')
    date_prevue          = fields.Datetime('Date prévue', compute='_compute_date_prevue', store=True, readonly=True)
    product_id           = fields.Many2one('product.product', 'Article', related='production_id.product_id')
    bom_id               = fields.Many2one('mrp.bom', 'Nomenclature', related='production_id.bom_id')
    state                = fields.Selection([
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
        ], "État", default='encours')
    line_ids            = fields.One2many('is.ordre.travail.line', 'ordre_id', 'Lignes')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.ordre.travail')
        res = super(is_ordre_travail, self).create(vals)
        return res


    def get_heure_debut_fin(self,workcenter_id, duree, heure_debut=False, heure_fin=False, tache=False):
        cr=self._cr
        """Rechercher l'heure de fin si l'heure de début est fourni en fonction de la duree et des dispos et vis et versa"""
        # Recherche des ouvertues du poste de charge 
        # Comme chaque ligne fait 30mn, il suffit de mettre une limite en fonction de la durée de la tache
        limit = ceil(duree*2) # La dispo des ressources est par plage de 30mn
        res=False
        if heure_debut:
            res = heure_debut + timedelta(hours=duree) # Théorique si pas de fermeture
            filtre=[
                ('workcenter_id', '=' , workcenter_id),
                ('disponibilite', '>' , 0),
                ('employe_id'   , '=' , False),
                ('heure_debut'  , '>=', heure_debut),
            ]
            dispos=self.env['is.dispo.ressource'].search(filtre, limit=limit, order="heure_debut")
            if len(dispos)>0:
                res = dispos[len(dispos)-1].heure_fin
        if heure_fin:
            res = heure_fin - timedelta(hours=duree) # Théorique si pas de fermeture
            filtre=[
                ('workcenter_id', '=' , workcenter_id),
                ('disponibilite', '>' , 0),
                ('employe_id'   , '=' , False),
                ('heure_fin'  , '<=', heure_fin),
            ]
            dispos=self.env['is.dispo.ressource'].search(filtre, limit=limit, order="heure_fin desc")
            if len(dispos)>0:
                res = dispos[len(dispos)-1].heure_debut
        if tache:
            #Supprimer la tache des dispos avant de la recéer
            filtre=[
                ('taches_ids'  , 'in', tache.id),
            ]
            lines=self.env['is.dispo.ressource'].search(filtre)
            for line in lines:
                line.taches_ids=[(3, tache.id)] 
            #******************************************************************

            #** Ajout des relations *******************************************
            for dispo in dispos:
                dispo.taches_ids=[(4, tache.id)] 
        return res


    def calculer_charge_ordre_travail(self):
        for ordre in self:
            date_debut_ordre_production = date_fin_ordre_production = False
            now = datetime.now()
            #Pour un calcul au plus tard, il faut que la date prévue soit dans plus de 20 jours => Sinon, calcul au plus tôt
            date_limite_au_plus_tard = now + timedelta(days=20)
            if ordre.production_id.is_planification in ['au_plus_tot','date_fixee'] or ordre.date_prevue<date_limite_au_plus_tard:
                if  ordre.production_id.is_planification=='au_plus_tot':
                    heure_debut = now
                else:
                    heure_debut = ordre.date_prevue
                date_debut_ordre_production = heure_debut
                date_fin_ordre_production = heure_debut
                duree_precedente=0
                mem_tps_apres=0
                for tache in ordre.line_ids:
                    workcenter_id = tache.workcenter_id.id
                    #Décale la date de début car 'Tps passage après' est renseigné (en heures ouvrées)
                    if mem_tps_apres>0:
                        heure_debut = self.get_heure_debut_fin(workcenter_id, mem_tps_apres, heure_debut=heure_debut, tache=False)
                    duree_recouvrement = duree_precedente*tache.recouvrement/100
                    heure_debut = heure_debut - timedelta(hours=duree_recouvrement)
                    duree = tache.reste
                    heure_fin = self.get_heure_debut_fin(workcenter_id, duree, heure_debut=heure_debut, tache=tache)
                    tache.heure_debut = heure_debut
                    tache.heure_fin   = heure_fin 
                    duree_relle = (heure_fin-heure_debut).total_seconds()/3600
                    heure_debut = heure_fin
                    duree_precedente = duree_relle
                    if heure_fin>date_fin_ordre_production:
                        date_fin_ordre_production=heure_fin
                    mem_tps_apres=tache.tps_apres

            else:
                heure_fin = ordre.date_prevue
                date_debut_ordre_production = date_fin_ordre_production = heure_fin
                duree_precedente=0
                taches=self.env['is.ordre.travail.line'].search([('ordre_id', '=', ordre.id)], order="sequence desc")
                recouvrement_suivant = 0
                heure_debut_precedent=False
                for tache in taches:
                    workcenter_id = tache.workcenter_id.id
                    #Décale la date de fin car 'Tps passage après' est renseigné (en heures ouvrées)
                    if tache.tps_apres>0 and heure_debut_precedent:
                        heure_fin = self.get_heure_debut_fin(workcenter_id, tache.tps_apres, heure_fin=heure_debut_precedent, tache=False)
                    #Calcul de la durée de decalage de la tache en cours en fonction du recouvrement
                    decale = tache.reste*recouvrement_suivant/100
                    if decale>0:
                        heure_debut = heure_debut_precedent
                        #Recherche de la date de fin en partant de l'heure de début de la tache de fin et de la durée de recouvrement
                        heure_fin = self.get_heure_debut_fin(workcenter_id, decale, heure_debut=heure_debut)
                    #Recherche de la date de début à partir de l'heure de fin précédente
                    duree = tache.reste
                    heure_debut = self.get_heure_debut_fin(workcenter_id, duree, heure_fin=heure_fin, tache=tache)
                    tache.heure_debut = heure_debut 
                    tache.heure_fin   = heure_fin 
                    heure_fin = heure_debut
                    recouvrement_suivant = tache.recouvrement
                    heure_debut_precedent=tache.heure_debut
                    if tache.heure_debut<date_debut_ordre_production:
                        date_debut_ordre_production = tache.heure_debut
                    if tache.heure_fin>date_fin_ordre_production:
                        date_fin_ordre_production = tache.heure_fin

            # ordre.production_id.is_date_planifiee     = date_debut_ordre_production
            # ordre.production_id.is_date_planifiee_fin = date_fin_ordre_production
            # ordre.production_id.date_planned_start    = date_debut_ordre_production

            ordre.production_id.write({
                "is_date_planifiee"    : date_debut_ordre_production,
                "is_date_planifiee_fin": date_fin_ordre_production,
                "date_planned_start"   : date_debut_ordre_production,
            })

            #********************************************************************************


        #TODO : 
        #Commencer par créer les ordres de travail si ce n'est pas le cas
        #A la fin, mettre à jour la date de début et de fin de l'ordre de fabrication
        #Revoir la charge par plage de 30mn => cf ci-dessous

        #TODO : A revoir car le tableau charge est toujours vide suite aux modifiications précentes
        #Pour chaque plage de 30mn, rechercher les taches et enregister la liste des taches
        #Ajouter un champ pour sauvuegarder cette liste de tache et faire un champ calculé pour le nombre de taches
        #Il faudrait limiter ce calcul à la liste des taches traitées précédenmment
        #Comme cela il suffirait de mémoriser la liste des taches à actualiser pour étiter de tout recalculer juste pour un OF à calculer
        #=> Memoriser la liste des odres de fabrication est suffisant
        #** Enregistrement de la charge par plage de 30mn *******************************
        # charge={}
        # for dispo in charge:
        #     dispo.charge = charge[dispo]
        #********************************************************************************




    def vue_gantt_action(self):
        for obj in self: 
            action= {
                "name": "Gantt",
                "view_mode": "dhtmlx_gantt_ot,timeline,tree,form",
                "res_model": "is.ordre.travail.line",
                "domain": [
                    ("ordre_id" ,"=",obj.id),
                ],
                "type": "ir.actions.act_window",
                "context": {"vue_gantt":"production"}
            }
            #print(action)
            return action

class is_ordre_travail_line(models.Model):
    _name='is.ordre.travail.line'
    _description='Ligne Ordre de travail'
    _order='ordre_planning,sequence,heure_debut'

    ordre_id       = fields.Many2one('is.ordre.travail', 'Ordre de travail' , required=True, ondelete='cascade')
    production_id  = fields.Many2one('mrp.production', 'Ordre de production', related='ordre_id.production_id')
    is_sale_order_id    = fields.Many2one(related='production_id.is_sale_order_id')
    is_client_order_ref = fields.Char(related='production_id.is_client_order_ref')
    product_id     = fields.Many2one('product.product', 'Article'           , related='ordre_id.product_id')
    date_prevue    = fields.Datetime('Date prévue'                          , related='ordre_id.date_prevue')
    name           = fields.Char("Opération"                                , required=True)
    sequence       = fields.Integer("Séquence"                              , required=True)
    ordre_planning = fields.Integer("Ordre", help="Ordre dans le planning")
    workcenter_id  = fields.Many2one('mrp.workcenter', 'Poste de Travail'   , required=True)
    recouvrement   = fields.Integer("Recouvrement (%)", required=True, default=0, help="0%: Cette ligne commence à la fin de la ligne précédente\n50%: Cette ligne commence quand la ligne précédente est terminée à 50%\n100%: Cette ligne commence en même temps que la ligne précédente" )
    tps_apres      = fields.Float("Tps passage après (HH:MN)", default=0, help="Temps d'attente après cette opération avant de commencer la suivante (en heures ouvrées)")
    duree_unitaire = fields.Float("Durée unitaire (H)"                      , required=True)
    duree_totale   = fields.Float("Durée totale (H)", compute='_compute_reste', store=True)
    duree_reelle   = fields.Float("Durée réelle (H)", compute='_compute_duree_reelle', store=True, help="Durée entre Heure début et Heure fin")
    realisee       = fields.Float("Durée réalisee (H)")
    reste          = fields.Float("Reste (H)", compute='_compute_reste', store=True)
    heure_debut    = fields.Datetime("Heure début", index=True              , required=False)
    heure_fin      = fields.Datetime("Heure fin"                            , required=False)
    state          = fields.Selection([
            ('attente', 'Attente'),
            ('pret'   , 'Prêt'),
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
            ('annule' , 'Annulé'),
        ], "État", default='attente')


    @api.depends('duree_unitaire','realisee','ordre_id.quantite')
    def _compute_reste(self):
        for obj in self:
            duree_totale = obj.ordre_id.quantite*obj.duree_unitaire
            obj.duree_totale=duree_totale
            obj.reste=duree_totale-obj.realisee


    @api.depends('heure_debut','heure_fin')
    def _compute_duree_reelle(self):
        for obj in self:
            duree_reelle=0
            if obj.heure_fin and obj.heure_debut:
                duree_reelle = (obj.heure_fin-obj.heure_debut).total_seconds()/3600
            obj.duree_reelle=duree_reelle



    # def add_taches_sur_dispo(self):
    #     for tache in self:
            # filtre=[
            #     ('workcenter_id', '=' , workcenter_id),
            #     ('disponibilite', '>' , 0),
            #     ('employe_id'   , '=' , False),
            #     ('heure_debut'  , '>=', heure_debut),
            # ]
            # dispos=self.env['is.dispo.ressource'].search(filtre, limit=limit, order="heure_debut")




