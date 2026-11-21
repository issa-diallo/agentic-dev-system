# Gérer les skills d’un projet

Le [catalogue](SKILL_CATALOG.md) livré avec la méthode décrit les compétences et leurs sources. Chaque projet possède son propre état d’installation. Les worktrees Git rattachés à ce projet le partagent. En installation LOCAL, utiliser les commandes suivantes depuis le projet. Pour une installation partagée, remplacer `.agentic-local/scripts/` par `scripts/`.

```bash
store=.agentic-local/scripts/agentic-skill-store.py
python3 "$store" inventory --repo .
python3 "$store" install marketing/copywriting --repo .
python3 "$store" disable marketing/copywriting --repo .
python3 "$store" enable marketing/copywriting --repo .
python3 "$store" uninstall marketing/copywriting --repo .
```

L’inventaire expose le commit du catalogue et le commit installé. `installed` indique la présence dans le magasin du projet. `enabled` indique le choix de configuration, activé par défaut. `available` exige une installation à la révision et à la projection approuvées, avec toute sa chaîne de dépendances installée et activée. Le routeur vérifie ensuite la mission et la compatibilité du harnais. La consultation de l’inventaire lit uniquement les métadonnées locales.

**Installation.** La commande explicite `install` récupère le document et la licence depuis les chemins publics du commit épinglé sur GitHub. Elle vérifie les deux empreintes SHA-256, extrait les lignes auditées, puis vérifie l’empreinte de l’extrait. Elle conserve cet extrait et les conditions de licence dans `agentic-skill-store/v1.sqlite3` sous le répertoire Git commun. Les actions explicites sur le magasin sont atomiques, y compris l’installation des dépendances. Une nouvelle demande pour le même contenu réutilise l’installation. Les documents distants, scripts, commandes de plugins et hooks ne sont jamais exécutés par l’installateur. Git, Python 3 avec SQLite et un accès HTTPS direct à `raw.githubusercontent.com` suffisent à l’installation.

**Lecture pendant une mission.** Le brief fournit l’identifiant et les empreintes correspondant à sa sélection. Exemple avec un shell possédant ces deux valeurs issues du brief ou de l’inventaire :

```bash
python3 "$store" load marketing/copywriting --repo . --agent codex \
  --expect "$excerpt_sha256" --commit "$source_commit"
```

La commande contrôle la compatibilité du harnais, la configuration, la provenance et l’intégrité juste avant de restituer l’extrait. La réponse JSON porte `LOADED` et `applied: NOT_OBSERVED`. Le résultat du travail de l’agent apporte la preuve d’une utilisation effective. Le champ `terms` désigne la licence au commit indiqué. L’accès au catalogue, au magasin et aux instructions repose sur la confiance accordée aux fichiers du projet et au répertoire Git de l’utilisateur.

**Mise à jour et retrait.** Mettre à jour la méthode avec `update-agentic.py` livre les pins revus aux projets existants. Appliquer ensuite explicitement `python3 "$store" update marketing/copywriting --repo .`. Une nouvelle version du catalogue rend l’ancien pin indisponible jusqu’à cette opération si les documents, la licence, la projection ou les dépendances changent. Revenir à un pin antérieur exige un catalogue revu contenant ce pin et la même commande `update`. Les mises à jour gardent la désactivation locale. Le retrait d’une dépendance utilisée demande d’abord celui de ses consommateurs.

Une erreur réseau ou d’intégrité laisse les versions installées dans leur état antérieur. Une collision d’origine sous un identifiant demande une vérification du catalogue et une décision explicite de retrait. Si la licence ou le périmètre du contenu restent incertains, l’entrée demeure bloquée. Les autres projets, la configuration personnelle des clients et les permissions du harnais restent hors du périmètre de ces commandes.
