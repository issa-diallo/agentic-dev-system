# Pull Requests — petites modifications vérifiables

## Une raison métier principale de changer

Une story exprime un besoin complet et peut produire plusieurs PR. Chaque PR
livre un changement autonome, cohérent et testable, avec une raison métier
principale de changer. Authentification, sessions, profil, fichiers privés, NER
et facturation sont distincts lorsqu'ils peuvent évoluer et être validés séparément.
Leur présence dans la même story ne justifie jamais une PR unique.
Garder ensemble code, tests, migrations, contrats et protections indispensables
au même comportement. Ne pas découper par couche ou nombre arbitraire de fichiers.

## Aucun artefact de préparation dans le diff

Une PR applicative contient uniquement le code et les tests, migrations, contrats
et configurations indispensables au comportement livré : ces derniers sont des
dépendances de production ou des tests associés, pas un périmètre de support libre.
Réflexions, recherches,
PRD, TRD, parcours préparatoires, briefs, schémas de conception, plans, manifestes
PR_SPLIT, statuts, checkpoints, handoffs et rapports Execute/Verify/Review/Lead Tech
restent locaux, exclus de Git. Cela vaut aussi pour les artefacts approuvés ou
collectifs : les appeler « documentation métier » ou changer leur chemin ne
les rend pas livrables. Distinguer un schéma de conception d'une migration ou
d'un contrat exécuté par l'application, qui reste avec son code.

Scripts de réflexion, probes, benchmarks ponctuels, lanceurs de tests ajoutés pour
la mission, générateurs de preuves et outils de préparation restent aussi locaux.
Réutiliser les commandes de test du projet ; conserver avec le code les vrais
tests de régression et leurs fixtures indispensables. Ne pas ajouter des scripts
de travail à la PR sous prétexte qu'ils ont aidé à vérifier la fonctionnalité.
Un fichier Markdown n'est livré que si le produit l'utilise réellement et que
son lien avec le comportement demandé est prouvé ; son extension ou son titre
ne constitue ni une autorisation ni un motif de refus automatique.

Stocker ces travaux sous `.agentic-local/docs/agentic/work/<ticket>/`, avec
exclusion Git effective, en installation locale comme partagée. Donner les preuves
au reviewer hors du diff ; résumer les résultats dans la description de PR sans
y recopier les dossiers de préparation. Aucun rapport ne doit être committé pour
attester le commit qu'il examine. Une exception de taille ne lève pas cette règle.

PR_SPLIT exclut les ajouts/modifications de ces artefacts ; un retrait hérité
autorisé reste déclarable. Le refus automatique intervient à PR_SCOPE sur le diff
réel. PR_SCOPE exige une attestation indépendante pour chaque
chemin réellement changé : rôle `production` ou `test`, PASS et preuve concrète de
son utilité pour le comportement livré. Aucun rôle « tooling » ou « préparation »
n'est accepté. Fichier omis, ajouté à la revue hors diff ou attesté deux fois :
BLOCKED. Une affirmation globale de conformité ou une exception de taille ne
suffit pas. Les chemins locaux connus sont refusés même déclarés « production » ;
leur suppression pure reste possible pour une migration autorisée.
La garde staged reconnaît des chemins, pas la nature du contenu : l'inspection
indépendante du diff reste obligatoire. Ne pas supprimer les fichiers
locaux ni retirer de l'index des fichiers hérités sans l'accord prévu par INSTALL.

Une documentation utilisée par le produit (aide affichée, référence API consommée)
ou une évolution explicitement demandée d'un produit documentaire comme cette
méthode peut être un livrable de production. Sa nécessité est attestée fichier par
fichier selon le même contrôle ; aucune dérogation pour les notes de mission.

## Gate PR_SPLIT — dans PREPARE, avant BUILD non trivial

L'orchestrateur applique ce gate sans instructions supplémentaires :

1. Identifier toutes les capacités et leurs critères à partir de la story et du
   code réel ; distinguer support indispensable et comportement autonome.
2. Affecter chaque capacité à une PR autonome, même sous les cibles de taille.
   Couvrir chaque capacité exactement une fois.
3. Définir intention, fichiers exacts, AC, tests, contrats et compatibilité par PR.
   Les six rubriques et décisions communes peuvent être héritées ; chaque unité
   conserve son delta IMPLEMENTATION_PLAN et son DoR sans Research/Design/Plan
   supplémentaires par tâche.
4. Construire le DAG technique et contractuel : ordre de fusion, vagues sans
   collisions de fichiers, stack éventuelle, branche/worktree/implementer par PR.
5. Déléguer les unités indépendantes dans des worktrees distincts, un seul écrivain
   par worktree. Sans outils de sous-agents, exécuter séquentiellement et conserver
   une session de revue indépendante. Une tâche simple reste une entrée unique.
6. Exécuter `split` selon [PR_SPLIT](templates/PR_SPLIT.md), consigner son JSON et
   le verdict métier explicite de l'orchestrateur.

PASS exige couverture complète, périmètres autonomes, DAG acyclique et AC/tests/
fichiers/contrats définis. Des capacités séparables regroupées rendent BUILD
BLOCKED, même sous les seuils. Tout changement de scope exige revalidation.
Une indivisibilité technique exige contrainte concrète, preuve, risque du découpage
et reviewer indépendant. « Story complète », même dossier ou commodité de l'auteur
ne suffisent pas. Exemple recevable : migration et lecteur doivent basculer ensemble,
preuve d'incompatibilité des versions mixtes à l'appui.

## Taille et dépendances

- Cibles indicatives : 1 à 3 fichiers et au plus 100 lignes ajoutées + supprimées.
- Un seul commit logique final, squash possible des commits de travail.
- Une branche et une PR par unité liée au ticket ; identifiant `<story>-PR<n>`.
- Tout dépassement réel exige `size_exception` : contrainte, preuve et risque du
  découpage, confirmés par revue. Un binaire exige aussi cette justification ;
  son poids n'est pas représenté en lignes. Ne retirer ni tests ni sécurité.

Une collision de fichiers sérialise les vagues ; une dépendance fonctionnelle
reste déclarée même sans fichier commun. Contrats stabilisés/versionnés avant
délégation ; chaque étape reste testable et évite de casser la production.
Une stacked PR cible temporairement le parent : Verify/Review examinent
`parent..enfant`, pas tout l'empilement. Ship attend fusion des parents, rebase
sur la cible finale si nécessaire et preuves actualisées. `merged_commit` est le
SHA effectivement fusionné, y compris après squash, pas nécessairement l'ancienne
tête du parent. Une dépendance structurante échouée bloque les unités dépendantes.

## Gate PR_SCOPE — avant Ship pour chaque PR

`ship` compare Git réel base/tête/cible : chemins exacts (source et destination
des renames), taille, binaires, dépendances fusionnées et attestation indépendante
liée aux SHA et au hash du plan. Résultat JSON PASS/BLOCKED avec raison vérifiable.
L'orchestrateur actualise d'abord les refs distantes ; un checkout obsolète ne
prouve pas l'état serveur. Le script ne modifie ni Git ni les PR existantes.

Le reviewer examine explicitement ce que Git ne peut décider : capacité unique,
absence de fonctionnalité/refactoring indépendant, AC/tests, exceptions d'atomicité
et taille, compatibilité des contrats et identité des parents effectivement fusionnés
(lien de PR et SHA de fusion). Chaque axe reçoit PASS/BLOCKED avec preuve concrète.
Même un petit diff mêlant deux fonctionnalités reste BLOCKED.
L'orchestrateur vérifie la provenance du reviewer/session ; un nom dans JSON ne
prouve pas l'identité. Le script valide les déclarations et leur fraîcheur, pas
la classification métier ni l'authentification du reviewer.

PR_SCOPE BLOCKED empêche READY_FOR_HUMAN. PASS ne remplace pas Execute, Verify,
Review, Goal, CI, Lead Tech, [DEVELOPMENT](DEVELOPMENT.md),
[COMMITS](../../COMMITS.md) ou l'autorisation de fusion. Après changement de tête,
base ou manifeste, revalider. Une branche de release ne remplace pas les reviews
individuelles par une revue massive.
