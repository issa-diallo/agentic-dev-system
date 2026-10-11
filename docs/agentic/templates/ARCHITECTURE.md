# Architecture — <Produit>

## Statut

`ARCHITECTURE: DRAFT | PASS | BLOCKED`

## Contrat de préparation

Produire un cadrage court à partir du PRD, des stories et des choix utilisateur.
Adapter la profondeur au risque ; supprimer les rubriques non pertinentes.
Architecture PASS signifie « direction exploitable pour développer ».
Les preuves d’exécution sont produites en Execute/Verify.

Aucun benchmark, prototype, coût chiffré ou comparaison exhaustive requis ici.
Un outil décidé ne déclenche aucun test de qualification en Architecture ou ADR.
Une fois les choix utiles consignés et les principes cohérents, terminer la phase.
Exception : un test préalable indispensable pour lever une contradiction concrète
ou un risque critique sans mitigation. Consigner le cas, la contrainte touchée,
le test minimal et son critère d’arrêt ; pas de campagne générale de qualification.
Un plafond budgétaire déjà imposé reste une contrainte ; son contrôle est planifié
avant l’engagement payant concerné. Ne pas inventer des mesures.

## Contraintes et choix retenus

- besoins et contraintes impératives du PRD :
- stack utile au premier incrément (langage, application, données, hébergement) :
- origine des choix : utilisateur / socle existant / recommandation de l’agent :
- raison courte et compromis connus :

Un outil explicitement choisi par l’utilisateur est enregistré sans lui demander
de le justifier à nouveau. Sans choix, recommander une solution adaptée et avancer.
Comparer des alternatives seulement lorsqu’un arbitrage réel reste ouvert.
Ne pas ajouter cache, queue, recherche ou autres services sans besoin identifié.

## Responsabilités, données et flux

- modules et responsabilités :
- données principales et contrats entre modules :
- intégrations et actions externes :
- authentification, autorisation et isolation tenant si applicables :
- données sensibles, secrets et validation humaine si pertinents :
- livraison, stratégie de tests, observabilité et rollback pertinents :

Décrire les principes nécessaires au premier incrément ; les schémas détaillés,
endpoints, configurations et tests se précisent en Research/Design/Plan.

## Décisions durables / ADR

Créer un ADR court pour un arbitrage aux conséquences durables : frontière
majeure, isolation des données, contrat partagé, engagement difficile à annuler
ou remplacement d’une décision approuvée. Plusieurs outils d’un même arbitrage
peuvent être regroupés. Pas d’ADR systématique par composant de stack.
Les choix usuels sont tracés ci-dessus. Un ADR utile est rédigé ici sans exiger
de preuve technique ni une nouvelle approbation d’un choix déjà autorisé.

- ADR concernés et liens, ou « aucun arbitrage nécessitant un ADR » :

## Validations différées

| Hypothèse / risque | Story ou suivi | Responsable / rôle | Échéance | Vérification attendue | Action si échec |
|---|---|---|---|---|---|
| Faisabilité d’une intégration | … | Implementer | Execute/Verify de la story | Test du contrat | Corriger ; réviser uniquement la décision invalidée |
| Coûts d’exploitation | … | Produit | Après implémentation, avant montée en charge | Usage et facture observés | Ajuster le dimensionnement |

Ne garder que les validations pertinentes. Reporter ce registre dans le Plan
concerné ; Verify en consigne les résultats ou le suivi encore ouvert.
Sécurité, intégrité des données, contraintes légales ou budget impératif :
échéance avant l’exposition, l’action irréversible ou l’engagement concerné.
Un suivi produit après implémentation n’empêche pas le PASS s’il n’est pas
nécessaire à l’acceptation ou à la livraison actuelle.

## Gate Architecture

- [ ] direction et choix utilisateur enregistrés
- [ ] responsabilités et flux principaux compréhensibles
- [ ] protections pertinentes définies au niveau des principes
- [ ] validations différées affectées et échéancées
- [ ] ADR nécessaires rédigés, sans dossier comparatif obligatoire
- [ ] aucune contradiction indispensable ni risque critique sans mitigation

Faire une seule vérification de cohérence, puis PASS et poursuivre vers Design
System. Ne pas rouvrir la phase pour une préférence technique ou une preuve absente.

BLOCKED seulement si une contradiction concrète empêche le premier incrément
ou si un risque critique n’a aucune mitigation. Consigner le fait, la contrainte
violée, le périmètre affecté et l’unique décision/information nécessaire.
Poser une question ciblée seulement si elle est indispensable pour trancher.
Un fait nouveau peut justifier une révision ; conserver les choix approuvés
et poursuivre les stories indépendantes.

Verdict : PASS / BLOCKED
Motif précis si BLOCKED et prochaine action :
