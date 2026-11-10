# Cycle de revue corrective borné

Option désactivée par défaut, exige `run.missions.enabled: true` et
`run.subscription_only: true` :

```json
"review_cycle": {
  "enabled": true,
  "max_attempts": 7,
  "max_corrections": 2,
  "max_cost_rank": 3,
  "prefer_cross_provider": true,
  "justification": "Un second fournisseur aide à confronter ce contrat"
}
```

Les bornes sont explicites : `max_attempts` compte les tentatives de lancement de
la PR (analyses et tests compris), `max_corrections` les retours à l'implémentation,
`max_cost_rank` plafonne le rang relatif déclaré des modèles, sans représenter un
prix ni un quota. Elles persistent après `requeue` et les succès intermédiaires.
Aucun retry automatique, aucun fallback après épuisement du quota. Les tentatives
d’escalade du routeur utilisent `--task-id <PR>:<role>` dans ce cycle : une erreur
implementer n’escalade pas le reviewer. Un historique hérité au seul ID de PR
bloque et exige une réconciliation explicite, sans effacement des preuves.

Déclarer `provider` sur les modèles pour activer la préférence entre fournisseurs.
Cette provenance reste **déclarative**, distincte du modèle observé par le CLI.
Le routeur cherche une alternative capable et permise par la politique, dans le
budget ; override strict, niveau/effort et indépendance restent prioritaires.
Alternative absente ou fournisseur auteur inconnu : choix initial conservé avec
raison dans `model_routing.review_selection`. Cela ne constitue jamais une
autorisation de changer de fournisseur après une erreur ou un quota épuisé.

`review_identity` lie auteur et reviewer aux identités runtime, sessions CLI et
modèles observés disponibles, au SHA, snapshot et hash de plan. Les valeurs non
exposées restent null. Un même modèle/fournisseur dans deux sessions distinctes
reste valable ; un fournisseur différent ne prouve pas l'indépendance.

Une revue bloquante s'arrête. L'orchestrateur utilise explicitement
`Scheduler.request_correction(pr, evidence)` avec la même configuration/contexte
que le runner. `evidence` reprend les preuves `requeue` (arrêt/identité confirmés,
plan, snapshot, raison/preuve et `orchestrator_verified`) et fournit `head`,
`diagnosis_kind` (`implementation` ou `capacity`) et un `diagnosis` concret.
Le contrôleur transmet les findings exacts à l'implementer, conserve les tests
verrouillés et l'historique, invalide Verify/revue et réclame deux lancements
restants au budget. Après correction, `delegate` exécute Verify puis une nouvelle
revue indépendante. `routing_override` optionnel exige un diagnostic `capacity`,
une politique de routage active et un modèle/effort admissible dans le budget ;
aucune escalade de modèle ou d'effort n'est automatique.

Une nouvelle révision commitée peut être réconciliée explicitement par cette API :
le diff et Verify gardent la base PR initiale, le nouveau HEAD est verrouillé
pendant la mission. Changement du plan/configuration ou des tests protégés :
BLOCKED. Si une double analyse est active, changer son HEAD exige une préparation
et une analyse renouvelées ; cette API ne réhabilite pas l'ancien consensus.

Claude reviewer utilise, seulement dans ce cycle, le preset officiel non modifié,
sans outils intégrés/MCP, hooks ou contexte automatique, avec les restrictions
existantes de l'analyse. Diff, sources UTF-8 régulières du périmètre et Verify
sont fournis inline. Les chemins ignorés non suivis, même absents, sont refusés
avant lecture : le snapshot Git ne lie pas leur contenu. Les fichiers suivis
restent admissibles même si un pattern ignore correspond ; les nouvelles sources
non ignorées et les suppressions restent représentées dans le contexte/diff. Le contexte est limité à 100 000 octets et bloque si trop
grand, sans troncature. Codex conserve sa sandbox read-only. Ces protections
reposent sur le CLI officiel de confiance, sans sandbox OS supplémentaire.
Le flux prépare SHIP uniquement : review/Lead Tech selon le risque, PR_SCOPE, CI
et autorisation humaine du merge restent obligatoires.
