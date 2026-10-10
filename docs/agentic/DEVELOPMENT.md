# Development — conventions de code

## Portée et priorités
Obligatoire pour toute création, correction et refactorisation de code.
Respecter d'abord les contraintes du langage, du framework, le formatteur et
les conventions cohérentes du dépôt. En cas de conflit substantiel, signaler
la décision à prendre ; ne pas changer les conventions de tout le projet.

## Principes
- SOLID quand applicable : responsabilité unique, extension sans régression,
  substituabilité, interfaces ciblées, dépendance aux abstractions utiles.
- KISS et YAGNI : choisir la solution simple répondant au besoin actuel.
- DRY : factoriser une logique réellement répétée, pas des ressemblances
  accidentelles. Éviter l'abstraction prématurée.
- Préserver les frontières : présentation, métier, données, validation,
  infrastructure et effets de bord ne sont pas une seule responsabilité.
- Une raison principale de changer par module. Ne jamais morceler un module
  cohérent uniquement pour atteindre un nombre de fichiers arbitraire.

## Taille et lisibilité
Seuils de revue indicatifs, sauf standard du framework plus approprié :
- lignes : cible de 100 caractères, formatteur officiel prioritaire ;
- fonction/méthode : cible de 30 lignes ;
- module de logique : cible de 200 lignes ;
- paramètres : préférer 3 ou 4 au maximum, utiliser un objet nommé si utile ;
- imbrication : viser 3 niveaux au maximum avec des sorties anticipées.
Tout dépassement invite à examiner la responsabilité et la lisibilité ;
ne pas rendre le code plus obscur pour faire passer un seuil.

## Emplacement des responsabilités
- Constantes : noms descriptifs, pas de valeurs métier magiques dispersées.
  Centraliser la configuration partagée ; conserver une constante locale
  quand elle appartient à un seul module.
- Types et interfaces : contrats explicites proches du domaine concerné.
  Extraire dans des modules dédiés dès qu'ils sont partagés ou volumineux ;
  éviter les répertoires globaux fourre-tout et les types circulaires.
- Fonctions réutilisables : extraire les règles partagées en modules nommés
  par capacité ou domaine. Préférer des fonctions pures lorsqu'approprié.
- Classes, services et composants : séparer orchestration, accès aux données
  et logique métier ; injecter les dépendances aux frontières nécessaires.
- Tests : à proximité du comportement testé ou selon la convention du dépôt.
  Un nouveau fichier sans raison architecturale n'est pas une amélioration.

## Nommage et structure
Observer les noms existants, le framework et ses conventions officielles.
Choisir des noms explicites et stables ; une même notion garde le même nom.
Ne pas imposer une casse unique à tous les langages.
- TypeScript/JavaScript : PascalCase pour classes, types et composants React ;
  camelCase pour variables/fonctions ; UPPER_SNAKE_CASE pour constantes
  globales immuables. Les noms de fichiers suivent le framework et le dépôt.
- Python : snake_case pour modules, variables et fonctions ; PascalCase pour
  classes ; UPPER_SNAKE_CASE pour constantes de module.
- Go : noms courts et idiomatiques ; export en PascalCase, privé en camelCase ;
  packages en minuscules simples ; noms de fichiers selon le dépôt.
- PHP/Laravel : respecter PSR-12, namespaces/autoload PSR-4 et conventions
  Laravel, notamment PascalCase pour classes et camelCase pour méthodes.
- CSS, SQL et fichiers de configuration : suivre le formatteur, le dialecte
  et les conventions locales établies.
Pour tout autre langage : rechercher ses conventions natives avant de nommer.
Ne pas renommer massivement le code existant dans une PR fonctionnelle.

## Corriger un bug
1. Reproduire et diagnostiquer la cause avec preuves ; vérifier code et tests.
2. Définir le comportement attendu et les cas limites.
3. Corriger au périmètre minimal ; conserver les API et comportements non visés.
4. Ajouter un test de non-régression adapté.
5. Lancer les vérifications utiles et inspecter le diff.

## Ajouter une fonctionnalité
1. Partir du ticket, des critères d'acceptation et du contrat existant.
2. Identifier les responsabilités et les modules à réutiliser.
3. Découper les changements en incréments indépendants et testables,
   conformément à [PULL_REQUESTS](PULL_REQUESTS.md).
4. Implémenter sans refactoring annexe ni duplication évitable.
5. Tester les règles métier, interfaces et contrats touchés.
6. Vérifier le résultat concret et préparer les preuves de revue.

## Refactoring et vérification
Un refactoring préserve le comportement observable. Séparer sa PR d'une
feature lorsque les objectifs peuvent être livrés indépendamment.
Ne jamais masquer un test échoué ni inventer une validation.
Respecter Verify, Review et les gates existants de la méthode.
La checklist de livraison et les règles de commits restent dans leurs
documents respectifs ; ne pas les répliquer ici.
