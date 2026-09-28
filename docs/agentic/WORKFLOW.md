# Workflow canonique

`PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Worktree Setup -> Execute -> Verify -> Review -> Goal -> Ship`

## 0. Choisir le mode

Lire `SCALING.md` et sélectionner :
- LIGHT
- STANDARD
- LARGE

Le mode détermine la profondeur, pas la qualité minimale.

## Pipeline Produit

1. PRD
2. Stories
3. Story Review
4. Architecture
5. Design System

Toutes doivent être PASS avant les premières stories d'implémentation structurantes.

## Pipeline par Story

### Research
Comprendre le code réel.

### Design
Définir ce qui doit être construit.

### Plan
Décider comment l'intégrer avant de coder.

### Worktree Setup
Isoler l'exécution lorsque la story est significative ou risquée.

### Execute
Implémenter sans redécider le produit ni l'architecture.

### Verify
Prouver que le résultat fonctionne avec des evidence.

### Review
Agent indépendant, findings Critical/Major bloquants.

### Goal
Pour les tâches longues, continuer jusqu'à critères mesurables SATISFIED ou blocker réel.

### Ship
PR, CI, validation, merge, cleanup.

## Boucles

```text
Stories <------ Story Review

Architecture <--- Research/Plan
     si décision structurante invalide

Execute <------- Verify
Execute <------- Review

Goal FAIL ------> Execute/Verify

Ship -> CI FAIL -> Plan/Execute selon la cause
```

## Parallélisme

Après Architecture + Design System PASS :

```text
S01 Research -> Design -> Plan -> Worktree -> Execute -> Verify -> Review -> Ship
S02 Research -> Design -> Plan -> Worktree -> Execute -> Verify -> Review -> Ship
S03 Research -> Design -> Plan -> Worktree -> Execute -> Verify -> Review -> Ship
```

Ne paralléliser que lorsque les dépendances et contrats le permettent.

## Definition of Ready for Execute

Une story est Ready for Execute si :
- acceptance criteria clairs ;
- dépendances connues ;
- research PASS ;
- design PASS ;
- plan PASS ;
- architecture compatible ;
- fichiers/zones impactées identifiés ;
- stratégie de test définie ;
- risques critiques traités ;
- aucun blocker ouvert.

Si ce n'est pas vrai, ne pas coder.

## Definition of Done

- Execute PASS
- Verify PASS
- Review PASS/PASS_WITH_MINOR
- Goal SATISFIED si applicable
- CI PASS
- validation humaine si requise
- merge effectué
- cleanup effectué
