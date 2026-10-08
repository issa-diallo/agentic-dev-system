# Verify — <story>

## Status

`VERIFY: IN_PROGRESS | PASS | BLOCKED`

## Principle

Ne pas déclarer que cela fonctionne. Le prouver.

## Acceptance criteria evidence

| Criterion | Evidence | Result |
|---|---|---|
| AC1 | … | PASS/FAIL |

## Automated checks

| Command | Result | Evidence |
|---|---|---|
| … | PASS/FAIL | … |

## Runtime verification

### UI
- browser flow :
- screenshot :
- responsive :
- accessibility :

### API / backend
- request :
- response :
- error cases :
- logs :

## Regression checks

- …

## Performance / security when relevant

- …

## Verify Gate

- [ ] chaque critère d'acceptation a une preuve
- [ ] tests pertinents PASS
- [ ] comportement réel vérifié
- [ ] aucune affirmation non prouvée

Verdict : PASS / BLOCKED

## Reproductibilité et limites

- date, branche/commit, environnement, versions et données de test :
- sortie brute / preuve consultable et commande exacte :
- non exécuté ou non applicable, avec raison :
- taille/contexte/durée mesurés, baseline comparable et méthode :
- tokens/coût/quota : valeur observée ou non observable :

Un contrôle statique de liens ou présence ne démontre pas l’obéissance d’un
modèle aux instructions. Séparer compatibilité déclarée et comportement testé.
