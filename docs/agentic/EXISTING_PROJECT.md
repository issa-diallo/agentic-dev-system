# Projet existant — démarrer depuis un ticket

Pour une installation personnelle non versionnée, utiliser `install-agentic.sh --local`
et suivre [LOCAL.md](LOCAL.md). Pour une installation partageable sans documents
produit, utiliser `--existing`. Voir [INSTALL.md](INSTALL.md).

## Quand utiliser cette entrée

Un dépôt existant peut traiter un ticket cadré sans reconstituer PRD, Stories,
Story Review, Architecture et Design System. L’absence de ces documents ne
bloque pas à elle seule. Une information indispensable manquante bloque.

Cette entrée ne s’applique pas à un nouveau produit ou à un gros périmètre,
même dans un dépôt existant : utiliser alors le pipeline produit complet.
Choisir séparément LIGHT, STANDARD ou LARGE selon le risque (SCALING.md).

## 1. Cadrer le ticket

Exiger un identifiant, un problème ou objectif, un périmètre et des critères
d’acceptation vérifiables. Pour un bug : comportement observé et attendu,
avec reproduction lorsque possible. Identifier les dépendances connues.
Si ces éléments manquent, compléter le ticket avant de poursuivre.

## 2. Entrer à Research

Lire les documents disponibles, puis inspecter le code, la configuration,
les tests et les composants concernés. Un template vide n’est pas une source
validée. Ne pas remplir artificiellement les cinq documents produit.

Dans `docs/agentic/work/<story>/research.md`, consigner :

- entrée EXISTING et justification du non-recours aux phases produit ;
- référence du ticket, critères d’acceptation et mode choisi ;
- documents disponibles, absents ou contradictoires ;
- architecture et stack observées, avec chemins de fichiers à l’appui ;
- conventions, contrats, données et composants UI utiles au ticket ;
- dépendances, zones impactées, tests et risques de régression ;
- authentification, autorisation, isolation tenant, données sensibles, secrets
  et actions externes concernés, ou non-applicabilité justifiée ;
- inconnues et blockers, stratégie de vérification et rollback si pertinent.

Ne pas inventer les raisons historiques des choix techniques. Distinguer les
faits observés des hypothèses ; résoudre les contradictions qui touchent le ticket.
Le socle observé suffit pour vérifier la compatibilité architecture/ADR lorsque
la documentation d’architecture manque et qu’aucun changement structurant n’est prévu.

## 3. Continuer le pipeline par story

`Research → Design → Plan → Worktree Setup si requis → Execute → Verify → Review → Goal si applicable → Ship`

Research, Design et Plan doivent être PASS avant Execute. Conserver la Definition
of Ready, l’isolation des stories non triviales, les preuves de Verify, la review
indépendante et les exigences CI/Ship. Pour une interface, réutiliser les conventions
et composants observés ; sans impact UI, justifier que le Design System est hors
périmètre. Le Design de story reste requis pour les comportements ou contrats.

## 4. Quand revenir au cadrage produit ou à Architecture

- Besoin ambigu : préciser le ticket ; si le périmètre devient important,
  reprendre PRD → Stories → Story Review → Architecture → Design System.
- Changement structurant (stack, auth, données, contrats majeurs, etc.) :
  marquer la story BLOCKED, créer ou mettre à jour l’ADR et ARCHITECTURE.md,
  faire valider la décision, puis réviser Research/Design/Plan avant Execute.
- Risque critique non traité : rester BLOCKED, même si la documentation existe.

## Statuts et contrôle

Dans STATUS.md, renseigner l’entrée EXISTING et la référence du Research de
chaque ticket concerné. Les phases produit non parcourues ne deviennent pas PASS :
indiquer « hors périmètre de ce ticket » dans Research. Ne pas modifier les statuts
produit globaux pour simuler leur validation.

Exécuter `bash scripts/agentic-check.sh --existing` pour le contrôle de présence
du socle. Sans option, le script exige les cinq documents produit. Ce contrôle
ne valide ni leur contenu, ni les gates, ni la Definition of Ready.

L’installateur peut avoir créé des templates produit vides : leur présence
n’oblige pas à les remplir pour cette entrée et ne prouve aucun PASS.

## Prompt de démarrage

> Applique AGENTS.md et docs/agentic/EXISTING_PROJECT.md au ticket <identifiant>.
> Le projet existe déjà et sa documentation produit peut être absente.
> Choisis le mode selon le risque, vérifie le cadrage du ticket et commence par
> Research sur le code réel. Documente les faits et inconnues utiles au ticket.
> Ne reconstitue pas un PRD global et ne change pas silencieusement l’architecture.
> Passe par Design, Plan, Execute, Verify et une Review indépendante ; respecte
> les gates, l’isolation et Ship. Si le périmètre exige le pipeline produit,
> explique pourquoi et reprends ce pipeline.
