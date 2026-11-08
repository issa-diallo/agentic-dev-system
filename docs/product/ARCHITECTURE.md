# Architecture — Méthode portable

ARCHITECTURE: PASS

## Socle observé
Markdown pour instructions, Bash/Git pour installation, Python unittest standard
pour régressions, GitHub Actions pour syntaxe et tests. Aucun runtime applicatif,
base de données, auth applicative, tenant ou UI à introduire. Les raisons
historiques de cette stack ne sont pas supposées.

## Décision et alternatives
Conserver ce socle et les modes PRODUCT, EXISTING, LOCAL. Ajouter une navigation
conditionnelle dans docs/agentic/README.md, une politique MODELS.md et une étude
OPTIONAL_TOOLS.md. Enrichir CONTEXT, rôles et templates existants. Ne pas créer
cinq nouveaux index ni un agent par spécialité. Le contrat Bash copie les fichiers
portables ; les preuves et statuts propres au dépôt source ne sont pas hérités.

Alternative rejetée : remplacement de configuration Codex globale,
proxy ou framework de routage automatique. Plus de dépendances et risque de
remplacer les choix du projet, sans gain démontré. Les modèles et niveaux sont
recommandés, leur disponibilité vérifiée dans l'interface réellement utilisée.

À la demande utilisateur du 2026-11-08, les profils canoniques sont copiés dans
les dossiers natifs du projet `.codex/agents/` et `.claude/agents/` pour découverte
au lancement normal. En LOCAL, seuls les six chemins sont exclus de Git ; aucune
configuration de compte, confiance, modèle ou permissions n’est remplacée.
Les anciens overrides de rôles sont retirés des lanceurs. Voir INSTALL pour le
contrat de préservation et les preuves de découverte, distinctes d’un lancement.

ADR : docs/adr/001-context-routing.md. Pas de remplacement de stack approuvée.
Cette décision applique la mission autorisée ; elle ne nécessite aucune
installation externe. Les nouveaux projets gardent leur propre phase Architecture.

## Contrats, sécurité et opérations

Le panneau compagnon facultatif lit les métadonnées du serveur Codex existant via
le proxy local et WebSocket sur socket Unix. Python stdlib, aucun nouveau service
ni dépendance externe. Il filtre le dépôt/worktrees et n’émet que des lectures de
liste de threads après initialisation ; pas de prompt, reprise, contrôle d’agent
ou validation de gate. Transport borné et neutralisation des caractères terminal.
Les indisponibilités restent explicites ; les états runtime ne deviennent pas des PASS.

Une seule copie canonique des règles détaillées ; obligations conservées dans
AGENTS et renvois conditionnels obligatoires. Aucun secret dans les artefacts.
Réseau seulement pour recherches et publication explicitement demandée.
Ne pas écraser les personnalisations ; local exige activation volontaire.
Les outils tiers restent des procédures opt-in, sans code d'intégration livré.
Tests stdlib, fixtures temporaires, liens Markdown locaux et contrats critiques.
CI source non imposée aux projets. Rollback par revert des commits ; comparer
les fichiers générés avant toute restauration, conserver les notes locales.

Verdict : PASS
