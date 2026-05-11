# Prospect Finder BTP

Outil d'extraction automatique de prospects BTP depuis l'API officielle du gouvernement français.  
**100% gratuit — aucune installation requise — tourne entièrement sur GitHub.**

---

## Comment ça marche ?

Le script interroge l'API publique [`recherche-entreprises.api.gouv.fr`](https://recherche-entreprises.api.gouv.fr) pour extraire des entreprises BTP françaises (0 à 49 salariés) ayant un site web, puis génère un fichier CSV prêt à importer dans Clay.

---

## 1. Forker le repo

1. Cliquez sur le bouton **Fork** en haut à droite de cette page
2. Choisissez votre compte GitHub comme destination
3. Validez — vous avez maintenant votre propre copie du projet

---

## 2. Lancer une extraction depuis GitHub Actions

1. Dans votre repo, cliquez sur l'onglet **Actions**
2. Dans la colonne de gauche, cliquez sur **Extract BTP Prospects**
3. Cliquez sur le bouton **Run workflow** (à droite)
4. Renseignez les paramètres souhaités :
   - **Nombre max de prospects** (défaut : 500)
   - **Départements** : codes séparés par virgule, ex: `75,69,13` (vide = France entière)
   - **Uniquement avec site web** : `true` ou `false`
5. Cliquez sur **Run workflow** (bouton vert)

Le job démarre en quelques secondes. Vous pouvez suivre la progression en cliquant sur le run en cours.

---

## 3. Télécharger le CSV

1. Une fois le job terminé (icône verte ✓), cliquez sur le run
2. Faites défiler jusqu'à la section **Artifacts** en bas de page
3. Cliquez sur **prospects-btp-XXXXXXX** pour télécharger l'archive ZIP
4. Décompressez — vous obtenez le fichier `prospects_btp_YYYY-MM-DD.csv`

Le CSV est encodé UTF-8 avec BOM : il s'ouvre directement dans Excel et s'importe sans problème dans Clay.

---

## 4. Modifier les paramètres par défaut

Ouvrez le fichier `extract.py` et modifiez les variables en haut du fichier :

```python
# Codes NAF à cibler
NAF_CODES = ['4120A', '4321A', ...]

# Tranches d'effectif (NN=0, 00=0, 01=1-2, 02=3-5, 03=6-9, 11=10-19, 12=20-49)
TRANCHES_EFFECTIF = ['NN', '00', '01', '02', '03', '11', '12']

# Départements ciblés (vide = France entière)
DEPARTEMENTS = ['75', '69']

# Nombre maximum de prospects
MAX_RESULTS = 500

# Filtrer uniquement les entreprises avec site web
ONLY_WITH_WEBSITE = True
```

---

## Colonnes du CSV exporté

| Colonne | Description |
|---|---|
| Nom entreprise | Raison sociale |
| SIRET | Numéro SIRET du siège |
| Code NAF | Code activité principale |
| Dirigeant | Prénom + Nom du dirigeant (si disponible) |
| Adresse | Adresse complète du siège |
| Ville | Commune du siège |
| Département | Code département |
| Effectif | Tranche de salariés |
| Site web | URL du site internet |

---

## Source de données

API officielle française : **recherche-entreprises.api.gouv.fr**  
Données issues du Registre National des Entreprises (RNE) — accès gratuit, sans clé API.
