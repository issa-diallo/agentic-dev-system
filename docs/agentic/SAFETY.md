# Agent Safety Rules

## Objectif

Permettre une forte autonomie dans un périmètre contrôlé.

## Commandes dangereuses

Un agent ne doit pas exécuter silencieusement une commande destructrice ou irréversible.

Exemples :
- `rm -rf`
- `git reset --hard`
- `git clean -fd`
- `git push --force`
- suppression massive de fichiers
- reset/destruction de base de données
- `DROP DATABASE`
- `docker system prune`
- suppression de volumes
- destruction d'infrastructure
- rotation/suppression de secrets

## Politique

- bloquer par hook lorsque possible ;
- sinon demander une validation explicite ;
- préférer une alternative réversible ;
- sauvegarder ou documenter le rollback ;
- ne jamais exposer des secrets dans les logs.

## Main branch / production

- pas de force push ;
- pas de changement destructif sans plan ;
- pas de migration irréversible sans rollback ;
- pas de merge avec Critical/Major ouvert.
