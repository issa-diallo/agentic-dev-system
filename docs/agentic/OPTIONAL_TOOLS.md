# Outils optionnels : qualification avant activation

Socle opérationnel sans aucun de ces outils. Étude documentaire du 2026-10-08,
compatibilités déclarées par les projets, non testées ici. Aucune dépendance,
clé, hook, proxy, serveur MCP ni configuration globale installés par la méthode.

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
- Compatibilité : qualification requise pour client, auth et routage réels avant adoption.
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

## Protocole commun

Avant un pilote autorisé : noter source/version, fichiers/configuration touchés,
données exposées, baseline, critère de qualité et rollback. Sauvegarder seulement
les réglages utiles, sans publier de secrets. Après activation puis désactivation,
rejouer même tâche et tests avec accès au brut. Rejeter toute perte de précision.
Sans besoin démontré, garder le socle ; aucun installer tiers dans nos scripts.
