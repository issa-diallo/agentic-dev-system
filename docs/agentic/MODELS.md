# Modèles et niveaux

Choisir le modèle disponible le moins coûteux capable selon tâche et risque.
LIGHT/STANDARD/LARGE règle la profondeur documentaire, pas le modèle.
L'inventaire et les overrides proviennent des capacités réellement exposées,
jamais de noms supposés ni d'une équivalence entre interfaces.

| Niveau | Travail | Validation |
|---|---|---|
| LOW | lecture/docs ciblées, mécanique à faible risque | contrôles déterministes |
| MEDIUM | implémentation cadrée, préparation locale | tests et review indépendante |
| HIGH | architecture, refactoring, review, complexité élevée | contrats et cas limites |
| EXTRA_HIGH | risque critique, auth/autorisation, sécurité, migrations | justification, mitigations et arrêt/escalade définis |

`agentic-models.py`, si disponible, recommande modèle/effort à partir de l'inventaire
fourni et des tentatives observées. Il ne modifie pas le modèle principal, ne
connaît pas les droits du compte et ne lance aucun agent. Les efforts portables
reconnus par ce routeur sont low/medium/high/xhigh ; Max/Ultra ne sont pas des
équivalences API présumées. Aucun nom de modèle imposé.

Dans IMPLEMENTATION_PLAN et le handoff : niveau requis, inventaire réel,
recommandation, modèle demandé, observation effective ou null, limite et validation.
Le runtime hôte applique seulement les overrides supportés lors d'un lancement réel.
Une recommandation n'est pas une application ; sans override, elle reste consultative.
Capacité insuffisante : BLOCKED et handoff exploitable, jamais faux PASS ou changement
fictif du modèle principal. Conserver les instructions utilisateur prioritaires.

Escalader sur preuve d'insuffisance de capacité : tâche, échec observé, diagnostic
concret, tentative et niveau. Une erreur d'implémentation ne justifie pas une relance
plus coûteuse sans analyse. Ne pas boucler après échec au niveau maximal.
Redescendre pour les tâches mécaniques lorsque l'incertitude est levée.

L'orchestrateur route aussi les skills depuis les racines autorisées disponibles,
charge uniquement les instructions retenues et transmet un contrat ciblé.
Distinguer selected, loaded, applied ; lire un skill ne prouve pas l'appliquer.
Les rôles Markdown ne créent aucun sous-agent. Utiliser les outils natifs réellement
exposés, conserver identifiant/reçu observé et vérifier le handoff ; sinon fallback
explicite et session indépendante pour Review. Aucun skill absent inventé.

Tokens, coût API, quota et durée restent null/non observables tant que le runtime
ne les expose pas ; un cost_rank relatif n'est ni prix ni économie démontrée.
Un cache ou une réduction d'octets ne prouve pas un gain de quota.

Lancement réel vers un modèle économique, brief et gates : [DELEGATION](DELEGATION.md).


## Politique déclarative optionnelle (recommandation)

`route(task, capabilities, attempts=None, policy=None)` conserve le routeur historique
sans politique. Le CLI `python3 scripts/agentic-models.py input.json` lit les champs
`task`, `capabilities`, `attempts` optionnel et `routing_policy` optionnel. Le template
`agentic.config.json` expose `routing_policy` désactivée par défaut. Pour utiliser
cette politique consultative, l'appelant transmet explicitement ce champ au routeur ;
le lanceur/scheduler historique n'active pas encore ce contrat. Le lancement et
l'attestation du modèle effectif relèvent du runtime, pas de cette recommandation.

```json
{
  "version": 1,
  "enabled": true,
  "rules": [
    {"id": "build-implementation", "match": {"role": "implementer", "phase": "BUILD"},
     "priority": 10, "prefer": [{"harness": "codex"}, {"harness": "claude"}],
     "minimum_level": "MEDIUM", "fallback": "blocked"}
  ]
}
```

Ce sont des préférences configurables, sans fournisseur supérieur présumé et sans
création d'agents permanents. `prefer` est une liste ordonnée de sélecteurs : chaque
objet contient exactement `model` (identifiant d'inventaire) ou `harness` (nom déclaré).
Le routeur choisit le moins coûteux capable dans le premier groupe admissible.
La deuxième préférence est un fallback autorisé et visible. `fallback: "least_cost"`
autorise explicitement le routeur historique si tous ces groupes sont impossibles ;
le défaut `"blocked"` refuse. Aucun appel réseau, login, clé ni API n'est nécessaire.
La politique n'autorise aucune voie de facturation ni contournement de la politique
`subscription_only` du lanceur : une recommandation n'est jamais une permission de lancer.

`task.role` est obligatoire lorsque la politique est active : `orchestrator`,
`explorer`, `test-author`, `implementer`, `reviewer`, `lead-tech`. `task.phase` est
`PREPARE`, `BUILD` ou `SHIP`. `risk` conserve les valeurs historiques : `low`,
`ordinary` (défaut), `high`, `critical`, `security_critical`. Les règles `match`
peuvent combiner ces trois dimensions, omises pour accepter toute valeur.
La plus grande `priority` entière gagne (défaut 0). Deux règles gagnantes bloquent ;
ni l'ordre ni la spécificité ne départagent implicitement. Sans règle correspondante,
le moins coûteux capable est conservé avec les contraintes de contexte actives.

Priorité : contraintes de sécurité/capacité/indépendance, puis
`task.routing_override: {"model": "id", "effort": "high"}`, puis règle, puis fallback
explicitement autorisé. L'override est strict, sans fallback ; il résout un conflit
de préférences. Le maximum des `minimum_level` des règles de priorité gagnante reste
un plancher, même avec override. Le niveau classifié, les escalades diagnostiquées et
le minimum HIGH des missions reviewer/lead-tech restent aussi des planchers.
`minimum_level` prend LOW/MEDIUM/HIGH/EXTRA_HIGH (défaut LOW). Un `effort` optionnel
dans une règle ou override impose exactement cet effort ; il doit être présent dans
l'inventaire et satisfaire le niveau requis. Les efforts portables restent ceux du
routeur historique. Effort inconnu/insuffisant, champ de politique inconnu, règle
malformée (même non applicable), contexte inconnu ou choix impossible : BLOCKED.
Une politique désactivée valide son schéma puis rend la sortie historique inchangée.

L'inventaire peut déclarer `harness`, `available` et `enabled` (booléens, défaut true),
`modalities` (liste de `text`, `image`, `audio`, `video`, défaut `["text"]`). Le routeur
filtre les modèles indisponibles/désactivés et exige toutes les modalités de
`task.modalities` (défaut `["text"]`). Aucune capacité multimodale n'est inférée d'un
nom. Pour reviewer/lead-tech, `task.session_id` et `task.implementer_session_id`
sont obligatoires, non vides et différents ; un même modèle dans deux sessions est
permis. L'appelant doit vérifier ces identités : les chaînes déclarées ne prouvent
pas l'indépendance du runtime.

La sortie active expose `policy.source`, `matched_rule`, `context`,
`attempted_preferences`, `preference_index` (base zéro) et `fallback_used`, ainsi
qu'une raison explicite. `applied` reste false, `observed` null et `verification`
`not_verified` : inventaire, modèles, efforts et sessions sont déclarés, jamais
annoncés observés/appliqués par cette fonction. Les coûts/quotas non exposés restent
null ; `cost_rank` est un ordre relatif non monétaire. L'historique des tentatives
continue de bloquer les relances non diagnostiquées, y compris avec override/fallback.
