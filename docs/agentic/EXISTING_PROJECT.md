# Projet existant — réutiliser le socle

Installation personnelle : `install-agentic.sh` ou `--local`, puis
[LOCAL](LOCAL.md). Installation partageable : `--shared --existing`.
Choisir EXISTING dans le statut et LIGHT/STANDARD/LARGE selon le risque.

## PREPARE du ticket

Identifier ticket, problème/comportement attendu, périmètre et AC vérifiables.
Lire les décisions, ADR et artefacts disponibles ; inspecter uniquement code,
configuration, tests et composants concernés. Distinguer faits/hypothèses et
résoudre les contradictions touchant le ticket. Ne pas inventer les raisons
historiques d'une stack observée.

Réutiliser ce socle dans les six rubriques de [PREPARE](templates/PREPARE.md).
Compléter le delta utile : parcours et UI si concernés, contrats/données,
AC/tests/fichiers/dépendances, auth/autorisation/tenant/secrets/actions externes,
validation humaine, observabilité/rollback selon risque. N/A doit être motivé.
Aucun Research/Design/Plan supplémentaire requis pour chaque tâche ; les preuves
et décisions déjà valides restent référencées, pas recopiées ni revalidées sans fait nouveau.

L'absence de documents produit ne bloque pas à elle seule ; le socle observé
suffit sans changement structurant. Aucun PASS produit fictif : documents absents,
vides ou legacy ne prouvent pas un gate. Nouveau produit/gros périmètre : préparer
les six rubriques avec plus de profondeur selon [BOOTSTRAP](BOOTSTRAP.md).

## BUILD et SHIP

PREPARE PASS et PR_SPLIT PASS avant BUILD non trivial. Respecter DoR, worktree et
owner unique, environnement selon besoin, routage des skills/modèles disponibles,
lancement natif observé ou fallback honnête. Verify obligatoire, review indépendante,
Goal si applicable, PR_SCOPE et CI PASS, examen final Lead Tech et autorisation
avant merge ; READY_FOR_HUMAN pour mission limitée à une PR.

Changement structurant : consigner dans ADR/architecture et adapter les rubriques.
Seul un fait nouveau invalidant une contrainte rouvre une décision approuvée ;
seules les stories affectées sont BLOCKED. L'autorisation existante suffit.
Risque critique sans mitigation ou information indispensable manquante : BLOCKED.

## Reprise V1 et contrôle

Conserver artefacts, données et décisions V1 ; leurs templates restent facultatifs
pour reprise/legacy. Référencer les éléments utiles, sans imposer de nouveaux PASS
Research/Design/Plan. Un statut historique ne prouve pas une nouvelle révision.

`bash scripts/agentic-check.sh --existing` vérifie la présence du socle, pas les
gates. En PRODUCT, les templates produit legacy peuvent encore être distribués
pour transition ; leur présence ne vaut jamais PASS et ne les rend pas obligatoires
pour une mission V2. Notes, handoffs et preuves personnels restent locaux.
