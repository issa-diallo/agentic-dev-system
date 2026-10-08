# ADR-001 — Navigation conditionnelle et héritage sans runtime

## Status
ACCEPTED — 2026-10-08, dans le périmètre explicitement autorisé du ticket #6.

## Context
AGENTS fait 8 764 octets et prescrit des lectures exhaustives. L'installateur
copie déjà la méthode ; trois rôles et CONTEXT existent. La priorité est de
préserver les gates tout en réduisant les lectures répétées.

## Decision drivers
Portabilité, sécurité, personnalisation, absence de dépendances superflues,
vérifiabilité et maîtrise du coût de maintenance.

## Options considered
1. Index existant + règles conditionnelles : faible complexité, revue sémantique
   nécessaire pour vérifier qu'aucune obligation n'est perdue.
2. Index par domaine et agents propriétaires : plus de duplication et dépendance
   au harness ; rejeté pour ce petit corpus.
3. Compression/proxy obligatoire : données et cache à qualifier, rejeté.

## Decision / Why
Option 1. AGENTS garde les invariants. README de la méthode indique quand lire
les sources ; MODELS exprime des niveaux sans noms figés. Contrats de délégation
et compaction étendent les fichiers existants. Outils tiers évalués mais absents
par défaut. L'installateur distribue la méthode, jamais les preuves ni le statut
courant de son dépôt source.

## Consequences
Moins d'instructions universelles ; fichiers détaillés toujours obligatoires
lorsque leur déclencheur s'applique. Pas de garantie de coût/quota. Un contrôle
statique ne prouve pas qu'un modèle obéira ; revue et diagnostic runtime restent
nécessaires. Aucun changement d'auth, tenant ou accès à des secrets.

## Migration / rollback
Aucun changement de CLI ni FORCE. Nouvelle installation hérite automatiquement ;
installation existante : comparaison et sauvegarde manuelles. Revert des commits
pour le socle, restauration sélective après comparaison pour les projets générés.

## Related
[Architecture](../product/ARCHITECTURE.md), [ticket #6](https://github.com/issa-diallo/agentic-dev-system/issues/6).
