# Research — DOC-architecture-fast

RESEARCH: PASS

Entrée EXISTING, mode STANDARD : modification de la méthode documentaire
existante, sans changement de stack ni de contrats logiciels. Ticket #15 (initialement local) :
demande utilisateur du 11 octobre 2026, simplifier Architecture et supprimer
les boucles de preuves et les remises en cause de ses outils.

## Constats

- METHOD exige un ADR par catégorie technique et la justification des alternatives.
- ARCHITECTURE impose deux stacks comparées, coûts et une longue checklist.
- ADR impose deux options même si le choix a déjà été donné.
- WORKFLOW permet le retour Research/Plan → Architecture sans critère précis.
- Installateur distribue les templates et règles ; tests/test_context.py vérifie
  leur héritage dans PRODUCT, EXISTING et LOCAL.

## Critères d’acceptation

1. Architecture peut PASS avec un cadrage bref et les choix utilisateur enregistrés.
2. Aucun benchmark, prototype, coût chiffré ou preuve d’exécution requis à ce gate.
3. ADR limités aux arbitrages ayant des conséquences durables ; pas un ADR par outil.
4. Toute validation différée a un responsable, une échéance et un effet en cas d’échec.
5. Blocage seulement sur contradiction concrète indispensable ou risque critique
   sans mitigation ; pas de remplacement silencieux ni de revalidation répétée.
6. Règles cohérentes, installation préservée, contrôles exécutés et review indépendante.

Auth, données sensibles, tenant et secrets : aucun traitement ajouté. Actions
externes : aucune publication ni fusion prévue. Rollback : revert du diff documentaire.
Limite : les contrôles statiques ne prouvent pas la conduite de modèles dans les
deux projets signalés, qui ne sont pas accessibles dans cette mission.
