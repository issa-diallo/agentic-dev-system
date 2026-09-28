# Scaling the Method

Le même système doit fonctionner pour un petit script comme pour un SaaS complexe.

## Principe

La méthode ne change pas :

`PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Execute -> Verify -> Review -> Ship`

Ce qui change est la profondeur des artefacts.

## Mode LIGHT

À utiliser pour :
- petit projet personnel ;
- prototype ;
- correction isolée ;
- feature à faible risque ;
- codebase simple.

Règles :
- PRD peut tenir sur une page ;
- Stories peut contenir quelques items ;
- Story Review peut être une checklist ;
- Architecture peut être un choix de stack succinct ;
- Design System peut être minimal ;
- Research + Design + Plan peuvent être courts mais doivent exister ;
- Verify reste obligatoire ;
- Review peut être légère mais indépendante pour les changements non triviaux.

Objectif : préparer suffisamment pour éviter les aller-retours sans ralentir le travail.

## Mode STANDARD

À utiliser par défaut.

Règles :
- artefacts complets ;
- architecture + ADR pour décisions structurantes ;
- worktree par story significative ;
- environnement reproductible ;
- goals mesurables quand utile ;
- evidence de vérification ;
- review indépendante ;
- CI avant Ship.

## Mode LARGE

À utiliser pour :
- SaaS multi-tenant ;
- plusieurs agents en parallèle ;
- données sensibles ;
- production critique ;
- migrations ;
- sécurité ;
- gros refactors ;
- intégrations nombreuses.

Règles supplémentaires :
- dependency map explicite ;
- ADR obligatoires pour les choix structurants ;
- worktree isolé par story ;
- scripts d'environnement ;
- goal mesurable ;
- evidence complète ;
- review indépendante forte ;
- checks CI de la méthode ;
- rollback ;
- observabilité ;
- sécurité et données revues explicitement.

## Sélection du mode

Choisir selon le risque, pas selon la taille du repo.

Questions :
- peut-on perdre des données ?
- peut-on exposer des données ?
- peut-on casser la production ?
- plusieurs agents vont-ils travailler en parallèle ?
- existe-t-il des dépendances entre stories ?
- le rollback est-il difficile ?
- la fonctionnalité touche-t-elle auth, paiement, sécurité ou multi-tenant ?

Si plusieurs réponses sont oui, utiliser STANDARD ou LARGE.

## Règle anti-bureaucratie

Un artefact court et précis vaut mieux qu'un document long et vague.

Le but de la préparation est de réduire :
- les décisions pendant Execute ;
- les tokens gaspillés ;
- les retours arrière ;
- les conflits entre agents ;
- les corrections après implémentation.
