# Design — DOC-existing-project

Design : PASS.

Critères : entrée explicite EXISTING, indépendante de LIGHT/STANDARD/LARGE ;
ticket cadré et architecture observée consignés dans Research ; absence des cinq
documents produit non bloquante ; aucun PASS produit fictif ; retour au pipeline
produit pour nouveau produit/gros périmètre ; décisions structurantes via ADR.
Les gates par story et la review indépendante restent obligatoires.
Le checker accepte --existing pour vérifier le socle sans exiger les documents
produit ; son défaut reste le parcours produit. Il ne valide pas les gates.

## Installation

Design PASS : --existing omet les documents produit ; --local implique --existing,
requiert une racine Git et installe exclusivement sous .agentic-local, ignoré via
info/exclude. Aucun AGENTS racine modifié. Refuser collisions, symlinks dangereux,
répertoire local déjà suivi, options invalides avant copie. FORCE est refusé
explicitement : remplacement manuel après comparaison. Ne pas distribuer les
artefacts de travail du dépôt source. Bash et Git existants suffisent.
