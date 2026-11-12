# PROMPTS.md — Bibliothèque de prompts de réflexion

> Une collection de **20 instructions en langage naturel** pour challenger une idée, prendre des décisions et améliorer un projet.
>
> **Important :** `Grill me`, `Roast me`, etc. ne sont **pas des commandes natives ou des slash commands officielles** de ChatGPT, Claude Code ou Codex. Ce sont des formulations de prompts à copier et à adapter. Elles ne déclenchent pas automatiquement des outils, des actions ni un mode système.

## Utilisation

1. Choisir une instruction dans le catalogue.
2. Remplacer `[PROJET]`, `[DÉCISION]` ou `[OBJECTIF]` par le contexte concret.
3. Demander des exemples, des hypothèses vérifiables et des actions priorisées.
4. Exiger que le modèle distingue **faits vérifiés**, **hypothèses** et **informations manquantes**.

**Modèle recommandé :**

```text
[COMMANDE] — Analyse [PROJET / DÉCISION].

Contexte : [objectif, utilisateur, contraintes, stade du projet].
Appuie-toi uniquement sur les informations disponibles.
Distingue faits, hypothèses et inconnues.
Identifie les 3 risques ou objections les plus importants,
puis propose 3 actions concrètes, classées par impact et effort.
Ne confonds pas critique constructive et agressivité.
```

## Catalogue des 20 prompts

### 1. Critique et remise en question

| Prompt | Usage | Exemple prêt à copier |
|---|---|---|
| **Roast me** | Critique humoristique et incisive | `Roast me : critique avec humour mes habitudes de développement et termine par 3 conseils utiles.` |
| **Grill me** | Questions difficiles et contradictions | `Grill me : pose-moi une question difficile à la fois sur la viabilité de [PROJET] et attends ma réponse.` |
| **Challenge me** | Contestation des hypothèses | `Challenge me : remets en question les 5 hypothèses majeures de [PROJET].` |
| **Judge me** | Évaluation selon des critères explicites | `Judge me : évalue [DÉCISION] sur l'impact, le coût, le risque et la réversibilité.` |
| **Be brutally honest** | Retour direct, factuel | `Be brutally honest : dis-moi ce qui ne fonctionne pas dans [PROJET], avec des preuves et sans flatterie.` |
| **Call me out** | Incohérences et engagements non tenus | `Call me out : signale mes contradictions entre objectifs annoncés et actions réalisées.` |
| **Expose my blind spots** | Angles morts | `Expose my blind spots : quels risques commerciaux, humains ou techniques ai-je oubliés dans [PROJET] ?` |
| **Destroy my idea** | Recherche des scénarios d'échec | `Destroy my idea : construis le meilleur argument contre [PROJET], puis explique ce qui pourrait le sauver.` |

### 2. Analyse des risques et décisions

| Prompt | Usage | Exemple prêt à copier |
|---|---|---|
| **Play devil's advocate** | Défense argumentée de la thèse opposée | `Play devil's advocate : pourquoi un client refuserait-il d'acheter [PROJET] ?` |
| **Reality check** | Faisabilité réelle | `Reality check : compare les objectifs de [PROJET] aux moyens, contraintes et preuves disponibles.` |
| **Stress test my plan** | Test de robustesse | `Stress test my plan : teste [PLAN] face à un budget divisé par deux, un retard et un refus client.` |
| **Red team my project** | Recherche méthodique des défaillances | `Red team my project : évalue les risques d'architecture, sécurité, conformité et exploitation de [PROJET].` |
| **Audit me** | Audit des pratiques | `Audit me : examine mon workflow de cadrage, tests, développement et recette ; relève les inefficacités.` |
| **Debate me** | Débat contradictoire | `Debate me : défends l'avis contraire à ma décision [DÉCISION] avec des arguments vérifiables.` |

### 3. Coaching et stratégie

| Prompt | Usage | Exemple prêt à copier |
|---|---|---|
| **Coach me** | Objectifs et progression | `Coach me : transforme [OBJECTIF] en plan hebdomadaire mesurable, avec points de contrôle.` |
| **Mentor me** | Conseils issus de scénarios réalistes | `Mentor me : guide-moi pour passer de développeur à éditeur logiciel B2B.` |
| **Interrogate me** | Clarification par questions successives | `Interrogate me : questionne-moi une étape à la fois jusqu'à clarifier le besoin client de [PROJET].` |
| **Push me harder** | Exigence et discipline | `Push me harder : propose un objectif plus ambitieux mais mesurable pour les 30 prochains jours.` |
| **Prioritize for me** | Arbitrage et suppression du superflu | `Prioritize for me : classe mes tâches de [PROJET] par impact, urgence et effort ; indique quoi abandonner.` |
| **Think like a CEO** | Vision rentabilité et marché | `Think like a CEO : analyse [PROJET] avec les critères acquisition, coût, marge, rétention et trésorerie.` |

## Combinaisons utiles

### Validation d'un produit B2B
```text
Challenge me + Think like a CEO + Reality check.
Analyse [PROJET] : cible, problème, alternatives, disposition à payer,
coût d'acquisition et preuve de demande.
Sépare les hypothèses des faits. Propose 5 entretiens de validation.
```

### Revue technique avant production
```text
Red team my project + Stress test my plan.
Analyse l'architecture de [PROJET] : sécurité, confidentialité, gestion
des erreurs, observabilité, migrations, continuité et coûts.
Classe les risques et donne les tests à exécuter avant production.
```

### Focus hebdomadaire
```text
Grill me + Prioritize for me.
Questionne-moi sur mes résultats de la semaine, une question à la fois.
Puis propose les 3 priorités de la prochaine semaine et ce que je dois arrêter.
```

## Cas pratiques — projets de ce dépôt

- **CustomsFlow** : `Destroy my idea : pourquoi un transitaire ne paierait-il pas pour un portail de pré-dédouanement automobile et de suivi 846A ?`
- **Doc2XML** : `Red team my project : recherche les risques liés à l'extraction de documents et à la génération de XML réglementaires, avec validation humaine.`
- **Agentic Dev System** : `Audit me : mon orchestration multi-modèles améliore-t-elle réellement le coût, la qualité et la vitesse par rapport à un workflow plus simple ?`

## Principes de qualité

- Une critique doit porter sur les **idées et décisions**, pas sur la personne.
- Ne pas inventer de chiffres, de preuves de marché ou de règles juridiques.
- Définir des critères observables : temps gagné, taux d'erreur, taux de dossiers complets, coût par traitement, volonté de payer.
- Pour les questions réglementaires, vérifier les sources et distinguer l'analyse exploratoire d'un avis professionnel.
- Pour les agents de développement : ces prompts servent à l'analyse ; **ils ne remplacent pas** les consignes, tests, gates de validation ou procédures du dépôt.

---

**Maintenance :** ajouter de nouveaux prompts avec leur objectif, un exemple reproductible et les limites d'utilisation. Éviter les doublons et les formulations uniquement spectaculaires.
