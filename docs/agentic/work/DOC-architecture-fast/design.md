# Design — DOC-architecture-fast

DESIGN: PASS

Architecture fixe une direction suffisante pour commencer : choix et origine,
frontières, données et flux majeurs, protections pertinentes, stratégie de
livraison/test. Les inconnues mesurables vont dans un registre de validations.

Choix utilisateur conservés ; sans choix, recommandation unique accompagnée
d’une raison courte. Alternatives uniquement si un arbitrage reste ouvert.
Un ADR court peut regrouper un arbitrage cohérent ; les outils usuels sont
consignés dans Architecture. Aucun second gate de validation pour ces outils.

Échéances : faisabilité en Execute/Verify de la story concernée ; sécurité,
intégrité et contraintes impératives avant l’exposition ou l’action concernée ;
optimisations/coûts d’exploitation après implémentation par le produit, sauf
budget impératif explicite. Pas de mesure inventée.

Après rédaction, une seule vérification de cohérence, PASS et phase suivante.
Retour uniquement sur fait nouveau invalidant une contrainte, avec périmètre
affecté et question ciblée. Les stories indépendantes continuent.
