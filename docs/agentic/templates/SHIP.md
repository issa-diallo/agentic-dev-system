# Ship — <story>

## Preconditions

- [ ] PREPARE PASS, six rubriques/sources réutilisées accessibles
- [ ] PR_SPLIT PASS pour BUILD non trivial
- [ ] PR_SCOPE PASS sur le manifeste et les SHA actuels
- [ ] Execute PASS
- [ ] Verify PASS
- [ ] Review PASS ou PASS_WITH_MINOR
- [ ] Goal SATISFIED si applicable
- [ ] aucun Critical/Major ouvert

## Git

- branch :
- commit :
- remote :

## Pull Request

- [ ] Un objectif précis ; 1 à 3 fichiers et diff court visés
- [ ] Aucun artefact de préparation, plan ou rapport de mission dans le diff ;
  preuves conservées localement et transmises au reviewer hors du diff
- [ ] `deliverables` indépendant couvre chaque chemin réel avec preuve de son
  utilité en production ou pour les tests associés ; aucun script de travail
- [ ] Tout dépassement est expliqué sans omettre tests ni migration
- [ ] Un commit logique prévu après squash, selon
  [PULL_REQUESTS](../PULL_REQUESTS.md)

- URL :
- issue liée :
- description complète :
- evidence liée :
- screenshots si UI :

## Contrôle de périmètre PR_SCOPE

- manifeste / hash canonique, unité PR, raison métier principale :
- capacités, AC/tests/fichiers/contrats propres ; six rubriques/sources réutilisées :
- commande `agentic-pr-check.py ship` et JSON PASS/BLOCKED :
- SHA base réelle, tête et cible actualisées ; renames/binaires/mesures réelles :
- dépassement justifié et revu, aucun refactoring/capacité indépendante :
- parents effectivement fusionnés (URL PR + SHA), ordre et contrats compatibles :
- attestation reviewer indépendante, hash/SHA exacts, preuves explicites par axe :
- provenance session/identité vérifiée par orchestrateur :

Artefacts V1 facultatifs comme sources legacy ; aucun gate Research/Design/Plan
supplémentaire.

Voir [PR_SPLIT](PR_SPLIT.md). BLOCKED empêche READY_FOR_HUMAN. Ni ce contrôle
ni une attestation déclarative ne remplacent Verify/Review/CI/Lead Tech. Après
changement du manifeste ou des SHA, revalider sans réécrire les PR existantes.

## CI

| Check | Result |
|---|---|
| Agentic method | PASS/FAIL |
| Tests | PASS/FAIL |
| Build | PASS/FAIL |

## Examen final Lead Tech

- reviewer et indépendance selon le mode :
- rapport historique / verdict / risques résiduels :
- attestation finale hors diff (session ou support externe autorisé) :
- SHA base et tête examinés, identiques à la PR actuelle :
- CI de cette révision :
- corrections demandées et revalidation :
- [ ] verdict favorable à jour, aucun blocker ni Critical/Major ouvert

Voir le [profil Lead Tech](../roles/REVIEWER.md). Ce contrôle de Ship ne remplace
ni Review ni l'autorisation de fusion. Après tout nouveau commit, revalider.

## Deployment / migration

- migration :
- config/env :
- rollback :

## Human gate

- [ ] validation humaine obtenue si requise

## Merge

- strategy :
- merge commit :
- date :

## Cleanup

- [ ] worktree supprimé
- [ ] ressources temporaires nettoyées
- [ ] branche locale nettoyée
- [ ] STATUS mis à jour
- [ ] issue fermée

Verdict : READY_FOR_HUMAN / DONE / BLOCKED

Mission limitée à une PR : READY_FOR_HUMAN après tous les gates et CI.
DONE exige également fusion autorisée et cleanup.
