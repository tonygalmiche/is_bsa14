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
    is_nom_affaire       = fields.Char(related="production_id.is_nom_affaire")
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

        if limit<0:
            limit=1

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
            return action


    def get_operations(self,workcenter_id=False,employe_id=False):
        "Fonction utilisée par l'application externe inox-atelier pour récuprer les opérations des ordres de travaux à réaliser"
        cr = self._cr
        SQL="""
            SELECT 
                iot.name num_ot,
                mp.name num_of,
                mp.is_nom_affaire,
                mw.name workcenter_name,
                line.id line_id,
                line.name line_name,
                line.heure_debut,
                line.heure_fin,
                pt.name product_name,
                line.workcenter_id,
                pp.id product_id,
                (select count(*) from is_ordre_travail_line_temps_passe where line_id=line.id) count_tps
                --(
                --    select pav.name
                --    from product_variant_combination pvc join product_attribute_value_product_template_attribute_line_rel rel on pvc.product_template_attribute_value_id=rel.product_attribute_value_id
                --                                        join product_attribute_value pav on rel.product_attribute_value_id=pav.id and attribute_id=1
                --    where pvc.product_product_id=pp.id
                --    limit 1
                --) numero_attribut
            FROM is_ordre_travail iot join is_ordre_travail_line line on line.ordre_id=iot.id
                                      join mrp_production mp          on iot.production_id=mp.id
                                      join mrp_workcenter mw          on line.workcenter_id=mw.id
                                      join product_product pp         on mp.product_id=pp.id
                                      join product_template pt        on pp.product_tmpl_id=pt.id
            WHERE 
                mp.is_pret='oui' and
                mp.state not in ('draft','done','cancel') and
                iot.state='encours' and
                line.state not in ('termine','annule') and
                line.workcenter_id=%s
            ORDER BY line.heure_debut
        """

        print(SQL,workcenter_id)


        cr.execute(SQL,[workcenter_id])
        res = cr.dictfetchall()
        ids=[]
        lines=[]
        for line in res:

            print(line)


            #** Recherche si les boutons de l'opération sont actifs ***********
            test=False
            operation=self.env['is.ordre.travail.line'].browse(line["line_id"])
            if operation:
                test = operation.afficher_start_stop
            #******************************************************************

            print('test=',test)


            if test:
                ids.append(line["line_id"])
                #** Problème d'encodage en XML-RPC ??
                line["operation"]      = operation.name.encode('utf_8').decode('latin_1')
                line["product_name"]   = line["product_name"].encode('utf_8').decode('latin_1')
                lines.append(line)

                print(line)




        return {
            'test':'ok éè€',
            'ids':ids,
            'lines':lines,
        }











class is_ordre_travail_line(models.Model):
    _name='is.ordre.travail.line'
    _inherit = ['mail.thread']
    _description='Ligne Ordre de travail'
    _order='ordre_planning,sequence,heure_debut'

    ordre_id       = fields.Many2one('is.ordre.travail', 'Ordre de travail' , required=True, ondelete='cascade')
    production_id  = fields.Many2one('mrp.production', 'Ordre de production', related='ordre_id.production_id')
    is_sale_order_id    = fields.Many2one(related='production_id.is_sale_order_id')
    is_client_order_ref = fields.Char(related='production_id.is_client_order_ref')
    product_id     = fields.Many2one('product.product', 'Article'           , related='ordre_id.product_id')
    date_prevue    = fields.Datetime('Date prévue'                          , related='ordre_id.date_prevue')
    name           = fields.Char("Opération"                                , required=True)
    libre          = fields.Boolean("Libre", default=False, help="Permet de démarrer le suivi du temps sur cette opération à tout moment")
    sequence       = fields.Integer("Séquence"                              , required=True)
    ordre_planning = fields.Integer("Ordre", help="Ordre dans le planning")
    workcenter_id  = fields.Many2one('mrp.workcenter', 'Poste de Travail'   , required=True)
    recouvrement   = fields.Integer("Recouvrement (%)", required=True, default=0, help="0%: Cette ligne commence à la fin de la ligne précédente\n50%: Cette ligne commence quand la ligne précédente est terminée à 50%\n100%: Cette ligne commence en même temps que la ligne précédente" )
    tps_apres      = fields.Float("Tps passage après (HH:MN)", default=0, help="Temps d'attente après cette opération avant de commencer la suivante (en heures ouvrées)")
    duree_unitaire = fields.Float("Durée unitaire (HH:MM)"                      , required=True)
    duree_totale   = fields.Float("Durée prévue (HH:MM)", compute='_compute_reste', store=True)
    duree_reelle   = fields.Float("Durée hors tout (HH:MM)"        , compute='_compute_duree_reelle', store=True, help="Durée entre Heure début et Heure fin")
    heure_debut    = fields.Datetime("Heure début", index=True              , required=False)
    heure_fin      = fields.Datetime("Heure fin"                            , required=False)
    state          = fields.Selection([
            ('attente', 'Attente'),
            ('pret'   , 'Prêt'),
            ('encours', 'En cours'),
            ('termine', 'Terminé'),
            ('annule' , 'Annulé'),
        ], "État", default='attente')
    temps_passe_ids = fields.One2many('is.ordre.travail.line.temps.passe', 'line_id', 'Lignes')
    temps_passe = fields.Float("Temps passé (HH:MM)", compute="_compute_temps_passe", readonly=True, store=True)
    reste       = fields.Float("Reste (HH:MM)"      , compute='_compute_temps_passe', readonly=True, store=True)
    afficher_start_stop = fields.Boolean("Afficher les boutons start/stop", compute="_compute_afficher_start_stop", readonly=True, store=False)
    commentaire     = fields.Text("Commentaire")
    commentaire_ids = fields.One2many('is.ordre.travail.line.commentaire', 'line_id', 'Commentaires')




    def _get_last_state(self):
        last_state=""
        for obj in self:
            for line in obj.ordre_id.line_ids:
                if line.id==obj.id:
                    return last_state
                if line.state!='annule':
                    last_state=line.state
        return last_state


    @api.depends('state')
    def _compute_afficher_start_stop(self):
        for obj in self:
            last_state = obj._get_last_state()
            affiche=False
            if obj.state not in ('termine','annule'):
                if obj.libre:
                    affiche=True
                else:
                    if last_state=="":
                        affiche=True
                    else:
                        if last_state=="termine":
                            affiche=True
                        else:
                            if last_state in ('encours','pret') and obj.recouvrement>0:
                                affiche=True
            obj.afficher_start_stop = affiche


    @api.depends('temps_passe_ids','temps_passe_ids.temps_passe','duree_totale')
    def _compute_temps_passe(self):
        for obj in self:
            temps_passe = 0
            reste = 0
            for line in obj.temps_passe_ids:
                temps_passe+=line.temps_passe
            reste = obj.duree_totale-temps_passe
            obj.temps_passe=temps_passe
            obj.reste=reste


    @api.depends('duree_unitaire','ordre_id.quantite')
    def _compute_reste(self):
        for obj in self:
            duree_totale = obj.ordre_id.quantite*obj.duree_unitaire
            obj.duree_totale=duree_totale


    @api.depends('heure_debut','heure_fin')
    def _compute_duree_reelle(self):
        for obj in self:
            duree_reelle=0
            if obj.heure_fin and obj.heure_debut:
                duree_reelle = (obj.heure_fin-obj.heure_debut).total_seconds()/3600
            obj.duree_reelle=duree_reelle



    def get_employe_id(self):
        for obj in self:
            employes = self.env['hr.employee'].search([("user_id","=", self._uid)])
            for employe in employes:
                employe_id = employe.id
            return employe_id


    def start_action(self, employe_id=False):
        now = datetime.now()
        for obj in self:
            if not employe_id:
                employe_id = self.get_employe_id()
            if employe_id:
                self.stop_action(employe_id=employe_id, now=now)
                #** start d'une nouvelle ligne ********************************
                vals={
                    "line_id"    : obj.id,
                    "employe_id" : employe_id,
                    "heure_debut": now,
                }
                self.env['is.ordre.travail.line.temps.passe'].create(vals)
                obj.state="encours"
                #**************************************************************
        return True


    def stop_action(self, employe_id=False, now=False):
        if not now:
            now = datetime.now()
        for obj in self:
           if not employe_id:
                employe_id = self.get_employe_id()
        if employe_id:
            filtre=[
                ("employe_id","=", int(employe_id)),
                ("heure_fin" ,"=", False),
            ]
            lines = self.env['is.ordre.travail.line.temps.passe'].search(filtre)
            for line in lines:
                line.heure_fin = now
                test=True
                for l in line.line_id.temps_passe_ids:
                    if not l.heure_fin:
                        test=False
                        break
                if test:
                    if line.line_id.state not in ('termine','annule'):
                        line.line_id.state="pret"
        return True


    def end_action(self, employe_id=False):
        now = datetime.now()
        for obj in self:
            obj.state="termine"
            for line in obj.temps_passe_ids:
                if not line.heure_fin:
                    line.heure_fin=now
        return True


    def acceder_operation_action(self):
        for obj in self:
            res={
                'name': 'Opération',
                'view_mode': 'form',
                'res_model': 'is.ordre.travail.line',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
            }
            return res




class is_ordre_travail_line_temps_passe(models.Model):
    _name='is.ordre.travail.line.temps.passe'
    _description='Temps passé Ligne Ordre de travail'

    line_id     = fields.Many2one('is.ordre.travail.line', 'Ligne ordre de travail', required=True, ondelete='cascade')
    employe_id  = fields.Many2one("hr.employee", "Opérateur", required=True)
    heure_debut = fields.Datetime("Heure de début"          , required=True)
    heure_fin   = fields.Datetime("Heure de fin")
    temps_passe = fields.Float("Temps passé (HH:MM)", compute="_compute_temps_passe", readonly=True, store=True)


    @api.depends("heure_debut","heure_fin")
    def _compute_temps_passe(self):
        for obj in self:
            temps_passe = 0
            if obj.heure_debut and obj.heure_fin:
                #heure_debut = datetime.strptime(obj.heure_debut, "%Y-%m-%d %H:%M:%S")
                #heure_fin   = datetime.strptime(obj.heure_fin, "%Y-%m-%d %H:%M:%S")
                temps_passe = (obj.heure_fin - obj.heure_debut).total_seconds()/3600
            obj.temps_passe = temps_passe


class is_ordre_travail_line_commentaire(models.Model):
    _name='is.ordre.travail.line.commentaire'
    _description='Commentaires Ligne Ordre de travail'

    line_id     = fields.Many2one('is.ordre.travail.line', 'Ligne ordre de travail', required=True, ondelete='cascade')
    employe_id  = fields.Many2one("hr.employee", "Opérateur", required=True, default=lambda self: self.get_employe())
    date        = fields.Datetime("Date"                    , required=True, default=fields.Datetime.now)
    commentaire = fields.Text("Commentaire")

    def get_employe(self):
        employe_id=False
        filtre=[
            ('user_id', '=', self.env.user.id),
        ]
        employes=self.env['hr.employee'].search(filtre, limit=1)
        for employe in employes:
            employe_id=employe.id
        return employe_id

