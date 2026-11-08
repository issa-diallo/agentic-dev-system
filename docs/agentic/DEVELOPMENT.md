# Development — conventions de code

## Portée et priorités
Obligatoire pour toute création, correction et refactorisation de code.
Respecter d'abord les contraintes du langage, du framework, le formatteur et
les conventions cohérentes du dépôt. En cas de conflit substantiel, signaler
la décision à prendre ; ne pas changer les conventions de tout le projet.

## Principes
- SOLID quand applicable, sans cérémonie :
  - S : une raison principale de changer par module. Ne jamais morceler un
    module cohérent uniquement pour atteindre un nombre de fichiers arbitraire.
  - O : étendre par un point de variation déjà réel (au moins deux cas
    existants), pas par une hiérarchie ou un plugin spéculatif.
  - L : une implémentation substituable respecte le contrat de l'abstraction
    (entrées, sorties, erreurs) sans cas particulier chez l'appelant.
  - I : interfaces petites, définies par le besoin du consommateur ; aucune
    méthode inutilisée à implémenter.
  - D : dépendre d'une abstraction à une frontière réelle (réseau, base,
    horloge, service externe), pas pour chaque classe.
- KISS et YAGNI : choisir le code le plus simple qui exprime clairement
  l'intention et répond aux critères d'acceptation du ticket ; éviter l'astuce
  qui oblige à relire. Ne pas ajouter de code, paramètre, option, configuration,
  dépendance, interface ou point d'extension « au cas où » ; une abstraction à une
  seule implémentation, sans frontière réelle, est du YAGNI. Retirer le code mort
  que le changement introduit.
- DRY : une règle métier, une constante, un type ou une validation a une seule
  source de vérité. Factoriser à la troisième répétition réelle, ou dès que la
  même règle doit évoluer ensemble ; tolérer des ressemblances accidentelles et
  des modules qui changent pour des raisons différentes. Éviter l'abstraction
  prématurée.
- En cas de tension, YAGNI et la lisibilité priment sur DRY et SOLID.
- Préserver les frontières : présentation, métier, données, validation,
  infrastructure et effets de bord ne sont pas une seule responsabilité.

## Correspondances déclaratives — CORE-DESIGN-001

Appliquer obligatoirement [Prefer Declarative Mapping Over Conditional Logic](../../rules/core/prefer-declarative-mapping.md)
en planification, implémentation, refactoring et revue, dans tous les langages.
Dès deux branches simples valeur/résultat, évaluer une correspondance native
nommée si elle améliore la clarté. Préserver fallbacks, priorité, types et effets
de bord ; garder les conditions pour prédicats complexes ou sémantique inadaptée.
Vérifier les clés connues/inconnues, défauts, précédence et cas limites par les
tests appropriés. Cette préférence ciblée ne remplace pas le seuil DRY général.

## Taille et lisibilité
Seuils de revue indicatifs, sauf standard du framework plus approprié :
- lignes : cible de 100 caractères, formatteur officiel prioritaire ;
- fonction/méthode : cible de 30 lignes ;
- module de logique : cible de 200 lignes ;
- paramètres : préférer 3 ou 4 au maximum, utiliser un objet nommé si utile ;
- imbrication : viser 3 niveaux au maximum avec des sorties anticipées.
Tout dépassement invite à examiner la responsabilité et la lisibilité ;
ne pas rendre le code plus obscur pour faire passer un seuil.
Pour le code ajouté ou modifié, la revue motive les dépassements ou demande une
simplification. Un fichier existant long ne justifie pas un refactoring annexe :
isoler sa remise en ordre si elle peut être livrée indépendamment.
« Un commit, une fonction » signifie une intention précise, pas une fonction
syntaxique obligatoire : plusieurs fonctions liées et leurs tests peuvent former
un seul petit changement cohérent.

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
- Tests : à proximité du comportement testé ou selon la convention du dépôt. Écrire avant
  le code les tests unitaires issus des règles métier (RM1…) et critères d'acceptation
  explicitement établis dans le ticket ; ils guident l'implémentation. Ne pas inventer de
  règles ni exiger un cycle rouge/vert ou un commit rouge. Conserver ces tests pendant
  l'implémentation et exécuter les contrôles pertinents en Verify.
  Un nouveau fichier sans raison architecturale n'est pas une amélioration.

## Nommage et structure
Observer les noms existants, le framework et ses conventions officielles.
Choisir des noms clairs, simples et cohérents, issus du vocabulaire métier du
ticket, qui révèlent le rôle et l'intention (ce que c'est ou ce que cela fait,
pas comment) ; une même notion garde le même nom. Éviter les abréviations
obscures et les noms génériques (`data`, `info`, `manager`, `tmp`, `util`)
sauf convention du framework. Cela vaut pour les fonctions, variables, classes
et constantes. Ne pas imposer une casse unique à tous les langages.
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
3. Corriger un seul problème au périmètre minimal ; conserver les API et comportements
   non visés. Tout autre bug indépendant reçoit son propre ticket et sa propre PR.
4. Ajouter un test de non-régression adapté.
5. Lancer les vérifications utiles et inspecter le diff.

## Ajouter une fonctionnalité
1. Partir du ticket, des critères d'acceptation et du contrat existant.
2. Identifier les responsabilités et les modules à réutiliser.
3. Passer PR_SPLIT avant BUILD non trivial : une raison métier principale par PR ;
   conserver code, tests, migrations et contrats indispensables ensemble.
   Découper les changements en incréments indépendants et testables,
   conformément à [PULL_REQUESTS](PULL_REQUESTS.md).
4. Implémenter sans refactoring annexe ni duplication évitable. Dès qu'un changement
   indépendant apparaît, revoir le découpage ticket/PR avant de poursuivre selon
   PULL_REQUESTS ; cette vérification s'applique aussi aux petites modifications.
5. Tester les règles métier, interfaces et contrats touchés.
6. Vérifier le résultat concret et préparer les preuves de revue.

## Refactoring et vérification
Un refactoring préserve le comportement observable. Séparer sa PR d'une
feature lorsque les objectifs peuvent être livrés indépendamment.
Ne jamais masquer un test échoué ni inventer une validation.
Respecter Verify, Review et les gates existants de la méthode.
La checklist de livraison et les règles de commits restent dans leurs
documents respectifs ; ne pas les répliquer ici.
