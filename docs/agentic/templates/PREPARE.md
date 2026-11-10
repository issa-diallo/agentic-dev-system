# PREPARE — <mission / ticket>

Mode : LIGHT / STANDARD / LARGE. Entrée : PRODUCT / EXISTING.
Sources réutilisées : documents, décisions/ADR, code et preuves avec chemins.
Périmètre, responsable et autorisations : TODO.

Les six rubriques tiennent dans ce fichier ou référencent des artefacts existants.
Aucun formulaire ni six gros fichiers imposés. Justifier N/A selon le périmètre.
Ce fichier rempli et tous les artefacts de préparation restent locaux, exclus de
Git, même approuvés ou collectifs. Stockage :
`.agentic-local/docs/agentic/work/<ticket>/`, avec exclusion Git effective,
y compris en installation partagée. Les templates distribués ne sont pas les
livrables remplis d'une mission. Appliquer `docs/agentic/PULL_REQUESTS.md` du socle.

Démarrage rapide : `python3 scripts/agentic-prepare.py init <ticket> --file <chemin>...`
génère ce squelette : rubriques front/back/données non concernées en N/A, commandes de
vérification détectées par profil (front, back, données, contrat). `check <fichier>`
contrôle la structure. Ticket trivial (≤2 fichiers, ≤30 lignes, un profil, ni contrat ni
données) : Repères, AC -> vérification et Gate suffisent. Full-stack : contrat/données
d'abord, puis back, puis front (`units`).

**Repères** : fichiers, décisions et tests déjà connus (chemin : rôle) ; lire avant de chercher.

## PRD
Problème, utilisateurs, objectif, priorités, exigences fonctionnelles et contraintes.
Scope/non-scope et critères d'acceptation mesurables.
Ticket et décisions utilisateur réutilisés ; inconnues réellement bloquantes.

| AC | Vérification (commande ou preuve) |
|---|---|

Règles métier -> tests (tests unitaires d'abord, écrits avant le code) :

| RM | Règle métier | Test(s) unitaire(s) |
|---|---|---|

Exception motivée : documentation, configuration, refactor couvert, spike.

Questions ouvertes : tableau Question / Bloquante / Statut / Réponse ; une question
bloquante non résolue bloque PREPARE.

## TRD
Stack observée ou choix retenus : frameworks, services, API, infrastructure,
sécurité, déploiement et contraintes techniques ; responsabilités, contrats et dépendances.
Si double analyse optionnelle HIGH/EXTRA_HIGH : justifier le surcoût quota,
préparer les IDs AC/RM et les sources explicites du contrat `analysis` selon
`docs/agentic/DOUBLE_ANALYSIS.md` du socle. Deux avis
indépendants puis synthèse/arbitrage sourcé requis avant BUILD ; désaccord critique
non résolu ou fournisseur manquant : BLOCKED. Aucun double lancement LOW/MEDIUM.
Décisions durables : ADR ciblé ; aucune qualification systématique des outils.
Validations différées : hypothèse, responsable, échéance, preuve attendue, action si échec.

## APP_FLOW
Parcours, navigation, actions utilisateur, transitions et états des écrans
(chargement, vide, succès, erreur), effets externes ; N/A motivé si absent.

## UX_UI_BRIEF
Identité visuelle, design system et composants existants, typographie et couleurs.
Responsive, états, interactions et accessibilité ; N/A motivé si sans UI.

## BACKEND_SCHEMA
Modèles, tables, relations et contraintes de données ; contrats, stockage,
migrations et intégrité ; N/A motivé si absent.
Auth, autorisation, tenant, données sensibles, secrets, actions externes,
validation humaine : protections pertinentes ou non-applicabilité justifiée.

## IMPLEMENTATION_PLAN
Incréments, fichiers exacts, dépendances/contrats, AC et tests par capacité.
PR_SPLIT : manifeste/hash, verdict et vagues ; avant tout BUILD non trivial.
Branche/worktree, owner unique, ressources, environnement reproductible si pertinent.
Skills disponibles sélectionnés à charger ; modèle/effort recommandé et capacité réelle.
Verify : commandes et preuves adaptées ; reviewer indépendant, CI et PR_SCOPE.
Observabilité et rollback selon risque ; goal mesurable si tâche longue/complexe.

## Gate PREPARE
- [ ] Six rubriques pertinentes complétées ou sources réutilisées référencées ; N/A motivés
- [ ] AC, scope, dépendances, fichiers et tests définis ; architecture/ADR compatibles
- [ ] Aucune décision différée requise ouverte, risques critiques traités, aucun blocker
- [ ] PR_SPLIT PASS avant BUILD non trivial ; isolation et ownership prêts
- [ ] Capacités runtime connues, délégation et fallback honnêtes, autorisations explicites

Verdict : DRAFT / PASS / BLOCKED. Preuves : TODO. Blockers : TODO.
PASS autorise BUILD dans ce périmètre ; présence du template ne vaut jamais PASS.
