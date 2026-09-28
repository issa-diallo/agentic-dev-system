# Context Hygiene

## Objectif

Garder le contexte principal utile et réduire le bruit.

## Règles

- le main agent garde les décisions et contraintes ;
- déléguer les explorations lourdes à des sub-agents ;
- demander aux sub-agents un résumé exploitable, pas un dump ;
- ne pas charger des skills/MCP/plugins inutiles ;
- ne pas créer de documentation artificielle uniquement pour nourrir l'IA ;
- préférer lire le code réel quand une information peut changer ;
- résumer les longues investigations avant Execute ;
- conserver dans le contexte principal : objectif, contraintes, décisions, blockers, evidence.

## Pattern recommandé

```text
Main agent
   |
   +--> Research sub-agent
   |       |
   |       +--> concise findings
   |
   +--> Security sub-agent
   |       |
   |       +--> risks/findings
   |
   +--> Main agent keeps only actionable context
```

## Gate

Avant une longue phase Execute :
- [ ] contexte principal nettoyé
- [ ] décisions clés accessibles
- [ ] bruit historique non nécessaire écarté
- [ ] résultats des sub-agents résumés
