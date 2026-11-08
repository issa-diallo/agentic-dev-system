# Rédiger un ticket pour préparer les tests métier

Un ticket décrit le comportement voulu et les règles qui le justifient. Il doit
permettre de préparer les tests sans inventer une attente métier. Il ne remplace
pas PREPARE ni PR_SPLIT : l’agent complète ensuite les choix techniques et le plan.

## Informations à donner

Le contenu doit permettre d’identifier **l’objectif, les règles métier et les
contraintes**, sans imposer ces intitulés exacts. Ces informations peuvent être
dans la description, les critères d’acceptation, les exemples ou des sources
référencées. Le modèle ci-dessous est une aide, pas un format obligatoire.

1. **Problème et objectif** : situation actuelle, difficulté et résultat souhaité.
2. **Périmètre** : capacité concernée, exclusions et comportements à préserver.
   Un besoin contenant plusieurs capacités autonomes peut être un ticket parent ;
   PR_SPLIT définit les sous-tickets d’implémentation et leurs PR.
3. **Acteurs et contexte** : qui agit, sur quelles données, depuis quel parcours,
   avec quels droits et dans quel tenant si ces notions sont pertinentes.
4. **Règles métier identifiées** : RM1, RM2… avec conditions d’application et effets
   attendus. Citer les règles existantes réutilisées et les décisions approuvées.
5. **Critères d’acceptation** : AC1, AC2… observables et reliés aux règles concernées.
6. **Exemples concrets** : état initial, action ou entrée, résultat attendu et données
   après l’action. Inclure refus et limites seulement lorsqu’ils sont pertinents.
7. **Contraintes et dépendances** : documents, tickets liés, contrats et décisions
   imposées ; questions ouvertes avec leur caractère bloquant ou reportable.

Référencer une source précise suffit : ne pas recopier tout le cadrage produit.
Mentionner les parcours, données sensibles, effets externes et exigences de sécurité
qui concernent le ticket. Pour une rubrique sans objet, écrire N/A et la raison.
Une information inconnue est une question ouverte, pas un N/A.

## Écrire une règle vérifiable

Préciser : **dans quelle situation, qui fait quoi, quel résultat est attendu**.
Éviter les formulations comme « gérer les factures », « sécurisé » ou « fonctionne
correctement » sans comportement observable.

Un critère d’acceptation décrit ce que l’on doit constater pour une règle. Les
scénarios donnent des exemples concrets permettant de vérifier ce critère. Un seul
critère peut demander plusieurs scénarios et plusieurs tests.

Chaque scénario métier doit avoir une source : règle explicite du ticket ou règle
existante précisément référencée. Une conséquence directement nécessaire au respect
de cette règle peut être testée en expliquant le lien. Une nouvelle attente métier
doit être clarifiée avant d’être transformée en test.

L’absence d’une interdiction ne prouve pas une autorisation. « Une facture payée
ne peut plus être modifiée » ne prouve pas qu’une facture non payée est modifiable.
Elle peut être bloquée pour un autre motif. Préserver son comportement existant
sans lui inventer un nouveau critère de réussite.

L’agent peut ajouter des tests techniques de régression ou de contrat fondés sur
le code et les contrats existants. Il distingue leur source des règles du ticket.
Le rédacteur n’a pas à choisir les fichiers, le framework de test ou tous les détails
d’implémentation ; ces éléments se déterminent en PREPARE puis en BUILD.

## Modèle à remplir dans le ticket

Adapter les rubriques à la capacité et au risque. Remplacer les indications entre
chevrons par des faits ou des références ; une rubrique vide n’est pas une preuve.

```markdown
## Problème et objectif
Aujourd’hui : <comportement constaté>.
Résultat souhaité : <changement observable et raison>.

## Périmètre
Inclus : <capacité et parcours concernés>.
Exclus : <capacités ou changements non demandés>.
À préserver : <comportements/contrats existants pertinents, références>.

## Acteurs et données
Acteur : <utilisateur, rôle ou système>.
Données et états concernés : <entités, champs, états>.
Accès / tenant / données sensibles / effets externes : <règles ou références>.

## Sources et décisions existantes
- SRC1 : <document/section, ticket/commentaire ou décision, contenu pertinent>.

## Règles métier
- RM1 — <condition -> comportement et effet attendus>. Source : <ticket ou SRC1>.

## Critères d’acceptation
- [ ] AC1 — <résultat observable>. Règle : RM1.

## Scénarios métier à vérifier
| ID | Règle / AC | État initial | Action / entrée | Résultat et données attendus |
|---|---|---|---|---|
| SC1 | RM1 / AC1 | <préconditions> | <action précise> | <résultat vérifiable> |

## Contraintes et dépendances
<Tickets liés, ordre nécessaire, contrats, contraintes imposées ou aucune connue>.

## Questions ouvertes
| Question | Conséquence si sans réponse | Bloquante maintenant ? | Réponse / responsable |
|---|---|---|---|
```

## Exemple : interdire la modification d’une facture payée

Ce qui suit est un **exemple de ticket complet**. Les précisions sur l’acteur, le
champ et le parcours sont des décisions explicites de cet exemple, à fournir ou à
retrouver dans un vrai ticket ; elles ne se déduisent pas de son seul titre.

**Problème et objectif.** Le formulaire de détail permet actuellement de changer
le libellé d’une facture payée. Empêcher cet enregistrement.

**Périmètre.** Le changement du libellé depuis ce formulaire. Les règles existantes
d’accès restent applicables. L’annulation de paiement et la modification des autres
champs ne sont pas traitées par ce ticket. Le comportement des factures non payées
reste inchangé ; aucune nouvelle autorisation n’est demandée.

**Acteur et données.** Utilisateur ayant déjà accès à cette facture selon les règles
existantes du produit. Facture F1 avec état `payée` et libellé `Prestation A`.

**RM1.** Une tentative de modification du libellé d’une facture payée depuis son
formulaire de détail doit être refusée, avec une indication visible du refus.
Le libellé enregistré doit rester inchangé. Source : règle explicite de ce ticket.

**AC1.** Depuis ce formulaire, l’utilisateur tente de remplacer `Prestation A` par
`Prestation B` sur F1. Le refus est visible ; après rechargement, le libellé reste
`Prestation A`. Règle : RM1.

| Scénario | Source | Vérification |
|---|---|---|
| SC1 | RM1 / AC1 | La tentative d’enregistrement est refusée et le refus est visible. |
| SC2 | RM1 / AC1 | Après cette tentative, le libellé enregistré reste `Prestation A`. |

SC2 vérifie l’effet du refus : afficher une erreur tout en enregistrant la nouvelle
valeur ne satisferait pas RM1. Aucun scénario affirmant qu’une facture non payée
est modifiable n’est ajouté à partir de cette règle.

Le ticket précise ici l’acteur, le champ, le canal et l’effet attendu. S’ils sont
absents d’un vrai ticket et des sources existantes, l’agent clarifie ceux nécessaires
à l’incrément avant de figer les tests. Il n’impose pas un texte d’erreur exact
si seul un refus visible est demandé.

## Utilisation dans Agentic

En PREPARE, reprendre ces informations dans les six rubriques ou par référence.
Conserver la traçabilité **source -> règle -> critère -> scénario -> test**. Le plan
de tests doit indiquer les règles couvertes et les lacunes identifiées ; la revue
les confronte au ticket, pas seulement aux tests qui passent.

Un ticket complet n’exige pas une nouvelle approbation humaine systématique.
L’orchestrateur vérifie sa complétude et valide PR_SPLIT selon la méthode. Une
question réellement indispensable non résolue bloque l’unité affectée ; le reste
du travail autorisé peut continuer.

Ce guide décrit le contenu du ticket. Les gates et modalités d’exécution des tests
restent définis par [PREPARE](templates/PREPARE.md), [DEVELOPMENT](DEVELOPMENT.md)
et [DELEGATION](DELEGATION.md). La préparation détaillée et les preuves produites
pendant la mission restent locales selon [PULL_REQUESTS](PULL_REQUESTS.md).
