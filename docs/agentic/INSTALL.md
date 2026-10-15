# Installation

La méthode est conçue pour être installée dans n'importe quel projet.

## Depuis un clone local du dépôt de la méthode

```bash
./install-agentic.sh /chemin/vers/mon-projet
```

Depuis le dossier du projet cible :

```bash
/path/to/agentic-method/install-agentic.sh .
```

L’installation est **LOCAL par défaut**, même avec `--existing`. Elle exige la
racine d’un dépôt Git. Pour un dossier neuf, faire `git init` explicitement avant
installation. `--local` est conservé ; `--local --shared` est refusé, quel que soit
l’ordre. Aucun réglage global Codex ou Git n’est nécessaire.

```text
.agentic-local/AGENTS.md
.agentic-local/COMMITS.md
.agentic-local/docs/agentic/       # méthode et tous les templates
.agentic-local/docs/agentic/work/  # documents de travail personnels
.agentic-local/scripts/           # checker, garde staged, wrapper de commit
```

Seul `info/exclude` reçoit `/.agentic-local/`. Son chemin est résolu par Git,
aussi en worktree ; son contenu précédent est conservé. Aucun fichier d’équipe,
`.gitignore`, hook ou template GitHub n’est modifié. Les règles qui réouvrent
le dossier local sont refusées, même si ses fichiers actuels restent ignorés :
l’installation retire alors uniquement le dossier vide qu’elle vient de créer
et restaure `info/exclude`. Un chemin local déjà suivi provoque un refus ; une
exclusion ne peut pas protéger les fichiers déjà dans l’index.

## Activation et documents produit

Suivre le prompt et la résolution des chemins de [LOCAL](LOCAL.md). Codex peut
lire la méthode, les rôles et tous les templates dans `.agentic-local/` ; aucune
activation automatique n’est promise. Les règles d’équipe restent prioritaires.
Pour un nouveau produit, créer les documents de cadrage depuis les templates
sous `.agentic-local/docs/agentic/work/<ticket>/`, avec exclusion Git effective.
Ces documents restent locaux après validation, en mode local comme partagé.
Ne pas publier les plans ou rapports sous un chemin métier. Seule une documentation
livrée explicitement à l'utilisateur a son propre objectif de PR, selon
[PULL_REQUESTS](PULL_REQUESTS.md).
Les gates PREPARE, PR_SPLIT, Verify et Review restent obligatoires ; aucun document vide ne prouve PASS.

## Installation partageable : demande explicite

```bash
./install-agentic.sh --shared /chemin/vers/nouveau-projet
./install-agentic.sh --shared --existing /chemin/vers/projet-existant
```

`--shared` conserve l’ancienne installation PRODUCT aux chemins standards,
avec PREPARE agrégé, les cinq templates legacy facultatifs et `docs/adr/`. `--shared --existing` conserve le
socle EXISTING sans documents produit. Ces ressources peuvent être versionnées
après décision d’équipe ; les notes de story et statuts personnels restent locaux
selon [COMMITS](../../COMMITS.md). S’il existe déjà AGENTS.md, COMMITS.md ou
docs/agentic, l’installation refuse avant copie. Préférer LOCAL pour préserver
l’existant. Les configurations optionnelles existantes ne sont pas écrasées.

## Protection et mise à jour

Les collisions sont contrôlées avant la création des dossiers. Une installation
fraîche fonctionne sans FORCE. Les fichiers optionnels existants sont conservés.
Les artefacts `docs/agentic/work/` du dépôt source ne sont jamais distribués.

`FORCE=1` est désormais refusé : comparer et sauvegarder les fichiers avant une
mise à jour manuelle. Une seconde installation locale refuse également d’écraser
les notes personnelles. Pour mettre à jour, sauvegarder hors des chemins
versionnables (dans `.agentic-local/` ou un dossier externe choisi), comparer le
socle avec la nouvelle version et reporter sélectivement les changements. Garder
STATUS, décisions, règles personnalisées et `work/` ; ne jamais les remplacer
par des templates neutres. Refaire le checker et la garde staged après mise à jour.

## Prompt de démarrage

Pour l’entrée EXISTING (ticket cadré sur projet existant), utiliser le prompt de
[EXISTING_PROJECT.md](EXISTING_PROJECT.md) et le contrôle `bash scripts/agentic-check.sh --existing`.
Les templates produit copiés ne constituent pas des gates PASS.

Pour l’entrée PRODUCT, une fois installé :

> Lis les règles équipe, puis AGENTS.md et l’index installé. Réutilise les décisions disponibles ; prépare les six rubriques utiles. Exige PR_SPLIT PASS avant BUILD non trivial, puis Verify, review indépendante et SHIP selon autorisation. Aucun template ne prouve PASS.

## Commits

Chaque projet installé reçoit `COMMITS.md`.

Les agents doivent :

- choisir le Gitmoji correspondant à l'intention réelle ;
- utiliser un titre impératif court ;
- expliquer le pourquoi dans le corps ;
- ajouter `Fixes #<issue_number>`.

La référence Gitmoji est https://gitmoji.dev/.

## Mise à jour

Pour mettre à jour la méthode dans un projet existant, comparer d'abord les changements entre la version installée et la nouvelle version. Ne pas écraser automatiquement des règles projet personnalisées.

## Héritage et personnalisation

### Reprendre une Architecture bloquée par des preuves

Après comparaison et sauvegarde, reporter les nouvelles règles de README,
AGENTS, METHOD, WORKFLOW, SCALING, EXISTING_PROJECT, BOOTSTRAP, OPTIONAL_TOOLS,
index, rôles et templates Architecture/ADR/Research/Plan/Verify. En LOCAL, les
chemins sont sous `.agentic-local/`. Conserver les décisions et artefacts du
projet cible ; ne pas remplacer son Architecture par un template vide.

Prompt de reprise :

> Applique PREPARE → BUILD → SHIP et le contrat court Architecture de METHOD.
> Réutilise mon architecture, mes outils et décisions validés. Complète seulement
> les rubriques PREPARE nécessaires au delta, sans tests de qualification,
> benchmarks ou preuves préalables. Référence les artefacts existants ; les
> templates V1 restent facultatifs. Reporte les validations pertinentes dans
> IMPLEMENTATION_PLAN puis Verify ou suivi produit, avec responsable et échéance.
> Si aucun risque critique ou décision indispensable ne bloque, valide PREPARE,
> exige PR_SPLIT PASS avant BUILD non trivial et poursuis les capacités prévues.
> Ne redemande pas les choix déjà autorisés.

Les profils LOCAL, PRODUCT partagé et EXISTING partagé copient le même socle : index, politique modèles, contexte,
rôles et templates. STATUS est initialisé depuis le template neutre ; aucun
statut ou artefact de travail du dépôt source n’est hérité. Les documents produit
PRODUCT viennent des templates, jamais du produit source. Le préflight refuse
une ressource obligatoire manquante avant toute écriture.

Après installation, choisir LIGHT/STANDARD/LARGE dans STATUS. Personnaliser
les documents projet et, pour plusieurs applications, des AGENTS.md de
sous-dossiers (API, web, mobile, etc.) précisant commandes, frontières et données.
Conserver les invariants racine, documenter les contrats partagés et les ADR.
L’installation ne remplace pas les personnalisations existantes : comparer
manuellement ou utiliser LOCAL, qui demande une activation explicite.
Aucun outil optionnel ni configuration Codex globale ne sont activés.
Les tests de génération vérifient la structure, pas l’exécution du modèle.

## Diagnostic et rollback

Instruction ignorée : vérifier le répertoire courant, les AGENTS.md applicables,
un éventuel AGENTS.override.md et les limites de la chaîne chargée dans le client.
En LOCAL, vérifier que le prompt active explicitement LOCAL.md après les règles
équipe. Lancer le checker depuis la bonne racine ; il prouve seulement la présence.
Si nécessaire, demander une lecture seule des règles effectives dans une session
dédiée ; cette validation runtime n’est pas exécutée par l’installateur.

Avant mise à jour, sauvegarder et comparer les fichiers concernés. Restaurer
sélectivement le socle depuis la version précédente sans écraser personnalisations,
artefacts de story ou règles d’équipe. Pour annuler une installation LOCAL,
désactiver sa référence dans les prompts, puis retirer seulement ses fichiers et
sa ligne d’exclusion après vérification ; ne pas nettoyer globalement Git.

## Migrer une installation ancienne

La migration est volontaire et manuelle. Elle ne réécrit aucun historique et
ne supprime aucun fichier physique. Ne l’exécuter que dans le dépôt demandé,
après revue et accord explicite sur les chemins à retirer de l’index. Une
ancienne installation partagée peut être intentionnelle : ne pas déduire que
AGENTS.md, COMMITS.md, docs/product, ADR, hooks ou .github appartiennent à une
personne. Les documents métier et règles d’équipe restent suivis.

### 1. Diagnostic sans modification

Depuis la racine du projet :

```bash
git status --short
git diff --cached --name-status
git ls-files -- .agentic-local docs/agentic AGENTS.md COMMITS.md docs/product docs/adr scripts hooks .github
git rev-parse --path-format=absolute --git-path index
git rev-parse --path-format=absolute --git-path info/exclude
```

Inspecter l’origine et le rôle de chaque candidat, ses changements staged et
non staged, ses statuts, décisions et travaux en cours. Les noms sont affichés
par Git avec échappement ; pour une liste machine, utiliser `git ls-files -z`.
Ne pas imprimer les contenus sensibles. Si l’index contient déjà des changements,
les terminer séparément ou sauvegarder leur patch et convenir de leur traitement ;
**arrêter la migration tant que l’index n’est pas vide**. Ne jamais les effacer
avec un reset. Les modifications non staged sont conservées.

Si `.agentic-local/` existe ou était déjà suivi, l’installateur refuse : ne pas
forcer ni supprimer le dossier. Sauvegarder ses contenus et l’index dans un
emplacement externe choisi, comparer le socle, restaurer sélectivement les
scripts/règles nouveaux, puis compléter `info/exclude` localement et vérifier
les exclusions. Sélectionner ensuite ses seuls fichiers internes suivis pour
la même procédure index ci-dessous. Conserver les notes et STATUS existants.

### 2. Installer localement et sauvegarder

Pour une ancienne installation aux chemins standards sans dossier local,
installer normalement : cette étape ne touche pas l’index ni les fichiers
anciens. Ensuite, définir une sélection **exacte et revue** dans un tableau Bash.
Exemple à adapter, sans sélectionner les documents métier :

```bash
personal=(docs/agentic/work/17/research.md docs/agentic/STATUS.md)
backup=".agentic-local/migration-backup-$(date +%Y%m%d-%H%M%S)"
mkdir "$backup"
index_path="$(git rev-parse --path-format=absolute --git-path index)"
exclude_path="$(git rev-parse --path-format=absolute --git-path info/exclude)"
cp "$index_path" "$backup/index"
cp "$exclude_path" "$backup/exclude"
git status --porcelain=v1 -z > "$backup/status.nul"
git diff --binary > "$backup/working.patch"
tar -cpf "$backup/files.tar" -- "${personal[@]}"
printf '%s\0' "${personal[@]}" > "$backup/selection.nul"
```

Vérifier la sauvegarde, arrêter si un fichier manque ou une commande échoue.
Sauvegarder aussi les fichiers locaux personnalisés si leur mise à jour est
prévue. Copier sélectivement les anciens `work/` et STATUS sous `.agentic-local/`
en conservant intégralement les contenus ; ne pas écraser un travail local
existant ni remplacer une décision par un template. Les originaux restent présents.

### 3. Exclure les originaux et faire valider la sélection

Ajouter les chemins personnels exacts à `.agentic-local/personal-paths.nul` :
`printf '%s\0' "${personal[@]}" >> .agentic-local/personal-paths.nul`.
Cette liste NUL, locale et revue, interdit aussi les anciens chemins ambigus
(ex. un COMMITS.md personnel), sans interdire leurs équivalents d’équipe ailleurs.
Elle ne doit pas contenir de dossiers ou de motifs glob.

Ajouter à `info/exclude` les motifs ancrés correspondant **uniquement** aux
originaux conservés. Pour les noms simples de l’exemple :

```bash
printf '\n/docs/agentic/work/17/research.md\n/docs/agentic/STATUS.md\n' >> "$exclude_path"
git check-ignore --no-index -v -- "${personal[@]}"
```

Les chemins avec `*`, `?`, `[`, `\`, `#`, `!`, espaces finaux ou retours à la ligne
exigent des motifs Git échappés et une vérification individuelle ; ne pas écrire
un chemin arbitraire comme motif. Pour un nom non représentable sûrement dans
`info/exclude`, conserver uniquement la copie locale et décider explicitement
du devenir de l’original avant de poursuivre. Ne pas éditer `.gitignore`.
Présenter la liste, la sauvegarde, les copies et les exclusions à l’utilisateur.
**Attendre son accord explicite avant toute modification de l’index.**

### 4. Retirer uniquement de l’index après accord

```bash
git --literal-pathspecs rm --cached -- "${personal[@]}"
git diff --cached --name-status
bash .agentic-local/scripts/agentic-staged-check.sh
git add --dry-run -A
git diff --cached --name-status
```

Ne jamais ajouter `-f` si Git refuse : comparer l’index, HEAD et les contenus,
puis faire résoudre le conflit. Vérifier que tous les originaux et copies sont
physiquement présents et identiques, que seuls les retraits autorisés sont staged
et que le diagnostic `add --dry-run -A` ne proposerait aucun fichier personnel.
Ne pas exécuter ici `add -A` : cela ajouterait aussi les changements métier
non staged préexistants, qui ne font pas partie de la sélection approuvée. La garde autorise ces suppressions pures.
Faire le commit de migration via le wrapper avec le message validé et le ticket.
Les branches/worktrees contenant encore l’ancienne installation nécessitent
leur propre diagnostic et sélection ; partager `info/exclude` ne retire aucun
fichier de leur index. Ne pas agir automatiquement sur les autres worktrees.

### 5. Rollback ciblé

Avant commit, si l’index était vide au départ, restaurer seulement les entrées
sélectionnées : `git --literal-pathspecs restore --source=HEAD --staged -- "${personal[@]}"`.
Cela conserve les modifications physiques. Comparer ensuite `info/exclude` à la
sauvegarde et retirer uniquement les motifs ajoutés par cette migration ; ne pas
écraser des exclusions communes modifiées depuis par un autre worktree.
Conserver le dossier local, les copies, la liste personnelle et les sauvegardes
jusqu’à décision explicite. La liste continuera à bloquer de nouveaux commits
personnels sur ces chemins ; restaurer la liste précédente seulement si la
classification est elle-même annulée après revue.

Après commit, le rollback fonctionnel restaure sélectivement les contenus et
la méthode **localement** depuis les sauvegardes ; il n’a pas besoin de réintroduire
les fichiers personnels dans Git. Les originaux physiques n’ont pas été supprimés.
Conserver les exclusions pour empêcher une pollution lors du prochain `add -A`.
Un choix ultérieur de partager certains documents exige une décision explicite
et une revue séparée de leur rôle. Restaurer leur suivi depuis un SHA précédent
est alors une opération distincte et autorisée ; la garde continue à refuser les
chemins personnels. Aucun contournement ou réintroduction automatique n’est prévu.
L’index sauvegardé sert de preuve et de secours : **ne pas le recopier sur un
index ayant reçu de nouveaux travaux**, ni utiliser reset --hard, clean ou
force push. Restaurer les contenus perdus sélectivement depuis l’archive validée.

## Adopter PR_SPLIT dans les projets déjà installés

Sauvegarder et comparer ; ne pas relancer l'installateur sur les personnalisations.
Reporter sélectivement README/AGENTS, index, METHOD/WORKFLOW/SCALING,
EXISTING_PROJECT, PULL_REQUESTS/DEVELOPMENT, rôles ORCHESTRATOR/REVIEWER et templates
PREPARE/PR_SPLIT/SHIP. IMPLEMENTATION_PLAN porte le découpage ; les templates
STORY/STORIES/DESIGN/PLAN hérités restent des références facultatives, à conserver
sans imposer de nouveaux fichiers ou PASS. Ajouter `scripts/agentic-pr-check.py`,
actualiser `scripts/agentic-check.sh` et, si utilisé, le template GitHub de PR.
En LOCAL, tous ces chemins du socle sont sous `.agentic-local/` ; le contrôleur
s'exécute depuis la racine Git applicative avec `--repo .`. Python 3 et Git requis,
aucun package ajouté. Conserver STATUS, work/, décisions et règles d'équipe.

Activer les nouvelles règles pour les nouvelles stories : demander à Codex
de réutiliser les décisions validées dans PREPARE/IMPLEMENTATION_PLAN, appliquer
PR_SPLIT automatiquement avant BUILD non trivial, déléguer les vagues compatibles
et contrôler PR_SCOPE avant SHIP. LIGHT garde un découpage compact dans
IMPLEMENTATION_PLAN ou son support PREPARE agrégé, sans Plan supplémentaire.
Ne modifier, découper, rebaser ou réécrire aucune PR déjà existante automatiquement.
Un éventuel traitement d'une PR ouverte est une mission distincte explicitement
cadrée. Vérifier présence (`agentic-check.sh --existing`), puis un manifeste local
`split` et un contrôle `ship` avec attestation indépendante réelle ; le contrôle
de présence ne prouve aucun PASS de périmètre. Vérifier exclusions personnelles
avec la garde staged avant commit. Rollback : restaurer seulement les règles et
scripts sauvegardés, conserver les artefacts et PR sans modification.


## Distribution V2 et activation Codex

Le socle distribue les scripts Planner, Workspace, Skills, Models, Scheduler et
Quality, trois profils dans `codex/agents/` et six skills courts dans `skills/`.
Aucune configuration `.codex/`, `.agents/`, globale ou d’authentification n’est
créée ou remplacée. Les préflights couvrent ces ressources avant toute écriture.
En mode partagé, une collision avec un fichier V2 existant est refusée.
PRODUCT initialise `docs/product/PREPARE.md` et conserve les templates V1 ;
les installations existantes sont comparées/manuellement mises à jour, jamais
écrasées. Aucun document validé ni historique n’est supprimé.

Depuis la vraie racine du projet, activation opt-in pour une invocation :

```bash
bash .agentic-local/scripts/agentic-codex.sh run "Ajouter une API authentifiée"
# Mode partagé : bash scripts/agentic-codex.sh run "Mission"
```

Le launcher ajoute seulement `-c agents.agentic_<role>.config_file=<chemin>`.
Le mode `run <mission> [options Codex]` préfixe une unique chaîne prompt par
la lecture des règles équipe, LOCAL/index/PREPARE et le routage de la racine
canonique skills du socle, plus celles déjà connues/autorisées par l’hôte. La mission
reste une donnée argv, sans évaluation shell. Les autres invocations passent
leurs arguments tels quels : `app-server` reçoit les overrides de configuration
des profils uniquement, et demande
un prompt LOCAL explicite pour activer la méthode dans le contexte principal. Les sous-agents reçoivent
uniquement leur contrat, le socle utile et les skills sélectionnés.
Les arguments utilisateur, le compte, les permissions et les règles équipe sont
conservés. Aucun `danger-full-access`, modèle, effort ou feature n’est imposé.
Les profils portent `name`, `description`, `developer_instructions` ; aucun
réglage de permissions hôte n’est remplacé par le launcher. Explorer/reviewer sans écriture est une instruction
coopérative, pas une sandbox OS. Les fichiers TOML modernes sont décrits dans la
[documentation officielle Codex](https://developers.openai.com/codex/subagents).
Le mode `config_file` est une compatibilité CLI à vérifier sur la version utilisée.
Une validation parsing/initialize n’est pas une preuve de sous-agents lancés.

Limites observées sur Codex CLI **0.162.1** : le parsing des profils et
`app-server --strict-config`/initialize passent, mais le test réel de rôles n’a
lancé ni démontré l’application d’aucun profil. Dans ce runtime, l’outil exposé
`collaboration.spawn_agent` ne possède aucun sélecteur de rôle configuré ;
`task_name` nomme une mission, il ne sélectionne pas `agentic_explorer` ou
`agentic_reviewer`. Cette observation concerne l’hôte testé, pas une garantie
sur tous les runtimes Codex. Un essai sous sandbox read-only a aussi échoué avec
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` lors du routage
skills. Ce résultat ne prouve ni lancement natif ni application de skills.
Ne pas contourner cet échec en augmentant automatiquement les permissions.

Utiliser les outils de délégation réellement exposés par l’hôte avec contrats
explicites, périmètres, skills utiles et reçus vérifiables. Le rôle est alors un
contrat de mission, sans prétendre qu’un profil TOML a été injecté. Sans délégation
disponible, déclarer le repli mono-agent et conserver la review dans une session
indépendante. Aucun PASS de profil natif appliqué sans preuve runtime correspondante.


Les skills restent ON_DEMAND. L’orchestrateur fournit explicitement le chemin
canonique `skills/` du socle au routeur `agentic-skills.py`, puis charge uniquement
les instructions sélectionnées ; pas d’auto-discovery native promise hors des
racines supportées. Lire/charger un skill ne prouve pas son application. Les liens
relatifs de chaque skill résolvent le socle dans les deux modes. CORE reste AGENTS.

Pour arrêter l’activation, lancer Codex normalement : aucun lien ou config à
retirer. Les artefacts personnels restent sous `.agentic-local/`, protégés par la
garde staged même après `git add -f`. Le rollback de l’installation et la migration
des anciennes données suivent les procédures ci-dessus.
