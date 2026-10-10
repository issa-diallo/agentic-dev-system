# Architecture — <Produit>

## Status
`ARCHITECTURE: DRAFT | PASS | BLOCKED`

PASS signifie « suffisamment décidée pour les premières stories identifiées »,
pas « infrastructure et production entièrement configurées ».
Ne jamais déclarer PASS si une décision critique pour ces stories reste ouverte.

## Contexte décisif
- mode : LIGHT / STANDARD / LARGE
- premier incrément et stories concernées :
- utilisateurs, données, charge connue :
- localisation/résidence des données et exigences légales confirmées :
- budget récurrent cible ou inconnu :
- compétences, délais, contraintes techniques :
- hypothèses à confirmer (ne pas les présenter comme des faits) :

## Décisions requises pour démarrer
| Sujet | Décision ou hypothèse validée | Pourquoi | Stories impactées |
|---|---|---|---|
| Langages et runtime | | | |
| Modules / frontières | | | |
| Données et contrats API | | | |
| Auth / autorisation / tenant si applicables | | | |
| Sécurité, secrets et conformité nécessaires | | | |
| Tests et environnement de développement initial | | | |

Ne renseigner les sujets non applicables que par « non applicable » justifié.
Une technologie facultative (cache, queue, monitoring avancé, etc.) n'est
pas une exigence avant les stories qui la nécessitent.

## Recherche ciblée et comparaison autonome
Avant d'interroger l'utilisateur sur une technologie, identifier les
contraintes réellement manquantes. Si une décision demande une comparaison :
1. Rechercher de manière ciblée jusqu'à trois options crédibles et adaptées,
   dont éventuellement une solution déjà disponible dans le projet.
2. Indiquer tarifs et unités (mensuel/usage), région, limitations, coûts
   annexes, réversibilité, sources vérifiables et date de consultation.
3. Distinguer prix confirmés, estimations et informations non vérifiées.
4. Recommander une option avec raisons et compromis ; poser uniquement
   les questions dont la réponse change réellement la décision.
5. Sans accès aux sources actuelles, signaler l'incertitude ; ne jamais
   inventer prix, fonctionnalités ou garanties de résidence des données.
Ne jamais souscrire, déployer ni engager de dépense sans autorisation.

| Option | Compatibilité / région | Coût et source datée | Limites | Avis |
|---|---|---|---|---|
| A | | | | |
| B | | | | |
| C (si utile) | | | | |

## Décisions reportées — registre obligatoire
| Décision | Hypothèse provisoire | Pourquoi reportable | Déclencheur / story | Responsable | Risque |
|---|---|---|---|---|---|
| | | | | | |

Catégories :
- BLOQUANT MAINTENANT : impacte sécurité, données, contrat ou une story
  imminente et aucune hypothèse sûre et réversible n'est possible.
- AVANT STORY : dépendance obligatoire avant Research/Design/Plan/Execute
  de la story indiquée ; cette story est BLOCKED jusque-là, pas tout le produit.
- NON BLOQUANT : décision réversible sans conséquence sur l'incrément courant.
Ne jamais reporter auth, permissions, tenant, réglementation ou conservation
des données lorsqu'ils conditionnent déjà les premières stories.

## Schéma initial
- structure et frontières :
- flux de données et contrats essentiels :
- tests pertinents et critères de sécurité :
- développement local et exécution du premier incrément :
- stratégie de déploiement initiale ou story qui doit la définir :
- compromis et alternatives rejetées :

## ADR
Créer un ADR pour une décision à conséquences durables, difficilement
réversible ou à risque significatif ; indiquer son impact et son statut.
Les choix simples/réversibles restent consignés ici. Un ADR requis avant
la première story doit être accepté avant PASS ; un ADR différé est rattaché
à une story et ne bloque que celle-ci jusqu'à décision.

## Architecture Gate
- [ ] Contraintes critiques des premières stories comprises
- [ ] Stack et frontières suffisantes pour les premières stories
- [ ] Contrats, données et sécurité nécessaires explicités
- [ ] Tests et environnement de développement initial définis
- [ ] Décisions critiques et ADR nécessaires maintenant résolus
- [ ] Options comparées et sources citées lorsqu'une recherche est utile
- [ ] Décisions restantes classées, avec propriétaire et déclencheur
- [ ] Aucun risque critique caché derrière une hypothèse

Verdict : PASS / BLOCKED
Motif précis si BLOCKED et prochaine action :
