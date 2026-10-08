# Modèles et niveaux

Choisir le modèle disponible le moins coûteux capable, puis le niveau adapté au
risque. Le mode de projet LIGHT/STANDARD/LARGE décrit les artefacts ; il ne
sélectionne pas automatiquement un modèle. Aucun nom de modèle n’est imposé.

| Niveau recommandé | Travail | Validation / escalade |
|---|---|---|
| Light / Low | lecture ciblée, docs, corrections simples, tests répétitifs cadrés | diff et contrôle déterministe ; escalader si ambigu |
| Medium | research standard, plan local, implémentation bien cadrée | tests et review indépendante ; escalader après deux essais sans convergence |
| High | refactoring significatif, bugs complexes, PRD, review critique | contradictions et cas limites examinés |
| Extra High | architecture, décisions critiques, sécurité complexe, problème difficile non résolu | justification écrite et critère d’arrêt dans Plan |
| Ultra | mission complexe divisible qui bénéficie de plusieurs agents | contrats stables, budget observable, isolation et consolidation ; jamais par défaut |

Ce tableau exprime une politique, pas une équivalence entre libellés UI et valeurs
API `reasoning_effort`. Vérifier les options de la version, du modèle et du compte.
Ultra peut inclure de la délégation, avec consommation des sous-agents ; ce n’est
pas simplement « davantage de réflexion ». [Documentation des modèles](https://learn.chatgpt.com/docs/models).

Noter dans Plan : niveau recommandé, modèle/niveau réellement disponibles,
raison et validation attendue. L’agent ne prétend pas changer son propre modèle
si le harness ne le permet pas. Utiliser la capacité disponible et signaler la
limite ; si elle est insuffisante, bloquer avec un handoff exploitable. Ne jamais
inventer un pourcentage de quota ou promettre une économie.

Choisir avant une phase stable, éviter les changements incessants et redescendre
pour les tâches mécaniques une fois l’incertitude levée. Le cache API dépend des
préfixes identiques ; il ne prouve pas un gain de quota dans chaque client Codex.
[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

Les sous-agents reçoivent entrées, sorties, périmètre, outils, niveau et validation.
Leur création/configuration dépend des capacités exposées : les rôles Markdown
ne créent aucun agent automatiquement. [Sous-agents Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents).
