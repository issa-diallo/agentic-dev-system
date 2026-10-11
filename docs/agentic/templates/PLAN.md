# Plan — <ticket> <titre>

## Statut

`PLAN: DRAFT | PASS | BLOCKED`

## Résultat attendu

<Description observable du résultat.>

## Changements

### 1. <étape>
- fichier(s) :
- modification :
- raison :

### 2. <étape>
- fichier(s) :
- modification :
- raison :

## Données / migrations

- changement de schéma :
- migration :
- compatibilité :
- rollback :

## API / contrats

- endpoints :
- payloads :
- erreurs :
- compatibilité :

## Sécurité

- auth :
- authorization :
- tenant isolation :
- validation :
- human-in-the-loop :

## Tests prévus

- unit :
- integration :
- contract :
- e2e :
- build/lint :

## Risques et mitigations

- risque :
  - mitigation :

## Validations différées de l’architecture

| Hypothèse / risque | Responsable / rôle | Échéance | Vérification | Action si échec |
|---|---|---|---|---|
| … | … | Execute/Verify ou suivi produit | … | … |

Reprendre les entrées pertinentes du registre Architecture ; pas de preuve
préalable exigée pour leur planification. Les contraintes impératives sont
vérifiées avant l’exposition ou l’engagement concerné. Les coûts d’exploitation
et optimisations après implémentation ont un suivi produit identifié.

## Fichiers prévus

- create:
- modify:
- delete:

## Plan Gate

- [ ] étapes actionnables
- [ ] tests prévus
- [ ] sécurité couverte
- [ ] dépendances résolues
- [ ] aucun blocker

Verdict : PASS / BLOCKED

## Complexité et contrat d’exécution

- complexité : Faible / Moyenne / Élevée / Critique ; mode / raison :
- dernier gate PASS, compatibilité architecture/ADR, blockers :
- budget observable (ou non observable), indicateurs et critère d’arrêt :
- modèle/niveau recommandé, disponible, justification et escalade :
- délégation : objectif, contraintes, AC, validations et livrable :
- agent/rôle, entrées, sorties, fichiers autorisés, outils et validation :
- dépendances, ordre, contrats stables, worktree et collisions évitées :
- commandes ciblées et evidence attendue par AC :

## Découpage en unités de PR

La story contient le besoin ; elle ne fixe pas une PR unique. Identifier les
capacités métier autonomes et leurs AC. Research/Design communs peuvent être
hérités par plusieurs unités ; garder fichiers, tests, contrats et Plan par PR.
Après Plan, remplir [PR_SPLIT](PR_SPLIT.md) : capacité → PR → AC/tests/fichiers,
DAG, ordre de fusion, vagues, stack, branche/worktree et implementer.
Une capacité séparable par PR ; code, tests et migrations indispensables ensemble.
En LIGHT, une entrée compacte dans Plan suffit. PR_SPLIT PASS avant Execute.
