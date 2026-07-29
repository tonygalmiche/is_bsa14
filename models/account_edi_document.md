# Erreur "NameError: name 'error' is not defined" à l'ouverture d'une facture client

## Symptôme

À l'ouverture d'une facture client (uniquement, pas les factures fournisseur),
une erreur JS apparaît :

```
Error: NameError: name 'error' is not defined
PY_ensurepy@.../web.assets_backend.js
py.evaluate@.../web.assets_backend.js
_setDecorationClasses@.../web.assets_backend.js
_renderRow@.../web.assets_backend.js
```

## Cause

Le module standard `account_edi` affiche un onglet "EDI Documents" sur les
factures, avec une liste (`account.edi.document`) dont la ligne `<tree>` a :

```xml
<tree ... decoration-danger="error">
    <field name="name"/>
    ...
    <field name="error" invisible="1"/>
```

Le champ `name` de `account.edi.document` est `related='attachment_id.name'`.

Si `attachment_id` pointe vers un `ir.attachment` qui n'existe plus (pièce
jointe supprimée manuellement, par exemple lors d'un nettoyage de base de
test), la lecture du champ `name` lève un `MissingError` côté serveur. Ça
casse la lecture de la ligne : le champ `error` n'arrive jamais jusqu'au
navigateur, et le JS plante en essayant d'évaluer la décoration
`decoration-danger="error"` sur cette ligne.

C'est pour ça que le bug touche quasi toutes les factures clients récentes
dès qu'un format électronique (Factur-X) est activé sur le journal de vente :
chaque facture a un `account.edi.document`, et il suffit qu'un seul
`attachment_id` soit orphelin pour déclencher l'erreur.

## Diagnostic (SQL)

```sql
-- Nombre de account.edi.document dont l'attachment_id est cassé
SELECT count(*) FROM account_edi_document ed
WHERE ed.attachment_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ir_attachment a WHERE a.id = ed.attachment_id);
```

## Solution

Vider les `attachment_id` orphelins (le fichier lié étant de toute façon
supprimé, la référence ne sert plus à rien) :

```sql
UPDATE account_edi_document
SET attachment_id = NULL
WHERE attachment_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ir_attachment a WHERE a.id = account_edi_document.attachment_id);
```

Origine constatée sur `bsa14-acier` : suppression manuelle de pièces jointes
(`ir.attachment`) sur une base de test, sans nettoyer les
`account.edi.document` qui les référençaient.
