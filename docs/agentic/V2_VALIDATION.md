# Validation du pilote V2

Le pilote valide les contrôles locaux A–H et observe deux implémentations natives
isolées. Il ne valide pas SHIP : CI distante, fusion des parents, examen final
Lead Tech de la migration et autorisation de merge restent des preuves séparées.
Ce rapport décrit des observations du 12 octobre 2026, pas une garantie sur tous
les modèles ou tous les hôtes Codex.

## Périmètre et provenance

Mission LARGE, dépôt existant, ticket #29, unité V2-PR09. PREPARE/PR_SPLIT et
délégation autorisent uniquement ce rapport et `tests/test_v2_pilot.py`
dans le dépôt source. Les tests utilisent Bash,
Git et Python stdlib ; toutes leurs installations et mutations Git se font dans
des fixtures temporaires. Leurs callbacks runtime, identités de reviewer et
attestations CI sont **simulés**. Ils exercent les scripts réellement installés,
pas un remplacement de leurs contrôles. Aucun appel de modèle dans ces tests.

Le socle testé avant PR09 est `bf4255ad81824ce4340d93620724d23a544f18ce` :
177 tests PASS en 48,434 s et reviews indépendantes observées. Ces résultats ne
prouvent ni CI distante ni fusion des parents. Les mesures et reçus personnels
restent exclus de Git dans `.agentic-local/v2/` chez l'orchestrateur :
`audit.md`, `pilot.json`, `benchmark.json`, `controlled-benchmark.json`,
`native-probe.json`, `pilot-skills-context.json`, `pilot-model-routes.json`,
`pilot-defect.json`, `pilot-resume-1.json`, `pilot-resume-2.json`,
`pilot-resume-after-upgrade.json` et les reçus `PILOT-*-*.json`.
Ce rapport constitue leur synthèse distribuable ; leur présence n'est pas un PASS.

L'audit V1 conserve gates, exclusions, garde staged, décisions et review
indépendante ; il regroupe la préparation dans six rubriques, puis ajoute les
contrôles d'attribution, ressources, routage et reprise. ECC a fourni des concepts
de chargement ciblé, DAG, impact et vérification ; aucun code ECC n'a été copié.
Source auditée : commit `b92f181b3b748d1abbc2afd94af6aa7d8c8fca29` du dépôt
[ECC](https://github.com/affaan-m/ECC/tree/b92f181b3b748d1abbc2afd94af6aa7d8c8fca29).
Une copie future doit conserver sa licence MIT et l'attribution ©2026 Affaan Mustafa.

## Scénarios A–H

| Scénario | Preuve exécutée | Verdict et portée |
|---|---|---|
| A — mauvais découpage | Deux capacités séparables regroupées : BUILD/scheduler refuse avant callback, sans réservation ni changement Git | PASS du contrôle ; Execute reste BLOCKED |
| B — deux unités indépendantes | Installation réelle, deux branches/worktrees, owners distincts, fichiers et ressources API logiques disjoints ; deux lancements avant collecte dans l'adaptateur simulé | PASS de l'intégration ; preuve native complémentaire ci-dessous |
| C — contexte ciblé API/SQL/React | Sélection puis lecture explicite du seul skill pertinent distribué ; hash et octets confrontés au fichier | PASS ; loaded ne vaut pas applied |
| D — LOW/MEDIUM/HIGH et escalade | Inventaire synthétique, routage déterministe ; échec de capacité explicitement synthétique ; requested présent et observed null au reçu | PASS de la politique ; aucune montée de modèle native démontrée |
| E — défaut puis correction | Unittest réel échoue ; handoff BLOCKED ; correction commitée, nouveaux tests PASS, requeue avec historique ; self-review et preuve de tête obsolète refusées | PASS ; review/CI des tests sont des attestations simulées |
| F — installation sans perte | Installation LOCAL dans worktree lié avec index staged, règles d'équipe et fichiers personnels ; index binaire, contenus, status et liste des worktrees conservés | PASS ; migration manuelle supplémentaire ci-dessous |
| G — interruption/reprise | État persisté, commits Git réels, même identité/owner après deux reprises, aucun nouveau lancement ; hors-scope préservé et BLOCKED sans libération avant arrêt | PASS ; deux reprises natives également observées |
| H — mesure honnête | Octets chargés confrontés aux fichiers, temps local mesuré, tokens/coûts/quota null ; trois paires contrôlées V1/V2 distinctes du warmup natif | PASS de la méthode de mesure ; aucun gain causal revendiqué |

Dans B, les réservations API sont des identifiants logiques ; aucun service, port,
conteneur ou base de données n'est démarré. COMPLETED n'est jamais assimilé à
review, acceptation, CI ou autorisation de livraison. E exerce réellement
`quality.run_checks`, `quality.assess`, requeue et acceptation sur les mêmes
worktrees ; la fixture CI existe seulement pour vérifier le contrat d'assessment.
La preuve manuelle `pilot-defect.json` confirme aussi un retour de test 1/BLOCKED
puis 0/PASS avec un nouveau hash de contenu, sans mutation de production.

## Exécution native observée et limites des profils

L'orchestrateur a réellement lancé `/root/pilot_v2_labels` et
`/root/pilot_v2_csv` via `collaboration.spawn_agent`. Il a validé les reçus avant
GO, puis constaté deux implémentations indépendantes en parallèle :

| Unité native | Tête Git observée | Diff | Tests repris indépendamment |
|---|---|---|---|
| labels | `c3e814a73ff519aa4e9998c6558b0ba0caed7214` | 2 fichiers, 55 lignes | 4 PASS |
| csv | `bfc1c48cdd10470bdd3795baf0591aef1058b6f1` | 2 fichiers, 55 lignes | 6 PASS |

Le root a examiné chaque diff et relancé les tests : review indépendante PASS,
handoffs COMPLETED et acceptations PASS. Deux reprises ont conservé les mêmes
IDs, têtes et acceptations sans relancer de délégation. Deux exécutions ont été
observées, aucun conflit et aucune intervention métier humaine dans ces fixtures.
Les demandes étaient `gpt-6.1-sol`/`medium` ; l'observation du modèle effectif reste
null. Ni le nom du sous-agent ni un modèle demandé ne prouve le modèle exécuté.

Les agents ont reçu et lu le skill distribué de vérification, hash
`f328c82a570b5706346690b9028d3a7bf7c57d70edb6b5a8f2eeb41c54651a01`.
L'application est étayée par les tests sur critères et les diffs effectivement
examinés par le root, avec E2E N/A motivé pour ces bibliothèques hors ligne et
absence de self-review. Pour C, seuls selected et loaded sont établis : API
552 octets, SQL 561, React 474. Aucun applied supplémentaire n'est inventé.

Le probe CLI Codex 0.162.1 distingue trois faits :

- Les fichiers de profils et leur configuration passent le parsing observé.
- L'outil `collaboration.spawn_agent` exposé ne propose pas de sélecteur de rôle
  personnalisé. Un nom « explorer » ou « reviewer » ne charge pas ce profil.
- Le probe CLI n'a lancé aucun enfant personnalisé. La tentative read-only a
  rencontré `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`.

Le fonctionnement des profils personnalisés reste donc **limité/non démontré**
sur cet hôte. Le lancement natif des deux unités ci-dessus est établi séparément.
Le probe rapporte 182420 tokens d'entrée, dont 152320 en cache, 1166 de sortie et
167 de raisonnement. Ce périmètre est le tour CLI principal du probe ; les tokens
en cache sont inclus dans l'entrée. Aucun coût API, quota Codex, total de migration
ou usage d'enfant n'en est déduit. Responsable de la vérification restante :
orchestrateur, au prochain hôte disposant du sélecteur et du sandbox nécessaires.

## Conservation de l'installation et de la reprise

Le pilote natif avait installé la source `1a7d8052c8b314f72a1b589fe104785de2a42393`.
L'orchestrateur a ensuite migré manuellement ses trois fixtures vers `bf4255a` :
sauvegarde intégrale de chaque `.agentic-local` conservée, nouvelle installation,
puis restauration du seul dossier de mission `v2-pilot` identique. Les registres
Git communs sont restés intacts. `FORCE` a été volontairement refusé : il n'existe
pas de mise à jour automatique écrasant les personnalisations.

Les sauvegardes `backups/{project,labels,csv}` restent disponibles pour rollback,
y compris les notes personnelles. `pilot-resume-after-upgrade.json` constate les deux
unités COMPLETED/accepted true, mêmes IDs/têtes/hashes, trois status Git propres
et aucun fichier interne suivi. Cette preuve porte sur une migration manuelle
avec sauvegarde de fixtures V2 ; elle ne démontre pas un upgrade automatique V1.

## Comparaison mesurée H

Le warmup natif V1 utilisait `39adf261fcbf13431e56b62694455706958342da` :
`/root/baseline_labels` et `/root/baseline_csv`, 2 fichiers par PR, respectivement
50/47 lignes et 6/4 tests PASS, reviews réelles du root. Ces tâches ont été
sérialisées parce que la migration occupait les slots runtime ; le pilote V2
était parallèle, avec des contenus différents. Les deux observations ne permettent
aucune comparaison causale de vitesse, coût ou qualité des développeurs agents.

La mesure contrôlée utilise V1 `39adf26` et V2 `bf4255a` sur le même hôte : trois
paires en ordre alterné, contenus identiques vérifiés par SHA-256, mêmes critères,
10 tests et deux PR de 2 fichiers/55 lignes par essai. Les contenus sont semés
déterministement à partir du pilote natif déjà relu ; aucun agent frais n'est
chronométré. Les reçus scheduler V2 sont explicitement simulés.

| Essai apparié | Préparation fixture V1 / V2 (s) | Total local vérifié V1 / V2 (s) |
|---|---|---|
| 1 : V1 puis V2 | 0,857 / 2,183 | 1,562 / 4,778 |
| 2 : V2 puis V1 | 0,576 / 1,433 | 1,114 / 2,989 |
| 3 : V1 puis V2 | 0,556 / 0,968 | 1,259 / 2,393 |

Douze PR fixtures ont PR_SCOPE PASS ; chaque essai a 10 tests PASS, zéro conflit,
une tentative de fixture, zéro défaut et zéro intervention humaine pendant
l'essai. Ces compteurs excluent la définition antérieure du benchmark et le
travail natif ayant produit les contenus. La préparation mesure l'installation
et les fixtures, pas le cadrage produit. Le total couvre les contrôles locaux,
pas CI distante, publication ou merge. V2 ajoute runner, snapshots et reprises :
le surcoût observé n'est pas une économie. Échantillon local court ; tokens,
coût API et quota sont null, aucun gain d'ingénierie n'est démontré.

## Reproduction et gate de cette PR

Depuis le dépôt source : les tests contributeur ne sont pas copiés par
l'installation de la méthode dans un projet cible.

```bash
python3 -B -m unittest discover -s tests -p test_v2_pilot.py -v
python3 -B -m unittest discover -s tests -v
git diff --check
```

Le premier contrôle a passé les huit scénarios en 5,228 s ; la suite complète a
passé 185 tests en 55,091 s et `git diff --check` est PASS. Le contrôle des six
configurations d'installation passe après correction d'un lien vers un test
non distribué. Review indépendante, PR_SCOPE actualisé et CI de PR09 restent
à établir ; ce rapport ne les auto-valide pas. Les scripts sont coopératifs :
ils valident fraîcheur et cohérence des
attestations JSON, pas l'authentification runtime, une sandbox ou la classification
métier. La provenance et l'identité doivent être vérifiées par l'orchestrateur.
