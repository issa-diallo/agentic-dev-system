# Workflow canonique

`PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Worktree Setup -> Execute -> Verify -> Review -> Goal -> Ship`

## 0. Choisir le mode

Lire `SCALING.md` et sélectionner :
- LIGHT
- STANDARD
- LARGE

Le mode détermine la profondeur, pas la qualité minimale.

## Entrée projet existant

Pour un ticket cadré, suivre [EXISTING_PROJECT.md](EXISTING_PROJECT.md).
Les documents produit absents ou vides ne bloquent pas à eux seuls : consigner
le socle observé et la justification dans Research, puis suivre le pipeline par
story et ses gates. Ne pas marquer les phases produit PASS sans les avoir réalisées.
Nouveau produit ou gros périmètre : pipeline produit complet.

## Pipeline Produit

1. PRD
2. Stories
3. Story Review
4. Architecture
5. Design System

Toutes doivent être PASS avant les premières stories d'implémentation structurantes.
Architecture PASS signifie décisions suffisantes pour ces stories, avec
sécurité et contrats critiques résolus. Les choix réversibles ultérieurs
sont consignés avec une story/déclencheur et un responsable ; leur absence
ne bloque pas Design System. Une story dépendante reste BLOCKED jusqu'à
la résolution de sa décision, vérifiée dans Research/Design/Plan.

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
PR, CI, examen final selon le [profil Lead Tech](roles/REVIEWER.md), validation,
merge, cleanup. Respecter son déclenchement LIGHT/STANDARD/LARGE. Avant livraison,
le verdict et les preuves doivent porter sur la base et la tête actuelles de la PR.

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

Pour PRODUCT, après Architecture + Design System PASS. Pour EXISTING, après
Research PASS des stories concernées, avec socle observé compatible et contrats
stabilisés. Dans les deux cas, respecter les dépendances et isoler les worktrees :

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
- architecture compatible et aucune décision différée requise
  pour cette story encore ouverte ;
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

## États et isolation

États : BACKLOG, PRD, STORIES, STORY_REVIEW, ARCHITECTURE, DESIGN_SYSTEM,
RESEARCH, DESIGN, PLANNED, IMPLEMENTING, VERIFY, REVIEW, BLOCKED, PR_OPEN,
CI, READY_FOR_HUMAN, DONE. BLOCKED peut survenir partout.
Une mission limitée à ouvrir une PR reste READY_FOR_HUMAN après gates et CI ;
DONE exige merge et cleanup. Ne jamais merger sans autorisation applicable.
Story non triviale : identifiant, branche, worktree, implementer, reviewer
indépendant et PR dédiés. Convention `worktrees/<ticket>-<slug>` et branches
`feat/<ticket>-<slug>`, `fix/<ticket>-<slug>` ou `chore/<ticket>-<slug>` selon l’intention.
Deux agents ne modifient jamais le même worktree simultanément.
L’orchestrateur calcule les dépendances, commence par les stories structurantes,
évite les collisions et bloque la vague si une dépendance structurante échoue.
