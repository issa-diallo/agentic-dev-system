# Méthode de développement agentique

## Pipeline canonique

`PREPARE → BUILD → SHIP`

Choisir LIGHT, STANDARD ou LARGE selon [SCALING](SCALING.md).
La profondeur change, les garanties restent obligatoires. Chaque phase applicable
produit un artefact et un verdict PASS/BLOCKED ; seule PASS autorise la suivante.
Review accepte PASS_WITH_MINOR, jamais Critical/Major ouvert.

## PREPARE

Consolider le besoin et la préparation dans six rubriques : **PRD**, **TRD**,
**APP_FLOW**, **UX_UI_BRIEF**, **BACKEND_SCHEMA**, **IMPLEMENTATION_PLAN**.
Utiliser [PREPARE](templates/PREPARE.md) ou référencer des documents existants.
Ce sont des rubriques, pas six gros fichiers obligatoires. N/A exige une raison.

Nouveau produit/gros périmètre : préparer besoin, parcours, architecture, données,
interface et incréments à la profondeur utile. Sur existant, réutiliser décisions,
ADR, conventions et artefacts validés ; compléter uniquement le delta du ticket
selon [EXISTING_PROJECT](EXISTING_PROJECT.md). Ne pas recréer Research/Design/Plan
pour chaque tâche, ni inventer un PASS historique. Un template vide n'est pas une preuve.

PR_SPLIT est un gate avant BUILD non trivial, intégré à IMPLEMENTATION_PLAN :
capacités autonomes, AC/tests/fichiers/contrats, DAG, vagues, branche/worktree et
owner. Appliquer [PULL_REQUESTS](PULL_REQUESTS.md). Les décisions nécessaires,
risques critiques et blockers sont résolus avant PASS ; les preuves de faisabilité
planifiées en Verify ne constituent pas de nouveaux gates de qualification.

## BUILD

Implémenter les capacités prévues dans des worktrees isolés, un seul écrivain par
worktree. Préparer l'environnement reproductible selon le risque et la durée.
L'orchestrateur vérifie l'entrée BUILD, réserve ressources et ownership, route
skills et modèles, puis lance réellement les sous-agents avec les outils natifs
exposés. Il conserve identifiants observés et handoffs ; un nom dans un fichier
ne prouve pas un lancement. Sans ces outils, repli séquentiel explicite et session
indépendante pour Review ; ne jamais inventer de délégation ou de modèle utilisé.

Les commandes `agentic-build.py`, `agentic-workspace.py`, `agentic-skills.py`,
`agentic-models.py` et `agentic-scheduler.py` fournissent les contrôles V2 quand
elles sont disponibles. L'orchestrateur vérifie leur présence avant usage.
Les scripts ne sont ni sandbox ni autorisation de merge ; préparer/attribuer
ne lance aucun agent. Le contrat runtime distingue lancement, fin d'exécution et
acceptation vérifiée. Un timeout ou BLOCKED ne signifie pas arrêt confirmé.

Execute reste l'activité d'implémentation. **Verify obligatoire** ensuite : tests
réellement exécutés, build/API/navigateur/captures/logs/performance selon le risque.
Une review indépendante confronte diff, AC et preuves. LIGHT/STANDARD peuvent
confier Review et examen final à un reviewer distinct avec profil Lead Tech ;
LARGE ou risque critique conserve une seconde lecture distincte du premier reviewer.
Goal mesurable pour tâche longue/complexe, jusqu'à SATISFIED ou blocker réel.

## SHIP

Commit candidat par garde staged, PR_SCOPE PASS sur base/tête/cible actuelles,
Review et examen final Lead Tech frais, CI PASS, validation humaine si requise,
autorisation de merge applicable, fusion puis cleanup sûr. Nouveau commit,
changement de contenu/base/plan : revalider les preuves concernées.
Une mission limitée à une PR s'arrête à READY_FOR_HUMAN ; DONE exige merge et cleanup.

## Reprise V1 et sécurité

Conserver les données, décisions et artefacts V1. PRD/Stories/Story Review/
Architecture/Design System/Research/Design/Plan sont des templates de reprise ou
legacy facultatifs pour une nouvelle mission V2 ; leurs contenus peuvent alimenter
les six rubriques. Ne pas exiger leurs PASS distincts ni les supprimer pour migrer.
Leur présence ne constitue aucun PASS. Les anciennes preuves restent historiques.

Appliquer [SAFETY](SAFETY.md), [DEVELOPMENT](DEVELOPMENT.md),
[CONTEXT](CONTEXT.md) et [COMMITS](../../COMMITS.md) selon leur déclencheur.
Auth, autorisation, tenant, données sensibles, secrets, actions externes,
validation humaine, tests, observabilité et rollback sont traités selon le risque.
Jamais d'auto-approval de l'implementer, test non exécuté annoncé PASS, merge avec
Critical/Major ouvert, changement silencieux de stack ou coût non observé inventé.

## Contrat des décisions d’architecture

TRD réutilise les décisions d’ARCHITECTURE ; `templates/ARCHITECTURE.md` reste
un support facultatif de reprise. Un choix utilisateur fait autorité :
l’enregistrer sans redemander ses motivations ou son approbation. Sans choix,
recommander une solution avec une raison courte. Comparer seulement un arbitrage
encore ouvert ; pas d’ADR par outil ni de dossier de preuves avant développement.
Un outil décidé ne déclenche aucun test de qualification en PREPARE/TRD/ADR.
Exception uniquement pour un cas particulier indispensable : contradiction
concrète ou risque critique sans mitigation, test minimal et critère d’arrêt
documentés. La préférence de l’agent ou une compatibilité non encore testée
ne suffit pas à imposer ce test. Une fois les choix utiles consignés et les
principes cohérents, terminer la préparation de ces décisions et avancer.
Sans changement structurant sur l’existant, le socle observé suffit.

Un ADR court trace les arbitrages durables : frontières majeures, isolation des
données, contrats partagés, engagements difficilement réversibles ou remplacement
d’une décision approuvée. Regrouper les choix liés ; aucun gate supplémentaire.

Les validations de faisabilité sont réalisées en BUILD/Verify de la capacité
concernée. Coûts d’exploitation et optimisations peuvent être suivis par le
produit après implémentation. Reporter chaque validation dans IMPLEMENTATION_PLAN
puis Verify.
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
