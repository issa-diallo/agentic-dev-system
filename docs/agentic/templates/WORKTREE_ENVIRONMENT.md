# Worktree Environment — <project>

## Objective

Chaque worktree doit pouvoir être lancé et testé sans configuration manuelle répétitive.

## Setup

Command:
`scripts/worktree-setup.sh`

Responsibilities:
- installer dépendances ;
- préparer les variables d'environnement ;
- attribuer les ports ;
- préparer DB/services ;
- lancer migrations/seeds si pertinent.

## Dev

Command:
`scripts/worktree-dev.sh`

## Test

Command:
`scripts/worktree-test.sh`

## Down

Command:
`scripts/worktree-down.sh`

Responsibilities:
- arrêter services ;
- libérer ports ;
- nettoyer ressources temporaires sans détruire les données partagées.

## Isolation

- ports :
- database/schema :
- queues :
- temp files :
- containers :

## Gate

- [ ] setup reproductible
- [ ] dev démarre
- [ ] tests exécutables
- [ ] cleanup sûr
