# Reusable Agentic Development Method

Cette méthode est conçue pour être copiée dans n'importe quel dépôt logiciel.

## Objectif

Préparer suffisamment les tâches pour que l'implémentation soit rapide, claire et presque mécanique.

La méthode doit fonctionner pour les petits comme les gros projets. La profondeur change, pas l'ordre mental.

## Pipeline canonique

```text
PRD
 ↓
Stories
 ↓
Story Review
 ↓
Architecture
 ↓
Design System
 ↓
Research
 ↓
Design
 ↓
Plan
 ↓
Worktree Setup
 ↓
Execute
 ↓
Verify
 ↓
Review
 ↓
Goal satisfied?
 ↓
Ship
```

Voir `SCALING.md` pour choisir LIGHT, STANDARD ou LARGE.

## Règle d'or

Aucune phase ne doit inventer ce que la phase précédente devait décider.

- Execute ne redéfinit pas le besoin.
- Execute ne change pas la stack.
- Plan ne redéfinit pas l'architecture.
- Design ne réécrit pas les critères d'acceptation.
- Research ne modifie pas silencieusement le scope.
- Verify exige des preuves.
- Review ne se contente pas des affirmations de l'implementer.
- Ship ne masque pas une review ou un goal en échec.

## Entrées dans la méthode

- Nouveau produit ou gros périmètre : pipeline produit complet.
- Ticket cadré sur projet existant, même sans documentation produit : appliquer
  [EXISTING_PROJECT.md](EXISTING_PROJECT.md) et commencer à Research.

Dans ce second cas, consigner le cadrage, l’architecture observée et la justification
par ticket dans Research. Aucun PASS produit fictif n’est nécessaire. Les gates
par story restent obligatoires ; une information indispensable manquante bloque.

## Gate universel

Chaque phase applicable au parcours choisi doit répondre à :
1. Quel artefact a été produit ?
2. Quel est le verdict : PASS ou BLOCKED ?
3. Quelles contraintes deviennent obligatoires pour la suite ?

## Phase Produit

### 1. PRD
Définir problème, utilisateurs, valeur, scope, non-scope, contraintes, risques et succès.

Sortie : `docs/product/PRD.md`.

### 2. Stories
Découper le PRD en tranches fonctionnelles livrables et testables.

Sortie : `docs/product/STORIES.md`.

### 3. Story Review
Challenger couverture, dépendances, taille, critères et ordre.

Sortie : `docs/product/STORY_REVIEW.md`.

### 4. Architecture
Fixer une direction exploitable : choix retenus, responsabilités, données et
flux majeurs, protections pertinentes, livraison et stratégie de tests.
Respecter les outils choisis par l’utilisateur. Consigner les hypothèses et
validations différées avec responsable, échéance et action si échec.
Une vérification de cohérence suffit avant PASS et la phase suivante.
Les benchmarks, prototypes, preuves et coûts chiffrés ne sont pas requis ici.
Créer des ADR courts uniquement pour les arbitrages aux conséquences durables.

Sorties :
- `docs/product/ARCHITECTURE.md`
- `docs/adr/*.md`

### 5. Design System
Fixer le langage d'interface commun avant les designs de story.

Sortie : `docs/product/DESIGN_SYSTEM.md`.

## Phase Story

### 6. Research
Analyser le repo réel, les conventions, dépendances, tests, risques et points d'intégration.

Sortie : `research.md`.

### 7. Design
Définir précisément écrans, états, flux, contrats ou comportements.

Sortie : `design.md`.

### 8. Plan
Transformer les décisions précédentes en séquence d'implémentation concrète.

Un bon plan doit minimiser les décisions restantes pendant Execute.

Sortie : `plan.md`.

### 9. Worktree Setup
Pour une story significative, préparer un environnement isolé et reproductible.

Référence : `templates/WORKTREE_ENVIRONMENT.md`.

### 10. Execute
Implémenter le plan. Rester dans le scope. Ajouter les tests.

Sorties :
- code ;
- tests ;
- `handoff.md`.

### 11. Verify
Prouver que le résultat fonctionne.

Evidence possibles :
- tests ;
- build ;
- browser flow ;
- API calls ;
- screenshots ;
- logs ;
- mesures de performance.

Sortie : `verify.md`.

### 12. Review
Faire une revue indépendante contre story, architecture, plan, evidence et diff.

Sortie : `review.md`.

### 13. Goal satisfied?
Pour une tâche longue ou complexe, vérifier les critères mesurables du goal.

Sortie : `goal.md`.

Si aucun goal spécifique n'est nécessaire, les critères d'acceptation + Verify + Review font office de goal.

### 14. Ship
Créer commits/PR, passer CI, obtenir validation humaine si requise, merger et nettoyer.

## Préparation vs exécution

Le système optimise volontairement le travail avant Execute.

```text
Plus de clarté avant Execute
        ↓
moins de décisions pendant Execute
        ↓
moins de retours arrière
        ↓
moins de tokens gaspillés
        ↓
implémentation plus rapide
```

## Context hygiene

Avant les longues tâches, appliquer `CONTEXT.md`.

## Safety

Appliquer `SAFETY.md` et utiliser des hooks quand le harness le permet.

## Ce qui est interdit

- Idea -> Execute
- Story -> Execute sans Research/Design/Plan
- Execute -> changement silencieux de stack
- "ça marche" sans Verify/Evidence
- Implementer -> auto-approval
- tests non exécutés présentés comme PASS
- merge avec Critical/Major ouvert
- merge d'une story BLOCKED

## Contrat des décisions d’architecture

ARCHITECTURE suit `templates/ARCHITECTURE.md`. Un choix utilisateur fait autorité :
l’enregistrer sans redemander ses motivations ou son approbation. Sans choix,
recommander une solution avec une raison courte. Comparer seulement un arbitrage
encore ouvert ; pas d’ADR par outil ni de dossier de preuves avant développement.
Un outil décidé ne déclenche aucun test de qualification en Architecture/ADR.
Exception uniquement pour un cas particulier indispensable : contradiction
concrète ou risque critique sans mitigation, test minimal et critère d’arrêt
documentés. La préférence de l’agent ou une compatibilité non encore testée
ne suffit pas à imposer ce test. Une fois les choix utiles consignés et les
principes cohérents, terminer Architecture et avancer.
Sans changement structurant sur l’existant, le socle observé suffit.

Un ADR court trace les arbitrages durables : frontières majeures, isolation des
données, contrats partagés, engagements difficilement réversibles ou remplacement
d’une décision approuvée. Regrouper les choix liés ; aucun gate supplémentaire.

Les validations de faisabilité sont réalisées en Execute/Verify de la story
concernée. Coûts d’exploitation et optimisations peuvent être suivis par le
produit après implémentation. Reporter chaque validation dans Plan puis Verify.
Sécurité, intégrité, contraintes légales et budget impératif se vérifient avant
l’exposition, l’action irréversible ou l’engagement concerné.

BLOCKED exige une contradiction concrète empêchant l’incrément ou un risque
critique sans mitigation. Documenter fait, contrainte violée, périmètre affecté
et résolution attendue ; les inconnues reportables ne bloquent pas.
Après PASS, seul un fait nouveau invalidant une contrainte justifie le retour.
Une préférence ou une preuve absente ne suffit pas. Changement approuvé à revoir :
seules les stories affectées sont BLOCKED, ADR et ARCHITECTURE mis à jour,
validation du nouveau choix avant reprise, sans remplacement silencieux.
L’autorisation utilisateur déjà donnée suffit ; ne pas la demander de nouveau.
