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

Pour une capacité MEDIUM préparée, l'option [missions successives](#missions-successives-dune-pr-préparée)
réutilise une tâche/PR : tests métier seuls avant code, handoff contrôlé,
implementer avec tests verrouillés, Verify puis reviewer indépendant en lecture
seule. Chaque mission est routée séparément ; PREPARE reste contrôlé par
l'orchestrateur. Les tickets simples réduisent les délégations au nécessaire sans
supprimer la revue. Aucun rouge/vert obligatoire. Historique et snapshots servent
la reprise après arrêt confirmé ; preuve périmée ou blocage arrêtent le flux.
Le résultat prépare SHIP et ne remplace aucun de ses gates.

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
À la création de la PR et avant READY_FOR_HUMAN, synchroniser et relire les
critères d’acceptation du ticket selon [TICKETS](TICKETS.md#suivre-les-critères-pendant-la-livraison) :
cocher les AC prouvés, laisser ouverts ceux qui attendent une validation, et
répercuter les preuves invalidées après correction. L’orchestrateur vérifie cette
concordance ; une mise à jour requise non confirmée bloque la livraison prête.
Après fusion autorisée : cleanup sûr, ownership libéré après arrêt confirmé.
DoD : Execute et Verify PASS, gates précédents satisfaits, merge et cleanup effectués.

États visibles : BACKLOG → PREPARE → BUILD → SHIP → READY_FOR_HUMAN → DONE ;
BLOCKED partout. Sous-états BUILD : ASSIGNED/RUNNING/COMPLETED, Verify/Review/Goal.
COMPLETED signifie fin d'exécution, pas gate de qualité ni autorisation de livraison.
Une mission limitée à une PR reste READY_FOR_HUMAN après gates et CI ; aucun DONE
sans fusion et cleanup. Aucun merge sans autorisation applicable.

## Missions successives d'une PR préparée

Opt-in : ajouter `"missions": {"enabled": true}` à `run` dans la configuration.
`delegate` (et `quick` hors TDD explicite) enchaîne pour chaque PR **test-author →
implementer → Verify → reviewer**. Chaque mission BUILD utilise le routage existant,
sans changement manuel du modèle principal. PREPARE et SHIP restent contrôlés par
l'orchestrateur. L'option absente/désactivée conserve le comportement historique.

Une seule entrée PR_SPLIT et un seul worktree : les missions sont des étapes de
la tâche scheduler existante, jamais des PR distinctes. L'auteur écrit seulement
les tests des RM/AC préparés ; leur résultat initial est consigné, rouge ou vert,
sans commit exigé. L'implementer reçoit ces tests verrouillés. Les modifications
du produit par l'auteur ou des tests transmis par l'implementer bloquent le flux.
Sans tests dans le périmètre (documentation, par exemple), test-author est omis.
Les petits tickets peuvent garder l'option désactivée et appliquer les missions
nécessaires selon le skill, avec revue indépendante obligatoire.

Verify doit passer avant la revue. Le reviewer utilise une nouvelle identité
runtime observée et le preset Codex en lecture seule déjà requis (ou la revue
Claude tool-free du [cycle optionnel](DELEGATION.md#cycle-de-revue-corrective-borné)) ; sans harnais
adéquat, BLOCKED sans fallback. Son handoff contient `review.verdict` et
`review.findings` (sévérité/message). Une sortie zéro, un rapport absent ou PASS
avec Critical/Major ne valident rien. Le contrôleur confronte runtime, contenu
inchangé, rapport et preuves Verify sur HEAD/base/hash du plan courants. Les
constats restent des déclarations : l'orchestrateur vérifie les AC et SHIP.

L'état scheduler conserve historique, reçus, arrêts et preuves par mission. La
reprise utilise le même manifeste et `--state` : elle valide une mission arrêtée
sans la rejouer puis poursuit les étapes prêtes. Agent actif, arrêt inconnu,
BLOCKED ou mutation de HEAD/plan/contenu/configuration exigent réconciliation ;
aucune relance aveugle ni libération sur timeout seul. Après correction et
diagnostic, l'API `Scheduler.requeue` construite avec la même configuration et le
même contexte d'exécution exige ses preuves habituelles et conserve le contrat
de mission. La CLI scheduler isolée ne charge pas cette configuration du runner ;
ne pas l'utiliser pour cette réconciliation ni effacer l'état pour contourner un blocage.
`requeue` reprend la même mission et ne renouvelle pas Verify. Après une correction
du produit consécutive à une revue, les anciennes preuves sont périmées : conserver
un checkpoint BLOCKED. Le cycle optionnel `run.review_cycle` permet un retour
explicite via `Scheduler.request_correction` : findings transmis, tests verrouillés,
budget/tentatives persistants, Verify puis revue renouvelées sur la révision courante.
Sans cette option, conserver la réconciliation manuelle décrite ci-dessous. L'orchestrateur organise un retour explicite et contrôlé à
l'implémentation/Verify avant une nouvelle revue ; ni relance automatique du reviewer
ni édition manuelle de l'état pour présenter l'ancien Verify comme actuel.
Les restrictions tests/produit sont des comparaisons de contenu, pas une sandbox
du test-author ; toute mutation détectée reste à examiner. Le reviewer conserve
la sandbox du harnais. Les sessions internes CLI inconnues restent null.
Les dépôts contenant des gitlinks (sous-modules, même désinitialisés) sont bloqués
avant lancement en mode missions ; le contrôle récursif n'est pas pris en charge.
Le flux historique reste inchangé.

La réussite du runner prépare SHIP ; elle ne produit ni commit, ni publication,
ni fusion. Le skill obtient encore commit final unique, Review/Lead Tech,
PR_SCOPE et CI frais avant READY_FOR_HUMAN. `--dry-run` ne prépare que le premier
lancement et ne constitue aucune preuve de ce flux complet.
