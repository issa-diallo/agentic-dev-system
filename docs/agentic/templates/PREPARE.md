# PREPARE — <mission / ticket>

Mode : LIGHT / STANDARD / LARGE. Entrée : PRODUCT / EXISTING.
Sources réutilisées : documents, décisions/ADR, code et preuves avec chemins.
Périmètre, responsable et autorisations : TODO.

Les six rubriques tiennent dans ce fichier ou référencent des artefacts existants.
Aucun formulaire ni six gros fichiers imposés. Justifier N/A selon le périmètre.
Les notes, preuves et checkpoints personnels restent locaux, exclus de Git.

## PRD
Problème, utilisateurs, objectif, priorités, exigences fonctionnelles et contraintes.
Scope/non-scope et critères d'acceptation mesurables.
Ticket et décisions utilisateur réutilisés ; inconnues réellement bloquantes.

## TRD
Stack observée ou choix retenus : frameworks, services, API, infrastructure,
sécurité, déploiement et contraintes techniques ; responsabilités, contrats et dépendances.
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
