# COMMITS.md

## Objectif

Un bon message de commit doit expliquer pourquoi le changement a été fait,
pas seulement ce qui a changé.

Le diff montre déjà le code modifié. Le message de commit doit expliquer :

- le contexte ;
- l’intention ;
- le problème résolu ;
- les conséquences éventuelles.

Un historique Git propre aide pour :

- `git log` ;
- `git blame` ;
- `git revert` ;
- `git rebase` ;
- les reviews ;
- la maintenance long terme.

## Format obligatoire

Chaque commit doit commencer par **un Gitmoji adapté à l’intention réelle du changement**.

Format :

```text
<gitmoji> <Imperative title>

<Why this change was needed>
<What changed at a high level>
<Any important consequence>

Fixes #<issue_number>
```

La spécification Gitmoji autorise l’emoji Unicode ou le shortcode. Dans ce
projet, préférer **l’emoji Unicode** pour garder un `git log` compact.

## Choisir le bon Gitmoji

L’agent doit choisir le Gitmoji en fonction de l’intention principale du
commit, et non en fonction du type de fichier modifié.

Correspondances courantes :

| Gitmoji | Usage |
|---|---|
| 🎉 | Initialiser un projet |
| ✨ | Ajouter une nouvelle fonctionnalité |
| 🐛 | Corriger un bug |
| 🩹 | Faire une petite correction non critique |
| 🚑️ | Corriger un problème critique en urgence |
| ♻️ | Refactorer du code sans changer le comportement |
| 🎨 | Améliorer la structure ou le format du code |
| ⚡️ | Améliorer les performances |
| ✅ | Ajouter, modifier ou faire passer des tests |
| 🧪 | Ajouter un test qui échoue volontairement |
| 📝 | Ajouter ou modifier de la documentation |
| 💄 | Modifier l’interface ou les styles |
| ♿️ | Améliorer l’accessibilité |
| 📱 | Améliorer le responsive |
| 🔒️ | Corriger un problème de sécurité ou de confidentialité |
| 🛂 | Modifier les rôles, permissions ou autorisations |
| 🦺 | Ajouter ou modifier de la validation |
| 🏗️ | Faire un changement d’architecture |
| 🗃️ | Modifier la base de données ou le schéma |
| 👽️ | Adapter le code à un changement d’API externe |
| 🔧 | Ajouter ou modifier de la configuration |
| 🔨 | Ajouter ou modifier des scripts de développement |
| 👷 | Ajouter ou modifier la CI |
| 💚 | Corriger la CI |
| ⬆️ | Mettre à jour des dépendances |
| ⬇️ | Rétrograder des dépendances |
| 📌 | Épingler une version de dépendance |
| ➕ | Ajouter une dépendance |
| ➖ | Retirer une dépendance |
| 🔥 | Supprimer du code ou des fichiers |
| ⚰️ | Supprimer du code mort |
| 🚚 | Déplacer ou renommer des ressources |
| 💥 | Introduire un breaking change |
| 🚀 | Déployer |
| 🔖 | Créer une release ou un tag de version |
| ⏪️ | Revert un changement |
| 🔀 | Merger des branches |
| 🧑‍💻 | Améliorer l’expérience développeur |
| 🧱 | Modifier l’infrastructure |

Si aucun Gitmoji ne correspond clairement, consulter https://gitmoji.dev/
avant de créer le commit.

## Règles obligatoires

### 1. Un Gitmoji adapté dans chaque commit

Chaque commit doit commencer par exactement un Gitmoji représentant
l’intention principale.

Bon :

```text
🐛 Fix upload validation for empty file
```

```text
✨ Add artisan assignment workflow
```

Mauvais :

```text
✨ Fix upload validation for empty file
```

Le second exemple utilise un Gitmoji de nouvelle fonctionnalité pour une
correction de bug.

### 2. Séparer le titre du corps par une ligne vide

Un commit simple peut avoir seulement un titre uniquement si le projet
n’impose pas de ticket. Dans ce système, les changements liés à une story
doivent inclure le ticket dans le corps.

Exemple :

```text
✏️ Fix typo in user guide
```

Si le changement mérite une explication, utiliser un corps de message :

```text
♻️ Refactor packing list parser

Move Excel parsing responsibility from the frontend to the backend
to avoid duplicated logic and inconsistent results between layers.

Fixes #142
```

### 3. Limiter le titre à environ 50 caractères

Le Gitmoji compte dans la longueur du titre. Le titre doit rester court,
lisible et précis.

Bon exemple :

```text
🚚 Move Excel parsing to backend
```

Mauvais exemple :

```text
🚚 Move all Excel parsing logic from frontend utils to backend service and update upload page
```

Si le titre devient trop long, le commit contient probablement trop de
changements.

### 4. Commencer le texte du titre par une majuscule

Bon exemple :

```text
🐛 Fix upload page overflow on mobile
```

Mauvais exemple :

```text
🐛 fix upload page overflow on mobile
```

### 5. Ne pas mettre de point à la fin du titre

Bon exemple :

```text
✅ Add responsive layout checks
```

Mauvais exemple :

```text
✅ Add responsive layout checks.
```

### 6. Utiliser l’impératif dans le titre

Le titre doit sonner comme une instruction.

La règle simple :

```text
If applied, this commit will...
```

Exemples corrects :

```text
🐛 Fix mobile layout overflow
♻️ Refactor upload parser
✅ Add backend validation tests
🔥 Remove duplicate Excel logic
```

Exemples à éviter :

```text
🐛 Fixed mobile layout overflow
♻️ Refactored upload parser
✅ Adding backend validation tests
```

### 7. Couper le corps autour de 72 caractères

Le corps du message doit rester lisible dans le terminal.

Exemple :

```text
🚚 Move Excel parsing to backend

The frontend and backend both had parsing logic, which made the
result harder to maintain and increased the risk of inconsistent
packing list generation.

The frontend now only uploads the file and displays the backend
response.

Fixes #142
```

### 8. Expliquer le quoi et le pourquoi, pas le détail du comment

Le code montre déjà comment le changement a été fait.

Le message de commit doit expliquer :

- quel problème existait avant ;
- pourquoi ce changement est nécessaire ;
- ce que le changement améliore ;
- les effets secondaires éventuels.

### 9. Lier chaque commit à un ticket GitHub

Chaque commit doit référencer le ticket GitHub associé, afin de garder
une traçabilité claire entre le code et la tâche.

Format obligatoire à ajouter dans le corps du commit :

```text
Fixes #<issue_number>
```

Exemples :

```text
🐛 Fix upload validation for empty file

Prevent the API from accepting empty uploads to avoid invalid parsing
states and unclear client errors.

Fixes #142
```

```text
♻️ Refactor company access checks

Unify access validation rules used by services and controllers to
reduce duplicated conditions and inconsistent authorization behavior.

Fixes #187
```

## Convention pratique pour ce projet

Utiliser la structure :

```text
<gitmoji> Action + zone concernée + objectif
```

Exemples :

```text
🐛 Fix mobile overflow on landing page
🚚 Move Excel parsing to backend
✅ Add tests for packing list service
♻️ Refactor upload page into display-only flow
📝 Update Codex prompts for planning workflow
```

## Exemples valides

```text
🎉 Initialize strict Next.js project

The project needs a clean technical foundation before adding the
Telegram, Supabase and GitHub workflows.

This change sets up Next.js with strict TypeScript, Tailwind and the
initial folder structure required by the specifications.

Fixes #1
```

```text
🦺 Add Supabase environment validation

The application depends on several environment variables for
Supabase, Telegram, Anthropic and GitHub integrations.

This change validates required variables at startup to fail fast when
an environment is incomplete or misconfigured.

Fixes #18
```

```text
♻️ Centralize packing list parsing in backend

Parsing logic was duplicated between the frontend and backend,
making the upload flow harder to maintain and test.

The frontend now sends the file to the backend and displays the
normalized result returned by the API.

Fixes #42
```

## Exemples à éviter

```text
🐛 fixed stuff
```

```text
✨ changes
```

```text
♻️ Refactored the whole app and added Supabase and fixed lint
```

```text
✨ Added new feature.
```

## Règle finale

Avant de proposer ou créer un commit, l’agent doit vérifier que :

- le Gitmoji correspond à l’intention principale du changement ;
- le titre est à l’impératif ;
- le texte du titre commence par une majuscule ;
- le titre ne se termine pas par un point ;
- le titre reste court ;
- le corps explique pourquoi le changement existe ;
- le message ne décrit pas seulement le code modifié ;
- le corps contient `Fixes #<issue_number>` ;
- le commit reste atomique et cohérent.

Si une de ces règles n’est pas satisfaite, ne pas créer le commit.
