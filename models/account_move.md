# Position fiscale incorrecte à la création d'une facture fournisseur

## Symptôme

À la création manuelle d'une facture fournisseur, dès que l'on sélectionne un
fournisseur, le champ **Position fiscale** se positionne automatiquement sur
**« EU privé »**, alors que ce fournisseur n'a aucune position fiscale forcée
sur sa fiche et est basé en France.

## Cause

Ce n'est pas un bug : c'est la conséquence de la configuration des positions
fiscales combinée à l'absence de numéro de TVA sur la fiche du fournisseur.

### Configuration actuelle (table `account_fiscal_position`)

| id | Nom                                  | auto_apply | vat_required | Pays / Groupe                |
|----|---------------------------------------|:----------:|:------------:|-------------------------------|
| 1  | Domestique - France                   | oui        | **oui**       | France                        |
| 2  | EU privé                              | oui        | non           | Groupe Europe (inclut la France) |
| 3  | Intra-EU B2B                          | oui        | oui           | Groupe Europe                 |
| 4  | Import/Export Hors Europe + DOM-TOM   | oui        | non           | —                              |

La France fait partie du groupe de pays "Europe" (`res.country.group` id 1),
utilisé par les règles "EU privé" et "Intra-EU B2B".

### Logique standard Odoo

Fichier `addons/account/models/partner.py`, classe `AccountFiscalPosition`,
méthode `get_fiscal_position()` :

```python
# partner manually set fiscal position always win
if delivery.property_account_position_id or partner.property_account_position_id:
    return delivery.property_account_position_id or partner.property_account_position_id

# First search only matching VAT positions
vat_required = bool(partner.vat)
fp = self._get_fpos_by_region(delivery.country_id.id, delivery.state_id.id, delivery.zip, vat_required)

# Then if VAT required found no match, try positions that do not require it
if not fp and vat_required:
    fp = self._get_fpos_by_region(delivery.country_id.id, delivery.state_id.id, delivery.zip, False)
```

Et `_get_fpos_by_region()` :

```python
base_domain = [
    ('auto_apply', '=', True),
    ('vat_required', '=', vat_required),
    ('company_id', 'in', [self.env.company.id, False]),
]
...
domain_country = base_domain + [('country_id', '=', country_id)]
domain_group = base_domain + [('country_group_id.country_ids', '=', country_id)]

fpos = self.search(domain_country + state_domain + zip_domain, limit=1)
...
# fallback: country group with no state/zip range
if not fpos:
    fpos = self.search(domain_group + null_state_dom + null_zip_dom, limit=1)
```

Odoo calcule `vat_required = bool(partner.vat)`, c'est-à-dire : **le
fournisseur a-t-il un numéro de TVA renseigné sur sa fiche ?**

- Si le fournisseur **français n'a pas de numéro de TVA** (`partner.vat` vide),
  `vat_required` vaut `False`.
- Odoo cherche alors une position fiscale pour le pays France avec
  `vat_required = False`.
- « Domestique - France » exige `vat_required = True` → elle est donc
  **écartée** du résultat de recherche.
- La seule position restante qui correspond (via le fallback sur le groupe de
  pays) est **« EU privé »** (`vat_required = False`, s'applique à tout le
  groupe Europe, dont la France).

**Résultat : tout fournisseur français dont la fiche ne contient pas de
numéro de TVA se voit attribuer automatiquement « EU privé » au lieu de
« Domestique - France ».**

## Impact mesuré sur la base `bsa14-acier`

- Fournisseurs français (pays = FR, `supplier_rank > 0`) : **148**
- Parmi eux, fournisseurs **sans numéro de TVA renseigné** : **86** (~58 %)

Requête utilisée :

```sql
select count(*) from res_partner p
join res_country c on c.id = p.country_id
where c.code = 'FR' and (p.vat is null or p.vat = '') and p.supplier_rank > 0;
```

## Solutions possibles

1. **Décocher "Assujetti à la TVA" (`vat_required`) sur « Domestique -
   France »**, si cette position doit s'appliquer à tout fournisseur
   français, qu'il ait ou non un numéro de TVA.
   - Impact : il faut alors vérifier qu'aucune autre règle ne dépend de ce
     critère pour distinguer les cas domestiques des cas intracommunautaires.
2. **Renseigner le numéro de TVA** sur les fiches des fournisseurs français
   concernés (le plus correct fiscalement, mais demande un travail de
   fiabilisation des données sur 86 fiches).
3. **Forcer la position fiscale directement sur la fiche du fournisseur**
   (`property_account_position_id`), ce qui prime toujours sur les règles
   automatiques (`get_fiscal_position` retourne immédiatement cette valeur
   sans même évaluer les règles `auto_apply`).

La solution 1 est la plus simple à appliquer immédiatement et corrige le
problème pour tous les fournisseurs actuels et futurs sans TVA. La solution 3
reste utile au cas par cas pour des fournisseurs ayant un besoin spécifique.

---

# Compte 707100 sur les factures fournisseur générées depuis une réception

## Symptôme

Avec `facturation_picking_action` (facturation depuis une réception), la
facture fournisseur générée n'utilise pas le compte de la fiche article mais
le compte **707100** (compte de vente), avec en plus une position fiscale/TVA
incorrectes.

## Cause

Dans `facturation_reception_action()` ([stock_picking.py](stock_picking.py)),
le compte de la ligne de facture était calculé à partir du compte de
**revenu** du produit au lieu de son compte de **charge** :

```python
account_id = move.product_id.property_account_income_id.id \
    or move.product_id.categ_id.property_account_income_categ_id.id
```

`property_account_income_id` sert aux factures de vente (d'où 707100). De
plus, le compte et les taxes étaient injectés tels quels, sans jamais
appliquer le mapping de la position fiscale du fournisseur
(`account.fiscal.position.map_account` / `map_tax`).

## Correctif appliqué

- Compte de **charge** utilisé (`property_account_expense_id` /
  `property_account_expense_categ_id`) au lieu du compte de revenu.
- Position fiscale du fournisseur calculée via `get_fiscal_position(partner.id)`.
- Compte et taxes passés dans `map_account()` / `map_tax()` avant création des
  lignes, et `fiscal_position_id` renseigné sur la facture.

## Points de vigilance

- `facturation_livraison_action()` (factures client) utilise correctement
  `property_account_income_id` : non modifiée.
- Les factures déjà générées avec le compte 707100 ne sont pas corrigées
  automatiquement ; elles doivent être reprises manuellement.
