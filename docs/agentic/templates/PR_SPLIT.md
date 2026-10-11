# PR_SPLIT — <story>

`PR_SPLIT: DRAFT | PASS | BLOCKED`

Appliquer [PULL_REQUESTS](../PULL_REQUESTS.md) après Plan et avant Execute.
L'orchestrateur identifie les capacités ; le script vérifie la structure déclarée.
Manifeste, résultats et attestation restent locaux, exclus de Git. LIGHT : une
entrée compacte dans Plan, sans nouveau document ni délégation supplémentaire.
L’agent exporte cette entrée et la revue existante en JSON temporaires pour le
contrôle ; aucun document à rédiger par l’utilisateur ni nouvelle review.

## Manifeste version 1

Exemple valide : une capacité, une PR et ses tests.

```json
{
  "version": 1,
  "story": "S01",
  "capabilities": ["export-csv"],
  "prs": [{
    "id": "S01-PR1",
    "reason": "Exporter les résultats visibles en CSV",
    "capabilities": ["export-csv"],
    "files": ["src/export.py", "tests/test_export.py"],
    "acceptance": ["AC1: seules les lignes autorisées sont exportées"],
    "tests": ["python3 -m unittest tests.test_export"],
    "contracts": [{
      "name": "CSV v1",
      "compatibility": "Ajouter un export sans changer la lecture existante",
      "evidence": "Tests de format et autorisations dans test_export"
    }],
    "depends_on": [],
    "branch": "feat/S01-export",
    "worktree": "worktrees/S01-export",
    "implementer": "implementer-export"
  }]
}
```

Tous les champs montrés sont obligatoires. `contracts: []` signifie aucune interface
impactée. Les valeurs de `tests` sont des descriptions/commandes à lancer en Verify ;
le script ne les exécute jamais. `files` contient des chemins exacts relatifs à la
racine applicative, sans absolu, traversal ou `.git`. Aucun glob n'est interprété ;
les crochets de `app/users/[id]/page.tsx` sont littéraux. Inclure ancien et nouveau
chemins pour un rename. Les fichiers prévus non modifiés restent possibles ; la
revue vérifie les omissions par rapport aux AC.

Quatre capacités autonomes inscription/profil/sessions/fichiers privés donnent
quatre entrées PR, chaque `capabilities` contenant une seule valeur, et des AC/tests/
fichiers propres. `depends_on` référence les identifiants PR. Les contrats communs
restent stables et les dépendances explicites même sans fichier partagé. Les vagues
retournées ordonnent les travaux compatibles ; les fichiers communs sérialisent
sans inventer une dépendance métier. Branches/worktrees distincts ; un implementer
peut reprendre des unités successives, jamais plusieurs écrivains par worktree.

Champs optionnels : `indivisibility` si plusieurs capacités sont techniquement
indivisibles ; `size_exception` si taille réelle >3 fichiers/100 lignes ou binaire.
Leur forme est identique (reviewer requis seulement pour indivisibility) :

```json
{
  "constraint": "Le lecteur bascule avec la migration du format stocké",
  "evidence": "Test de migration : les versions mixtes échouent",
  "split_risk": "Une fusion partielle rend les données illisibles",
  "reviewer": "reviewer-migration"
}
```

Une exception ne permet pas de regrouper des capacités séparables. Le reviewer
indépendant vérifie la contrainte. Après fusion du parent, ajouter `merged_commit`
à son entrée : SHA complet effectivement fusionné dans la cible, même après squash.
Cette mutation change le hash du plan et exige une nouvelle attestation.

Les chemins worktree relatifs se résolvent depuis la racine Git de `--repo`,
indépendamment du dossier courant ; les alias physiques/symboliques sont refusés.

## Commandes et preuves

Depuis la racine Git applicative, Python 3 stdlib et Git requis. En LOCAL, adapter
le chemin du script à `.agentic-local/scripts/agentic-pr-check.py`, garder `--repo .` :

```bash
python3 scripts/agentic-pr-check.py split /chemin/local/pr-split.json
python3 scripts/agentic-pr-check.py ship /chemin/local/pr-split.json --repo . --pr S01-PR1 --base origin/main --head HEAD --target origin/main --review /chemin/local/pr-review.json
```

`--base` doit résoudre le merge-base réel cible/tête. Si la cible a avancé, fournir
ce SHA et examiner le diff complet. Verify/Review d'une stack peuvent examiner
parent..enfant ; Ship reste bloqué jusqu'à fusion des parents et actualisation.
Le reviewer vérifie que le SHA de fusion correspond à la PR déclarée.
Sortie JSON : gate, verdict, raison, hash canonique SHA256 du manifeste, vagues et
ordre. Ship ajoute SHA résolus, chemins/statuts, lignes, taille des blobs binaires
avant/après, dépendances et ancestralité. Aucun filtre externe Git ni commande du
manifeste exécuté ; aucune écriture Git. 0=PASS, 1=BLOCKED, usage CLI invalide=2.
Le contrôle de présence n'est pas ce gate.

## Attestation indépendante avant Ship

Produite séparément par le reviewer après examen réel, avec les SHA/hash issus du
contrôle. Chaque axe obligatoire, y compris N/A motivé. `contracts` couvre chaque
contrat exactement une fois ; `dependencies` chaque dépendance avec preuve PR/SHA
fusion. Listes vides si aucune interface/dépendance.

```json
{
  "pr": "S01-PR1",
  "plan_sha256": "<hash renvoyé par split>",
  "base": "<SHA base examiné>",
  "head": "<SHA tête examinée>",
  "target": "<SHA cible examinée>",
  "reviewer": "reviewer-export",
  "verdict": "PASS",
  "scope": {"pass": true, "evidence": "AC1 couverte par export.py et test_export.py"},
  "no_independent_changes": {"pass": true, "evidence": "Diff examiné : uniquement CSV, aucun refactoring annexe"},
  "size": {"pass": true, "evidence": "Deux fichiers, sous 100 lignes"},
  "indivisibility": {"pass": true, "evidence": "Une capacité avec son test : N/A motivé"},
  "contracts": [{"name": "CSV v1", "pass": true, "evidence": "Tests format/autorisations PASS, lecture inchangée"}],
  "dependencies": []
}
```

Tout changement de cible, même sans modification du merge-base, exige revue
actualisée des contrats et nouvelle attestation. Un nom dans JSON ne prouve pas
l'identité : l'orchestrateur vérifie la provenance
réelle de la session indépendante. Le script ne classe pas le métier. Findings
bloquants : `verdict: BLOCKED` ou axe `pass: false`, preuve et correction dans Review.
