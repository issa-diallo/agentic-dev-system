# Contexte, recherche et reprise

Le main agent garde objectif, contraintes, décisions, blockers et evidence.
Avant une longue tâche, déléguer les explorations lourdes avec un contrat étroit ;
le retour contient faits sourcés, chemins utiles, risques et décision attendue,
pas le journal complet. Les réponses restent concises : décisions, modifications,
tests, risques et prochaines actions. Éviter longs logs et code répété tout en
préservant les diagnostics utiles. Aucun dump de secrets, logs ou documents sans nécessité.

## Recherche ciblée

Partir du ticket, du chemin fourni et de l’index de méthode. Utiliser `rg --files`
pour localiser puis `rg -n` dans les zones utiles et lire les passages concernés.
Élargir seulement si l’hypothèse échoue. Grouper les lectures indépendantes,
conserver chemins et conclusions dans Research ; ne pas relire systématiquement
le même fichier. Le code réel prime sur une carte obsolète. Une recherche vide
ou tronquée ne prouve pas l’absence : vérifier portée, exclusions et sortie brute.
Charger skills/MCP/plugins uniquement pour un besoin identifié. Ne pas créer de
documentation artificielle pour nourrir l’agent.

## Checkpoint et compaction

À une transition naturelle ou avant une reprise, remplir [HANDOFF](templates/HANDOFF.md) :
objectif/AC, phase et dernier PASS, décisions avec raisons, contraintes et refus,
fichiers et branche/worktree, commandes/résultats, erreurs encore ouvertes,
blockers, prochaines étapes et lectures ciblées. Distinguer fait et hypothèse.
Ne pas compacter tous les quelques messages ni imposer cinq questions : demander
seulement une information réellement manquante. Si une commande de compaction
existe dans le client, vérifier sa syntaxe ; le checkpoint fonctionne sans elle.
Après reprise, vérifier état Git, artefacts et evidence avant l’étape suivante.
Changer les préfixes peut modifier la réutilisation du cache ; aucune garantie
sur le quota Codex ne découle du [cache API](https://developers.openai.com/api/docs/guides/prompt-caching).

## Mesurer sans promettre

Comparer une même tâche, version, modèle/niveau, outils, fichiers et critères,
avec succès et retours correctifs. Noter nombre de fichiers lus, lectures redondantes, octets/lignes chargés, appels d’outils,
durée et retries ; tokens/coût/quota seulement si une mesure réelle est exposée,
sinon « non observable ». Octets/4 est une estimation grossière, pas une facture.
Le gain de taille d’AGENTS n’est ni un benchmark de qualité ni un gain de quota.
Ne pas réécrire les vieux messages pour simuler une économie. Une optimisation
qui fait perdre un diagnostic ou un AC est rejetée, même si la sortie raccourcit.

Scénario reproductible : compter `wc -c -l AGENTS.md`, choisir un ticket LIGHT,
consigner les documents effectivement lus via l’index ; comparer avec la lecture
complète antérieure sur le même ticket. Répéter sur LARGE multi-app avec contrats
et sécurité. Rapporter taille statique et comportement observé séparément.

## Analyse des 26 conseils du guide fourni

Synthèse critique du guide utilisateur (septembre 2026), sans redistribution du
PDF. Chiffres commerciaux et anecdotes non repris comme preuves. « Reporter »
signifie évaluer seulement sur demande/besoin ; aucune installation automatique.

| N° | Conseil | Décision et raison |
|---|---|---|
| 01 | Réduire le raisonnement | Adapter : niveau le moins coûteux capable, risque et validation priment. |
| 02 | Éviter Max | Adapter : aucun plafond universel ; escalade justifiée. |
| 03 | Comprendre Ultra | Retenir : vérifier disponibilité et coût de délégation, voir MODELS. |
| 04 | Message programmé à 6 h | Rejeter : hors besoin produit, règles de quota variables, aucune tâche créée. |
| 05 | Choisir avant de commencer | Adapter : stabilité par phase, pas de promesse cache client. |
| 06 | Désactiver vitesse 1,5x | Reporter : arbitrage utilisateur latence/coût, aucune config globale modifiée. |
| 07 | Corriger en cours de travail | Retenir : intégrer les précisions sans perdre l’objectif initial. |
| 08 | Caveman | Rejeter : prose concise suffit ; ne pas sacrifier précision et preuves. |
| 09 | I Have ADHD | Reporter : besoin individuel, pas de plugin imposé à tous les projets. |
| 10 | Identifier la consommation | Adapter : mesures observables, aucune attribution de quota inventée. |
| 11 | Fournir un chemin | Retenir : point de départ précis réduit les recherches inutiles. |
| 12 | Cartographier le workspace | Adapter : carte courte et actualisée selon les changements. |
| 13 | AGENTS comme aiguillage | Retenir : invariants à la racine, détails obligatoires selon déclencheur. |
| 14 | Second cerveau | Reporter : utile sur corpus durable, pas de doublon du code. |
| 15 | Connecteurs inutilisés | Adapter : charger au besoin ; désactivation globale seulement autorisée. |
| 16 | Nettoyage mensuel | Adapter : audit si accumulation ; ni suppression ni planning implicites. |
| 17 | Images ailleurs | Reporter : fournisseur, données, secrets et coûts à qualifier séparément. |
| 18 | Compaction ciblée | Adapter : checkpoint naturel, préserver décisions et erreurs ouvertes. |
| 19 | Ponytail | Reporter : simplicité retenue ; outil optionnel à qualifier. |
| 20 | RTK | Reporter : mesurer sorties et diagnostics, pas extrapoler au coût total. |
| 21 | Headroom | Reporter : proxy/cache/récupération et auth à qualifier. |
| 22 | QMD | Reporter : gros corpus seulement ; coût d’index et données sensibles. |
| 23 | Budget | Adapter : budget observable ou indicateurs approximatifs explicités. |
| 24 | Tâches récurrentes | Retenir : amortir une optimisation mesurée sans chiffre garanti. |
| 25 | Agents nommés | Adapter : trois rôles portables, spécialités par contrat et capacités disponibles. |
| 26 | Cerveau et mains | Retenir : orchestration, exécution cadrée, review indépendante. |

Voir [MODELS](MODELS.md) et [OPTIONAL_TOOLS](OPTIONAL_TOOLS.md).
Le chargement hiérarchique d’instructions permet des règles de sous-dossier,
mais les règles racine doivent rester compatibles : [AGENTS.md Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Gate avant longue exécution

- [ ] décisions et contraintes accessibles, contexte historique résumé
- [ ] sorties déléguées exploitables et preuves localisables
- [ ] chemins, phase, blockers et prochaines actions dans le checkpoint
- [ ] aucune hypothèse de quota présentée comme mesure
