# Workflow canonique

`PREPARE → BUILD → SHIP`

## PREPARE : entrée et DoR

Lire [SCALING](SCALING.md), choisir LIGHT/STANDARD/LARGE et préciser PRODUCT ou
[EXISTING](EXISTING_PROJECT.md). Consolider les six rubriques de
[PREPARE](templates/PREPARE.md) : PRD, TRD, APP_FLOW, UX_UI_BRIEF, BACKEND_SCHEMA,
IMPLEMENTATION_PLAN. Réutiliser décisions, ADR et artefacts existants, compléter
seulement les lacunes utiles ; aucun Research/Design/Plan supplémentaire par tâche.

DoR BUILD : AC clairs, dépendances connues, PREPARE PASS, PR_SPLIT PASS pour tout
BUILD non trivial, architecture/ADR compatibles, aucune décision différée requise
ouverte, fichiers identifiés, tests définis, risques critiques traités et aucun blocker.
Une validation prévue en Execute/Verify ne bloque pas le DoR si les protections
nécessaires sont définies. Présence d'un document ou contrôle de ressources ≠ PASS.

PR_SPLIT précède toute implémentation non triviale : une capacité autonome par PR,
DAG, vagues, contrats, fichiers, tests et propriétaire selon
[PULL_REQUESTS](PULL_REQUESTS.md). LIGHT conserve une entrée compacte dans le plan.
Les artefacts V1 restent utilisables pour reprise/legacy, sans gates supplémentaires.

## BUILD : attribution, exécution et validation

1. Vérifier le manifeste et l'entrée via `agentic-build.py` si disponible.
2. Préparer branche/worktree, owner unique, ressources et environnement reproductible
   avec `agentic-workspace.py` et le contrat d'environnement selon le risque.
3. Router les skills réellement disponibles et charger les instructions retenues ;
   router modèle/effort selon l'inventaire réel, sans changer fictivement le principal.
4. L'orchestrateur appelle les outils natifs de lancement ; `agentic-scheduler.py`
   coordonne les états mais sa CLI prepare n'est pas un lancement. Conserver un reçu
   observé, confirmer identité et arrêt, vérifier handoff et résultats avant acceptation.
5. Execute implémente le périmètre ; Verify obligatoire exécute les tests et produit
   les preuves adaptées. Fin d'agent ≠ PASS. Review indépendante, Critical/Major bloquants.
6. Vérifier Goal SATISFIED pour tâche longue/complexe. En LIGHT/STANDARD, une review
   indépendante avec profil Lead Tech peut aussi couvrir l'examen final ; LARGE/risque
   critique exige une seconde lecture par un reviewer distinct de l'implementer et
   du premier reviewer.

Les scripts ne sont pas une sandbox. Sans capacité native, signaler le fallback
mono-agent/séquentiel ; conserver une session de review indépendante ou BLOCKED.
Sans arrêt confirmé, ne pas relancer ni libérer l'owner après timeout/BLOCKED.
Skills selected/loaded/applied et modèle requested/observed sont des faits distincts.
Tokens/coûts/quota non observés restent null ou « non observable ».

## Dépendances, vagues et reprise

Lancer les PR structurantes d'abord. Paralléliser uniquement des unités indépendantes
ou des stacks à contrats stabilisés, périmètres disjoints, worktrees et ressources
isolés. Jamais deux écrivains dans le même worktree. Une dépendance structurante
échoue : bloquer les descendants et leur dispatch ; les unités indépendantes continuent.
Une stack peut se préparer sur parent stabilisé ; Verify/Review portent sur parent..enfant.
SHIP attend la fusion des parents et les preuves du delta sur la cible actualisée.

Handoff/checkpoint local : objectif, AC, phase, dernier PASS, décisions, chemins,
owner, agent observé, état Git, erreurs ouvertes, preuves et prochaines actions.
À la reprise, réconcilier Git/plan/runtime/ressources avant dispatch ; aucune relance
aveugle. Retour au cadrage seulement sur fait nouveau invalidant une contrainte,
seules les stories affectées BLOCKED ; mettre à jour ADR/architecture et valider.
L'autorisation existante suffit, aucun remplacement silencieux.

## SHIP et Definition of Done

Appliquer [COMMITS](../../COMMITS.md), garde staged et
[PULL_REQUESTS](PULL_REQUESTS.md) : PR_SCOPE PASS sur les SHA réels, Review
PASS/PASS_WITH_MINOR et examen final Lead Tech à jour, Verify PASS, Goal SATISFIED
si applicable, CI PASS, validation humaine si requise et autorisation de merge.
Après fusion autorisée : cleanup sûr, ownership libéré après arrêt confirmé.
DoD : Execute et Verify PASS, gates précédents satisfaits, merge et cleanup effectués.

États visibles : BACKLOG → PREPARE → BUILD → SHIP → READY_FOR_HUMAN → DONE ;
BLOCKED partout. Sous-états BUILD : ASSIGNED/RUNNING/COMPLETED, Verify/Review/Goal.
COMPLETED signifie fin d'exécution, pas gate de qualité ni autorisation de livraison.
Une mission limitée à une PR reste READY_FOR_HUMAN après gates et CI ; aucun DONE
sans fusion et cleanup. Aucun merge sans autorisation applicable.
