# Configuration au premier lancement

Ce parcours est exécuté par l’orchestrateur **avant la première mission de
développement**, après lecture des règles de l’équipe. Il s’applique à LOCAL,
au dépôt source et aux installations partagées. Une consultation, une aide, une
lecture de statut ou le message exact `agentic ?` ne déclenche aucune question,
connexion, installation ni inférence. Le diagnostic `agentic ?` reste inchangé.

Le questionnaire se déroule dans la conversation du client. Ne pas lancer de
questionnaire dans le terminal d’un outil ou d’un agent enfant. Les valeurs
recommandées restent des propositions : attendre une réponse explicite.

## Vérifier l’état local

Résoudre la racine Git du projet et le socle de méthode réellement chargé.
Dans les commandes ci-dessous, `<socle>` désigne ce socle, `<projet>` la racine
applicative. Les remplacer par les chemins réels, sans les exécuter littéralement.

```bash
python3 <socle>/scripts/agentic-onboard.py status --repo <projet>
```

Conserver le chemin absolu `config` renvoyé. `--config <configuration>` ou
`AGENTIC_CONFIG` sont prioritaires ; une configuration existante à la racine
reste réutilisable. Sans configuration, le chemin est
`<projet>/.agentic-local/agentic.config.json`, y compris en installation partagée.
Le script ne lit pas les identifiants de connexion lors de `status`.

Si `onboarding_required` vaut `false`, reprendre directement la mission avec
cette configuration. Cet état prouve la configuration et les essais passés,
pas une connexion ou un quota encore valides : le runner les revérifie au
lancement. Un changement du contenu configuré invalide l’état de premier lancement.

## Questions dans la conversation

1. **Codex.** Annoncer sa détection puis vérifier la connexion suivant le
   [guide multi-modèles](MULTI_MODEL_GUIDE.md). Si absent ou déconnecté,
   accompagner l’installation ou `codex login` ; la connexion au compte est
   réalisée par l’utilisateur. Ne pas présenter la présence du binaire ou le
   login comme un test d’accès au modèle.
2. **Deuxième moteur.** Demander : « Voulez-vous ajouter Claude Code ? Oui / Non. »
   Si oui, réutiliser une installation et une connexion existantes ; sinon
   suivre l’installation et `claude auth login` du même guide. Ce choix autorise
   l’accompagnement correspondant sans redemander l’accord à chaque commande.
   Une interaction navigateur peut nécessiter l’utilisateur. Si non, conserver
   Codex seul. Une ancienne configuration qui route encore vers Claude doit
   être réconciliée explicitement, jamais écrasée pour masquer la contradiction.
3. **Revues.** Demander : « Voulez-vous activer les revues avec corrections
   automatiques ? Oui recommandé / Non. » Sans réponse, ne rien activer.
   Un refus désactive cette boucle optionnelle ; la revue indépendante exigée
   par la méthode reste obligatoire. Deux sessions Codex distinctes peuvent
   remplir les rôles auteur/reviewer si Claude n’est pas choisi.
4. **Limites, si la boucle est acceptée.** Proposer les limites existantes,
   sinon « Sept lancements et deux retours en correction maximum par PR.
   Conserver ces limites ? Oui / Personnaliser. » Expliquer qu’un lancement
   compte chaque tentative d’agent, analyses/tests et tentatives échouées compris ;
   un retour en correction est une reprise par l’implementer après une revue
   bloquante, suivie de Verify puis d’une nouvelle revue. Les deux limites
   s’appliquent ensemble. Exemple sans analyse supplémentaire : tests,
   développement, revue, correction, revue, correction, revue = sept lancements.
   On termine plus tôt si tout passe ; budget épuisé et problème restant =
   arrêt expliqué, jamais validation automatique. Au moins trois lancements
   sont nécessaires au parcours initial ; les corrections personnalisées
   peuvent nécessiter un budget supérieur pour être toutes possibles.

## Réutiliser les modèles connus

Réutiliser les modèles et leurs métadonnées renvoyés par `status`. Si des
informations manquent, relever le modèle effectivement choisi dans le runtime
ou les configurations CLI autorisées, puis demander seulement la confirmation
nécessaire : identifiant CLI accessible, capacité déclarée, efforts autorisés et
rang relatif. Ne pas imprimer les fichiers de compte ni leurs secrets.

Un nom de modèle ou une réponse correcte au smoke test ne prouve jamais une
capacité HIGH. La capacité et les efforts restent des déclarations d’inventaire
suivant [MODELS](MODELS.md), avec reviewer/Lead Tech au minimum HIGH. Le preset
Claude ne transmet pas d’effort explicite ; ne pas ajouter une règle qui l’exige.
Le `cost_rank` est un ordre relatif déclaré, sans prix ni quota inventé.

Préparer un fichier de réponses temporaire dans le dossier Git commun, hors
du diff. Deux booléens sont obligatoires :

```json
{"claude": false, "reviews": true, "max_attempts": 7, "max_corrections": 2}
```

Ce payload réutilise l’inventaire existant. Pour une configuration neuve ou des
métadonnées explicitement confirmées, ajouter `models`, avec pour chaque entrée :
`id`, `harness` (`codex` ou `claude`), `provider` (`openai` ou `anthropic`),
`model` (identifiant CLI réel), `max_level` ou `tiers`, `efforts` et `cost_rank`.
Aucun modèle fictif de template ne doit être copié. Les entrées portant le même
`id` sont complétées seulement avec les champs explicitement fournis ; les autres
réglages sont conservés. Omettre les limites si l’utilisateur conserve celles
déjà enregistrées. Ne jamais transformer une absence de réponse en consentement.

## Tester puis mémoriser

```bash
python3 <socle>/scripts/agentic-onboard.py configure --repo <projet> \
  --config <configuration> --answers <réponses-locales.json>
```

Le script vérifie les modèles, le routage réel des rôles et le budget relatif,
puis les contrôles d’abonnement existants. Il lance un essai par modèle retenu
dans un dépôt Git temporaire sans sources applicatives : Codex en lecture seule,
Claude avec le preset isolé sans outils/MCP. Ce sont de vrais appels modèles
sur l’abonnement ; timeout, quota, CLI incompatible ou réponse inattendue bloquent
sans retry ni changement de moteur. Les restrictions Claude du guide, notamment
la vérification du plan personnel et des politiques managed, restent applicables.
Les essais exigent les groupes de processus POSIX pour arrêter le CLI et ses
enfants avant de rendre la main, y compris après timeout ou interruption.

La réussite d’un essai prouve une réponse accessible, pas la capacité déclarée,
le quota restant ou l’absence de dépassement payant. Les journaux bruts et les
identités de compte ne sont pas conservés. Les réglages existants de double
analyse, de routage et les limites sont préservés ; un conflit exige une décision
explicite. Les réglages incompatibles d’authentification ou de harnais ne sont
jamais réécrits automatiquement.
Un mode TDD déjà activé est incompatible avec cette boucle dans `quick` :
le conserver avec la boucle désactivée, ou résoudre explicitement ce choix
avant de relancer la configuration. L’assistant ne désactive pas le TDD à votre place.

Seulement après succès, une exclusion Git locale ciblée est ajoutée si nécessaire,
puis la configuration privée est écrite atomiquement. Aucun fichier déjà suivi
ni lien symbolique n’est remplacé. Une modification concurrente détectée bloque
sans écraser le nouveau contenu. En cas d’échec, conserver le fichier précédent,
expliquer la cause et laisser le premier lancement en attente ; ne pas déclarer
les revues activées. Le script n’installe rien et ne lance aucune connexion.

Afficher un récapitulatif court : moteurs retenus, essais réussis, boucle de
revue activée ou refusée, limites, chemin de configuration. Après succès,
reprendre la mission initiale sans demander de relancer un skill. Aucun PASS
PREPARE/BUILD/SHIP ni autorisation de merge ne découle de cet onboarding.

## Utiliser les choix et les modifier

Conserver `--config <configuration>` sur **chaque** commande ultérieure de
`agentic-run.py`, notamment `inventory`, `delegate`, `quick`, `attempt` et toute
reprise. Pour les corrections, charger ce même fichier dans l’API scheduler.
Ne pas retomber sur le template ou le chemin par défaut du runner : en
installation partagée/source, il ne découvre pas seul ce nouveau chemin privé.

```bash
python3 <socle>/scripts/agentic-run.py inventory --repo <projet> --config <configuration>
```

Une demande « reconfigurer Agentic » rouvre les seules questions concernées,
en proposant les valeurs sauvegardées. Réexécuter `status` avec le même chemin,
puis `configure --reconfigure --repo <projet> --config <configuration>
--answers <réponses-locales.json>`. Une configuration déjà complète refuse
`configure` sans cette option et ne refait aucun essai. Garder une copie privée
de l’ancienne configuration avant une modification volontaire si une restauration
ultérieure est souhaitée ; ne jamais supprimer le fichier pour contourner un échec.
