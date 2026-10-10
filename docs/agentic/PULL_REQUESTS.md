# Pull Requests — petites modifications vérifiables

## Principe
Une PR = un objectif précis, un changement compréhensible et un commit
logique final. La revue humaine doit pouvoir comprendre rapidement pourquoi,
quoi et comment le résultat a été vérifié.

## Limites par défaut
- Cible : 1 à 3 fichiers modifiés, idéalement 1 seul si cela suffit.
- Cible indicative : 100 lignes de diff au total ou moins.
- Un seul commit dans l'historique final de la PR ; les commits de travail
  peuvent être regroupés par squash à la fusion.
- Une branche et une PR par changement autonome, liée à son ticket.
- Une PR ne mélange pas feature, bugfix et refactoring sans dépendance directe.

Les limites sont des alertes de découpage et de revue, pas un prétexte pour
retirer les tests, les types, les migrations ou les protections indispensables.
Documenter brièvement tout dépassement : pourquoi ces fichiers doivent être
livrés atomiquement et pourquoi une division présenterait plus de risque.

## Découper avant de coder
1. Définir l'intention et les critères vérifiables.
2. Identifier les fichiers nécessaires et les dépendances.
3. Si le changement dépasse les cibles, proposer plusieurs PR indépendantes
   ou empilées avec contrats stables et ordre de fusion documenté.
4. Chaque PR doit rester cohérente, testable et, si possible, déployable ;
   éviter les étapes qui cassent temporairement la production.
5. Pour frontend/backend distincts, stabiliser les contrats API ; vérifier la
   compatibilité ascendante jusqu'à la livraison complète.

## Revue et fusion
- Relire les fichiers et le diff : pas de formatage ou renommage parasite.
- Vérifier conformité [DEVELOPMENT](DEVELOPMENT.md), critères d'acceptation,
  tests pertinents, sécurité et absence de régression.
- Appliquer [COMMITS](../../COMMITS.md) aux messages.
- Respecter le reviewer indépendant, Verify, les contrôles CI et l'examen
  final Lead Tech définis par la méthode.
- Si un commit est ajouté après revue, réviser à nouveau sa tête et sa CI.
- Ne jamais sacrifier la qualité, l'atomicité ou une validation obligatoire
  pour forcer artificiellement une PR à trois fichiers.
- Regrouper en branche de release si nécessaire, sans remplacer la revue de
  chaque PR par une revue massive.
