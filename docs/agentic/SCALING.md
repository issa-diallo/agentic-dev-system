# Échelles de la méthode

`PREPARE → BUILD → SHIP` dans tous les modes. Choisir selon le risque, pas la
taille du dépôt. La profondeur change ; sécurité, Verify, review indépendante,
CI, contrôle du périmètre et autorisation de merge restent obligatoires.

| Mode | Usage | PREPARE | BUILD / SHIP |
|---|---|---|---|
| LIGHT | correction ciblée, prototype, capacité simple à faible risque | six rubriques minimales dans un fichier, références/N/A motivés | plan et PR_SPLIT compacts ; tests adaptés ; review indépendante avec profil Lead Tech |
| STANDARD | application, évolution courante | six rubriques concises, décisions existantes réutilisées | worktree/owner par PR non triviale, environnement reproductible selon besoin ; preuves et review indépendante avec profil Lead Tech |
| LARGE | production critique, données sensibles, migrations risquées, contrats complexes | six rubriques structurées, ADR ciblés, DAG et risques détaillés | isolation/ressources explicites, goal mesurable, observabilité/rollback, review forte puis seconde lecture Lead Tech distincte |

Six rubriques ne signifie pas six gros fichiers : PRD, TRD, APP_FLOW,
UX_UI_BRIEF, BACKEND_SCHEMA, IMPLEMENTATION_PLAN peuvent tenir dans
[PREPARE](templates/PREPARE.md) et référencer le socle validé.
Sur existant, compléter le delta utile ; aucun Research/Design/Plan supplémentaire
par tâche. Les templates V1 sont conservés pour reprise/legacy, facultatifs.

PR_SPLIT avant tout BUILD non trivial, même LIGHT : une capacité autonome par PR,
AC/tests/fichiers/contrats, branche/worktree et owner. Ne pas multiplier agents ou
documents pour une tâche simple ; lancer réellement toute délégation annoncée.
Un risque critique exige une seconde lecture indépendante même hors mode LARGE.

Choisir LARGE lorsque perte/exposition de données, production critique, rollback
difficile, auth/paiement/migration ou conflits de ressources nécessitent des
protections renforcées. Plusieurs agents augmentent les besoins d'isolation ;
leur nombre seul n'impose pas six dossiers documentaires.

Architecture fixe une direction courte. Aucun benchmark, prototype ni coût chiffré
requis au gate ; validations différées avec responsable/échéance dans le plan et
preuves en BUILD/Verify. Ne jamais économiser au prix d'un gate, d'un test ou d'une
protection. Les coûts non exposés par le runtime restent null/non observables.
