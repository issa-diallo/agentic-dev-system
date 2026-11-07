# Outils optionnels : choix et intégration

Socle opérationnel sans aucun de ces outils. Étude documentaire du 2026-10-08,
compatibilités déclarées par les projets, non testées ici. Entrée Cloudflare
security-audit ajoutée après lecture du skill le 2026-11-07. Aucune dépendance,
clé, hook, proxy, serveur MCP ni configuration globale installés par la méthode.

## Choix sans gate de qualification

Les notes ci-dessous concernent l’intégration et l’exploitation, sans constituer
des gates Architecture/ADR. Un outil choisi par l’utilisateur est enregistré et
la phase avance, sans pilote, benchmark ou test de qualification obligatoire.
Les contrôles d’intégration pertinents se font en Execute/Verify. Les mesures de
gains sont facultatives sauf critère explicite ; elles peuvent suivre l’implémentation.
Les autorisations d’actions externes et la protection des secrets restent applicables.
Un test préalable est exceptionnel : contradiction concrète ou risque critique
sans mitigation, avec justification et test minimal selon METHOD.

## RTK

- Fonction : binaire Rust filtrant les sorties shell ; utile si logs répétitifs volumineux.
- Compatibilité Codex : hooks PreToolUse/updatedInput et instructions documentés par le [projet](https://github.com/rtk-ai/rtk#readme), à vérifier sur la version du client.
- Gains : métriques de sortie, parfois estimées en octets/4 ; pas de preuve de baisse du coût complet.
- Risques : diagnostic masqué ; conserver sortie brute pour Verify. Télémétrie annoncée désactivée par défaut, vérifier la version.
- Cache : filtrage unique annoncé stable ; aucun benchmark du harness réalisé ici.
- Maintenance : binaire et hooks à suivre ; retester parsing et erreurs après mise à jour.
- Activation : pilote opt-in par invocation explicite, baseline brute et même tâche.
- Retrait : enlever hooks/instructions puis binaire selon [INSTALL](https://github.com/rtk-ai/rtk/blob/develop/INSTALL.md), vérifier les commandes Codex de la version.

## QMD

- Fonction : recherche CLI/MCP sur corpus documentaire ; pertinent pour milliers de documents, pas nécessaire pour ce petit socle.
- Compatibilité Codex : CLI/MCP génériques, pas de section Codex dédiée dans le [README](https://github.com/tobi/qmd#readme).
- Gains : pertinence de recherche, aucun gain de quota établi ici.
- Risques : index contenant les textes, chemins sensibles ; HTTP sans auth, préférer stdio ; modèles locaux téléchargés.
- Cache : index/cache local distinct du cache fournisseur.
- Maintenance : Node/Bun, SQLite, modèles, espace disque et réindexation.
- Activation : opt-in sur collection autorisée, exclure secrets, comparer rappel et pertinence avec rg.
- Retrait : plan recommandé non vérifié upstream : stopper daemon, retirer MCP/package, supprimer seulement les index ciblés après sauvegarde.

## Headroom

- Fonction : compression via proxy/wrapper ; [wrap Codex documenté](https://github.com/headroomlabs-ai/headroom#readme), Python et extras ML natifs ; wrapper pouvant installer Serena.
- Compatibilité : contrôler client, auth et routage réels lors de l’intégration avant d’exposer des credentials ; cela ne bloque pas le choix en Architecture.
- Gains : annonces du projet dépendantes des données ; aucun benchmark exécuté ici.
- Risques : credentials/contenus dans `~/.headroom`, mémoire `.headroom` projet ; diagnostics compressés à récupérer via [CCR](https://docs.headroomlabs.ai/docs/ccr).
- Cache : préfixe stable annoncé pour nouveaux contenus ; tester cache et récupération, ne pas réécrire l’historique sans mesure.
- Maintenance : élevée ; seule dernière release supportée selon [SECURITY](https://github.com/headroomlabs-ai/headroom/blob/main/SECURITY.md).
- Activation : reportée jusqu’à pilote explicite avec données autorisées, sorties brutes et rollback ; ne pas combiner RTK sans étude.
- Retrait : unwrap documenté ; vérifier restauration des réglages, arrêter proxy, traiter caches/credentials séparément sans suppression aveugle.

## Ponytail

- Fonction : instructions de simplicité, pas compression ; [README](https://github.com/DietrichGebert/ponytail#readme) et [skill](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md).
- Compatibilité : plugin Codex avec deux hooks Node déclaré ; vérifier [portabilité](https://github.com/DietrichGebert/ponytail/blob/main/docs/agent-portability.md).
- Gains : benchmarks sur autre modèle non extrapolables à Codex ; aucune économie garantie.
- Risques : minimalisme supprimant des AC ; les gates du projet priment, ne jamais remplacer AGENTS.
- Cache : ajout d’instructions, aucun bénéfice de cache établi.
- Maintenance : plugin, Node, hooks et copies d’instructions à suivre.
- Activation : inspiration documentaire suffit ici ; pilote opt-in si besoin démontré.
- Retrait : off désactive sans désinstaller ; retirer plugin/hooks/copies selon [INSTALL](https://github.com/DietrichGebert/ponytail/blob/main/INSTALL.md), vérifier règles résiduelles.

## Cloudflare security-audit

- Source : [dépôt officiel](https://github.com/cloudflare/security-audit-skill) et [SKILL.md](https://github.com/cloudflare/security-audit-skill/blob/main/skills/security-audit/SKILL.md), nom déclaré `security-audit`.
- Fonction : conseil sécurité et recherche de vulnérabilités fondée sur le code, les frontières de confiance et des preuves vérifiées indépendamment. Complète les skills de développement sécurisé sans remplacer les gates Verify/Review/SHIP.
- Activation : conseil ciblé par défaut ; workflow complet seulement sur demande explicite d'audit de code, de pentest, de revue complète ou de rapports. Charger ou sélectionner le skill n'autorise ni audit complet ni création de rapports.
- Audit complet : reconnaissance, recherche guidée par couverture, validation des candidats, sortie structurée, vérification indépendante puis rapports. Distinguer `confirmed`, `needs_validation` et `rejected` ; aucune sévérité sur `needs_validation`.
- Prérequis : outils de sous-agents avec isolation des écritures ; Node.js pour les validateurs JSON sans dépendance. Tout code cible exécuté exige une sandbox imposée par l'OS : réseau externe coupé, environnement minimal autorisé, cible/outils en lecture seule, écritures dans le scratch assigné et limites de ressources/temps. Sans ces contrôles, ne pas exécuter le code cible ; consigner la validation manquante.
- Périmètre : lecture source et reproductions locales bornées ; aucun test de service déployé, d'infrastructure partagée ou d'identité réelle. L'audit décrit les corrections, sans modifier la source cible.
- Rapports : hors du dépôt cible par défaut ; chemin interne seulement si explicitement choisi par l'utilisateur et entièrement ignoré par Git. Les rapports restent hors des PR applicatives selon [PULL_REQUESTS](PULL_REQUESTS.md).
- Installation : volontaire via le mécanisme de skills de l'hôte, depuis `skills/security-audit` du dépôt officiel ; fournir ensuite cette racine installée au [routeur](SKILL_ROUTING.md). Aucun téléchargement ni copie du skill tiers par `install-agentic.sh`.
- Maintenance et retrait : suivre la version installée, ses instructions et validateurs ; aucune exhaustivité ni économie garantie. Retirer la référence de la sélection ou désinstaller via l'hôte, sans supprimer les preuves d'audit conservées.

## Protocole d’un pilote demandé

Ce protocole s’applique seulement si un pilote est explicitement demandé ; il
n’est pas un préalable au choix d’un outil. Avant ce pilote : noter source/version, fichiers/configuration touchés,
données exposées, baseline, critère de qualité et rollback. Sauvegarder seulement
les réglages utiles, sans publier de secrets. Après activation puis désactivation,
rejouer même tâche et tests avec accès au brut. Rejeter toute perte de précision.
Sans besoin démontré, garder le socle ; aucun installer tiers dans nos scripts.
