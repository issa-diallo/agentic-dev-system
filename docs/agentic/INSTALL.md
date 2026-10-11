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
sous `.agentic-local/docs/product/` jusqu’à validation. Publier seulement les
documents métier validés que l’équipe veut versionner dans ses vrais chemins.
Les gates produit restent obligatoires ; aucun document vide ne prouve PASS.

## Installation partageable : demande explicite

```bash
./install-agentic.sh --shared /chemin/vers/nouveau-projet
./install-agentic.sh --shared --existing /chemin/vers/projet-existant
```

`--shared` conserve l’ancienne installation PRODUCT aux chemins standards,
avec cinq templates produit et `docs/adr/`. `--shared --existing` conserve le
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

> Lis AGENTS.md, COMMITS.md et docs/agentic/METHOD.md. Applique strictement PRD → Stories → Story Review → Architecture → Design System → Research → Design → Plan → PR_SPLIT → Worktree Setup si requis → Execute → Verify → Review → Goal si applicable → Ship. Identifie la première phase qui n'est pas PASS et commence uniquement par celle-ci. Pour chaque commit, utilise le Gitmoji approprié et respecte COMMITS.md.

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

> Applique le contrat court Architecture de METHOD. Conserve mes outils décidés.
> Termine le cadrage avec les informations disponibles, sans tests de qualification,
> benchmarks ou preuves préalables. Reporte les validations pertinentes en
> Execute/Verify ou suivi produit, avec responsable et échéance. Si aucun cas
> particulier indispensable ne bloque, indique Architecture PASS et poursuis
> Design System puis les stories. Ne redemande pas les choix déjà autorisés.

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
STORY/STORIES/DESIGN/PLAN/PR_SPLIT/SHIP. Ajouter `scripts/agentic-pr-check.py`,
actualiser `scripts/agentic-check.sh` et, si utilisé, le template GitHub de PR.
En LOCAL, tous ces chemins du socle sont sous `.agentic-local/` ; le contrôleur
s'exécute depuis la racine Git applicative avec `--repo .`. Python 3 et Git requis,
aucun package ajouté. Conserver STATUS, work/, décisions et règles d'équipe.

Activer les nouvelles règles pour les nouvelles stories : demander à Codex
d'appliquer PR_SPLIT automatiquement après Plan, déléguer les vagues compatibles
et contrôler PR_SCOPE avant Ship. LIGHT reste une entrée compacte dans Plan.
Ne modifier, découper, rebaser ou réécrire aucune PR déjà existante automatiquement.
Un éventuel traitement d'une PR ouverte est une mission distincte explicitement
cadrée. Vérifier présence (`agentic-check.sh --existing`), puis un manifeste local
`split` et un contrôle `ship` avec attestation indépendante réelle ; le contrôle
de présence ne prouve aucun PASS de périmètre. Vérifier exclusions personnelles
avec la garde staged avant commit. Rollback : restaurer seulement les règles et
scripts sauvegardés, conserver les artefacts et PR sans modification.
