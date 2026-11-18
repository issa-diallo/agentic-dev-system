# Contexte, recherche et reprise

Le main agent garde objectif, contraintes, décisions, blockers et evidence.
Avant une longue tâche, déléguer les explorations lourdes si les outils natifs sont
disponibles, avec un contrat étroit et un lancement réellement observé ; sinon
consigner le fallback séquentiel sans annoncer de sous-agent lancé. Le
retour contient faits sourcés, chemins utiles, risques et décision attendue,
pas le journal complet. La politique de communication commune est définie dans
[AGENTS](../../AGENTS.md) et s'applique aussi aux retours des sous-agents.

## Portée de la communication concise

Le format conversationnel résume le livrable ; il ne remplace ni un artefact de
phase, ni un schéma de sortie demandé, ni les sections des templates. Conserver
les analyses, critères d'acceptation, diagnostics utiles, preuves, risques et
validations nécessaires dans les rapports techniques et documents métier.
Une réponse brève ne justifie jamais un livrable incomplet ou un PASS non prouvé.
Lier les fichiers accessibles ; si un extrait est indispensable au diagnostic,
limiter la citation à cet extrait sans exposer de secrets. Pour un test non lancé,
dire « non exécuté » et pourquoi ; un blocker ou une incertitude reste visible,
même si aucune modification n'a été faite. Adapter la longueur au besoin réel.

Cette politique retient la sobriété de Caveman et la réponse principale en tête
d'I Have ADHD sous forme de règles natives. Aucun de ces outils, dépôt, plugin,
MCP ou package n'est installé. L'héritage passe par les fichiers déjà copiés par
l'installateur ; le mode LOCAL garde son activation explicite.

## Recherche ciblée

Partir du ticket, du chemin fourni et de l’index de méthode. Utiliser `rg --files`
pour localiser puis `rg -n` dans les zones utiles et lire les passages concernés.
Élargir seulement si l’hypothèse échoue. Grouper les lectures indépendantes,
conserver chemins et conclusions dans PREPARE ou le checkpoint local ; ne pas relire systématiquement
le même fichier. Le code réel prime sur une carte obsolète. Une recherche vide
ou tronquée ne prouve pas l’absence : vérifier portée, exclusions et sortie brute.
Charger skills/MCP/plugins uniquement pour un besoin identifié. Ne pas créer de
documentation artificielle pour nourrir l’agent.

## Checkpoint et compaction

À une transition naturelle ou avant une reprise, remplir [HANDOFF](templates/HANDOFF.md) :
objectif/AC, phase et dernier PASS, décisions avec raisons, contraintes et refus,
fichiers et branche/worktree, commandes/résultats, erreurs encore ouvertes,
blockers, prochaines étapes et lectures ciblées. Distinguer fait et hypothèse.
Ne pas compacter tous les quelques messages ni imposer cinq questions : demander
seulement une information réellement manquante. Si une commande de compaction
existe dans le client, vérifier sa syntaxe ; le checkpoint fonctionne sans elle.
Après reprise, vérifier état Git, hash du plan, owner/ressources, identifiant runtime,
arrêt confirmé, artefacts et evidence avant l’étape suivante. Ne pas relancer un
agent ou libérer son owner sur un simple timeout/BLOCKED. Réutiliser les décisions
et preuves toujours valides ; un changement de contenu/SHA invalide les preuves
concernées. Les checkpoints/handoffs personnels restent locaux, exclus de Git.
Changer les préfixes peut modifier la réutilisation du cache ; aucune garantie
sur le quota Codex ne découle du [cache API](https://developers.openai.com/api/docs/guides/prompt-caching).

## Renouvellement automatique du contexte (opt-in)

Contrôleur facultatif `scripts/agentic-context.py` : il observe une mission qu'il a
lui-même créée, puis renouvelle sa session Codex au point sûr. Aucune activation par
l'installation ; sans requête explicite, le flux manuel (checkpoint puis lanceur) reste
inchangé. Une session existante n'est jamais adoptée sur la seule affirmation
`writers_stopped` : chaque génération, la zéro comprise, naît d'un terminal géré.

**Prérequis.** Linux, `systemd --user` (>= 250), cgroup v2, `gnome-terminal`, Codex
0.169.0, affichage graphique, abonnement (`run.subscription_only` de la configuration
de la requête est vérifié par `check_subscription` du runner avant toute inférence).
Sinon : BLOCKED avant tout lancement ni création d'unité ; seuls le journal du contrôleur,
son diagnostic et la réservation du worktree sont écrits (et peuvent changer).

**Requête JSON** : celle du lanceur `agentic-context-launch.py` (mêmes champs) plus
`mission_id`. `state` doit être privé, ignoré par Git,
sous le worktree. Un seul contrôleur par worktree : verrou canonique pendant un pas, et
réservation persistante `<git-common-dir>/agentic-context/*.claim` liée à mission, fichier
d'état et requête. Une autre mission est refusée avant tout lancement, après `step()` comme
après redémarrage ; une réservation sans fichier d'état n'est jamais écrasée. Elle n'est
libérée ni par timeout, ni par absence de PID, ni par la phase `completed` seule : après
fermeture confirmée de toutes les unités `agentic-ctx-*`, l'opérateur supprime le `.claim`.

**Commandes.**
```
python3 scripts/agentic-context.py run --request REQUETE.json [--once]
python3 scripts/agentic-context.py status --request REQUETE.json   # lecture seule
python3 scripts/agentic-run.py context run|status --request REQUETE.json   # même contrôleur
```

**Cycle.** Mesure du dernier contexte (jamais le cumul) : < 120 s, sinon récupération
bornée (2 tentatives persistées) puis BLOCKED. À >= 40 % : demande de handoff (steer si
un tour est actif), attente du point sûr (tour inactif, aucun outil, processus de
l'unité limités à l'infrastructure), validation et sauvegarde atomique, fermeture
durable de l'admission, arrêt gracieux (SIGTERM) de l'infrastructure possédée, preuve
de fermeture cgroup/systemd, puis nouveau terminal. >= 50 % est signalé
(`target_exceeded`), pas garanti. Chaque nouvelle génération doit remettre un reçu de
bootstrap vérifié (identité, Git, plan, handoff, permissions, modifications) et une
mesure < 40 % avant son premier tour métier. Handoff invalide : 2 corrections au plus.

**Preuve de bootstrap.** Le JSON écrit par l'agent n'est qu'une déclaration. Le contrôleur
exige dans l'historique runtime (`thread/read`, même thread, tour de bootstrap `completed`)
un `commandExecution` terminé (code 0, cwd exact) de
`python3 scripts/agentic-context.py bootstrap-read --worktree W --instructions I --handoff H
--nonce T`, dont la sortie complète égale le document que le contrôleur reconstruit lui-même :
textes complets des instructions et du handoff (pas seulement leurs SHA256), branche, HEAD,
modifications, et chaque fichier requis (AGENTS.md du worktree s'il existe, skill `start-ticket`)
tant que le document reste sous la borne visible (24 000 octets UTF-8 d'enveloppe comprise,
échappements JSON inclus ; refus avant impression au-delà). Un fichier qui ne tient pas est
annoncé avec son nombre de parties et doit être lu par `bootstrap-file --path P --part K
--nonce T` (parties de 5 000 caractères) : toute partie manquante, tronquée ou étrangère refuse
le reçu. Au checkpoint, avant de fermer la génération, le contrôleur vérifie que le prochain
bootstrap tient dans ces bornes ; sinon BLOCKED, propriétaire et checkpoint conservés.
Codex 0.169.0 enveloppe la commande dans `/bin/bash -lc` avec la source
`unifiedExecStartup`. Dans le journal du même thread et du même tour, le contrôleur relie
l’identifiant de commande, les arguments et le répertoire à l’appel code-mode `exec`
qui les a exécutés. Le répertoire peut être un chemin absolu ou son URI locale exacte.
Pour chaque commande, le retour de cet appel doit contenir le code de sortie zéro et
l’intégralité de la sortie vérifiée dans `thread/read`. Un appel peut rendre plusieurs
parties ensemble. Une attribution ambiguë ou une sortie tronquée bloque la validation.
Le contrôleur vérifie aussi le modèle, l’effort et les permissions effectives par
`config/read`. Si seul le champ des permissions reprend la forme abrégée reconnue de
l’interface Codex, le contrôleur peut demander au même thread au repos de rectifier le reçu
une seule fois. Il journalise cette demande avant envoi, attend la fin de ce tour et
revérifie le reçu avant la mesure de contexte et le démarrage du travail.
La forme directe (sans enveloppe) n'existe que dans les fixtures de test.
Cela prouve des lectures complètes observées, pas la compréhension ; le plan n'est pas relu.
Seuls AGENTS.md et le skill sont garantis chargés : les autres règles déclenchées restent à la
charge de l'agent via le skill.

**Frontières.** Sont de l'infrastructure : les processus attestés à la création (pid,
starttime, argv exact enregistrés par le wrapper `admit-exec` ; le NUL terminal unique de
`/proc/PID/cmdline` est retiré, un vrai argument vide est conservé) et, pour un serveur
`codex` natif, son enfant direct `codex-code-mode-host` (exe et SHA256 du fichier homonyme de
la même release, relevés à l'admission puis revérifiés ; ni comm ni flags n'accordent rien).
Tout autre membre du cgroup, sous-cgroupes compris (inventaire borné de l'arbre), bloque
quiescence et retrait, de même qu'un membership illisible, disparu ou changeant : il est relu
après épinglage et avant tout signal, jamais assimilé à une liste vide. Les shells persistants
sont fermés par l'agent avant le handoff ; leur disparition est prouvée par la quiescence. Le
wrapper refuse, avant `exec`, un environnement effectif (celui que `systemd --user` fournit
réellement) qui contient un nom de facturation/endpoint ou un réglage de routage interdit par
la politique abonnement ; refus à texte fixe, sans valeur, rien n'est neutralisé. Le
nettoyage `systemctl stop` revalide l'invocation et la fermeture. Un serveur/terminal créé et
identifié avant la promotion du journal du lanceur est repris par observation positive (un
seul serveur, un seul TUI) ; une création inconnue reste BLOCKED. Un crash du lanceur avec
journal `identified` ou `verified` (thread connu, avant `submitting`) reprend EXACTEMENT cette
session : mêmes serveur, socket, thread et TUI vivant, sans nouvelle création ni signal. Le
journal n'est jamais cru seul : propriété/processus des deux unités, thread attendu unique,
aucun tour ni prompt existant, cwd, modèle, effort et permissions sont revérifiés avant l'unique
soumission ; session disparue ou ambiguïté : BLOCKED. Un échec explicite d'identification garde
l'arrêt confirmé puis la recréation bornée ; `submitting` reste fermé sans preuve positive.

**Garanties.** Chaque mutation (`turn/start`, `turn/steer`) est journalisée avant l'envoi,
avec nonce, et envoyée une fois ; un résultat inconnu est réconcilié par preuve positive
ou la mission est BLOCKED. Aucun SIGKILL, `cgroup.kill` ni transfert sur timeout. Unités
`SendSIGKILL=no`, `ExitType=cgroup`, `RemainAfterExit=yes`, sans `RuntimeMaxSec`. Les
copies précédentes de checkpoint sont conservées (aucune purge) ; disque plein : BLOCKED.
Pas de progrès (HEAD, modifications, prochaine action inchangés) : BLOCKED.

**Limites.** HEAD, branche, plan ou configuration modifiés pendant la mission :
BLOCKED (réconciliation humaine). BLOCKED est persistant ; l'état et le checkpoint
sont conservés pour diagnostic. Un brouillon `IMPLEMENTATION_COMPLETE` engage la
finalisation avant la prochaine mesure de contexte. Le contrôleur attend la fin du
tour identifié et la quiescence de ses processus. Si la structure du handoff est
invalide, il peut demander deux rectifications de forme au plus sur le même thread.
Chaque demande possède un nonce journalisé avant envoi. Les fichiers métier et le
checkpoint de référence sont vérifiés pendant la rectification. Après la sauvegarde
atomique du document validé, le contrôleur ferme l’admission et vérifie la fermeture
des unités de la dernière génération avant de déclarer `completed`. Les gates qualité
gardent leur propre verdict.

Un ancien blocage de mesure après la fin du travail peut reprendre cette finalisation.
La reprise exige le brouillon final dont l’empreinte figurait dans le journal, le
checkpoint d’origine intact et le dernier dispatch terminé sur la même session
possédée. Le diagnostic historique est conservé. Le schéma exact des
réponses `thread/read` n'est établi que par la recette réelle, et la route qualifiée est celle du
binaire natif ELF 0.169.0 installé (aucun wrapper Node, aucune prise en charge universelle).
En phase `working`, si le serveur et le thread de la génération sont positivement identifiés et
si le seul ancien TUI est prouvé terminé (unité `exited`, même invocation), le contrôleur
rouvre un TUI de la même génération et du même thread, sans prompt ; intention et essais
(2 au plus) sont persistés avant l'effet, une création interrompue est reprise par observation
positive ; serveur perdu, identité changée ou état inconnu : BLOCKED. Les descendants
métier du TUI (hors infrastructure attestée) empêchent le retrait : la mission reste en
attente puis BLOCKED, jamais de kill. La fenêtre du terminal
peut rester ouverte après la fin du TUI jusqu'au nettoyage de l'unité. Le sandbox des outils
dépend d'un prérequis d'environnement (profil AppArmor de `/usr/bin/bwrap` chargé par
l'opérateur) que le contrôleur n'installe ni ne modifie.

**Rollback.** Interrompre `run` (aucun effet sur la session en cours), garder le
checkpoint, puis fermer l'unité `agentic-ctx-*` listée dans `boundary.json` seulement
après preuve de fermeture ; revenir au flux manuel. Ne pas supprimer l'état.

## Mesurer sans promettre

Comparer une même tâche, version, modèle/niveau, outils, fichiers et critères,
avec succès et retours correctifs. Noter nombre de fichiers lus, lectures redondantes, octets/lignes chargés, appels d’outils,
durée et retries ; tokens/coût/quota seulement si une mesure réelle est exposée,
sinon null ou « non observable ». Octets/4 est une estimation grossière, pas une facture.
Le gain de taille d’AGENTS n’est ni un benchmark de qualité ni un gain de quota.
Ne pas réécrire les vieux messages pour simuler une économie. Une optimisation
qui fait perdre un diagnostic ou un AC est rejetée, même si la sortie raccourcit.

Scénario reproductible : compter `wc -c -l AGENTS.md`, choisir un ticket LIGHT,
consigner les documents effectivement lus via l’index ; comparer avec la lecture
complète antérieure sur le même ticket. Répéter sur LARGE multi-app avec contrats
et sécurité. Rapporter taille statique et comportement observé séparément.

## Analyse des 26 conseils du guide fourni

Synthèse critique du guide utilisateur (septembre 2026), sans redistribution du
PDF. Chiffres commerciaux et anecdotes non repris comme preuves. « Reporter »
signifie évaluer seulement sur demande/besoin ; aucune installation automatique.

| N° | Conseil | Décision et raison |
|---|---|---|
| 01 | Réduire le raisonnement | Adapter : niveau le moins coûteux capable, risque et validation priment. |
| 02 | Éviter Max | Adapter : aucun plafond universel ; escalade justifiée. |
| 03 | Comprendre Ultra | Retenir : vérifier disponibilité et coût de délégation, voir MODELS. |
| 04 | Message programmé à 6 h | Rejeter : hors besoin produit, règles de quota variables, aucune tâche créée. |
| 05 | Choisir avant de commencer | Adapter : stabilité par phase, pas de promesse cache client. |
| 06 | Désactiver vitesse 1,5x | Reporter : arbitrage utilisateur latence/coût, aucune config globale modifiée. |
| 07 | Corriger en cours de travail | Retenir : intégrer les précisions sans perdre l’objectif initial. |
| 08 | Caveman | Adapter : sobriété native dans AGENTS, précision et preuves préservées ; aucune installation. |
| 09 | I Have ADHD | Adapter : réponse principale en tête et sections utiles seulement ; aucune installation. |
| 10 | Identifier la consommation | Adapter : mesures observables, aucune attribution de quota inventée. |
| 11 | Fournir un chemin | Retenir : point de départ précis réduit les recherches inutiles. |
| 12 | Cartographier le workspace | Adapter : carte courte et actualisée selon les changements. |
| 13 | AGENTS comme aiguillage | Retenir : invariants à la racine, détails obligatoires selon déclencheur. |
| 14 | Second cerveau | Reporter : utile sur corpus durable, pas de doublon du code. |
| 15 | Connecteurs inutilisés | Adapter : charger au besoin ; désactivation globale seulement autorisée. |
| 16 | Nettoyage mensuel | Adapter : audit si accumulation ; ni suppression ni planning implicites. |
| 17 | Images ailleurs | Reporter : fournisseur, données, secrets et coûts à qualifier séparément. |
| 18 | Compaction ciblée | Adapter : checkpoint naturel, préserver décisions et erreurs ouvertes. |
| 19 | Ponytail | Reporter : simplicité retenue ; outil optionnel à qualifier. |
| 20 | RTK | Reporter : mesurer sorties et diagnostics, pas extrapoler au coût total. |
| 21 | Headroom | Reporter : proxy/cache/récupération et auth à qualifier. |
| 22 | QMD | Reporter : gros corpus seulement ; coût d’index et données sensibles. |
| 23 | Budget | Adapter : budget observable ou indicateurs approximatifs explicités. |
| 24 | Tâches récurrentes | Retenir : amortir une optimisation mesurée sans chiffre garanti. |
| 25 | Agents nommés | Adapter : trois rôles portables, spécialités par contrat et capacités disponibles. |
| 26 | Cerveau et mains | Retenir : orchestration, exécution cadrée, review indépendante. |

Voir [MODELS](MODELS.md) et [OPTIONAL_TOOLS](OPTIONAL_TOOLS.md).
Le chargement hiérarchique d’instructions permet des règles de sous-dossier,
mais les règles racine doivent rester compatibles : [AGENTS.md Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Gate avant longue exécution

- [ ] décisions et contraintes accessibles, contexte historique résumé
- [ ] sorties déléguées exploitables et preuves localisables
- [ ] chemins, phase, blockers et prochaines actions dans le checkpoint
- [ ] aucune hypothèse de quota présentée comme mesure
