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
