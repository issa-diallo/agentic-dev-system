# Catalogue des compétences spécialisées

Le registre versionné `skills/catalog.json` décrit les ressources externes examinées pour la méthode. Le projet reçoit ces métadonnées dès l’installation LOCAL ou partagée. L’installateur ne contacte aucun éditeur de skills. Pour un projet déjà équipé, lancer `python3 update-agentic.py /chemin/du/projet` depuis le dépôt du framework. L’outil de mise à jour respecte les personnalisations.

## Disponibilité par compétence

La colonne « Disponible » précise ce qui peut être installé. « Après installation » signifie que la sélection automatique devient possible lorsque le projet possède l’extrait vérifié et que sa configuration l’autorise. Les deux harnais lisent du Markdown sur demande. Chaque projection contient seulement les passages évalués au commit indiqué dans le registre.

| Skill | Disponible | Sélection automatique | Agents compatibles | Déclencheur |
|---|---|---|---|---|
| `anthropic/frontend-design` | Extrait Apache-2.0 | Après installation | Codex, Claude Code | Concevoir une interface React ou une landing page |
| `marketing/copywriting` | Extrait MIT | Après installation | Codex, Claude Code | Rédiger la promesse et le CTA d’une page commerciale |
| `claude-seo/seo-audit` | Grille MIT | Après installation | Codex, Claude Code | Auditer le référencement d’un site avec les pièces disponibles |
| `claude-seo/seo-page` | Grille MIT | Après installation | Codex, Claude Code | Examiner titres, liens, balises et contenu d’une page |
| `claude-seo/seo-geo` | Grille MIT | Après installation | Codex, Claude Code | Évaluer la citabilité dans les moteurs génératifs |
| `anthropic/canvas-design` | Extrait Apache-2.0 | Après installation | Codex, Claude Code | Composer une affiche ou une illustration statique |
| `showcase/systematic-debugging` | Extrait, MIT déclaré dans le README | Après installation | Codex, Claude Code | Localiser la cause d’un bug Python ou d’un test intermittent |
| `owasp/owasp-security` | Grille MIT | Après installation | Codex, Claude Code | Revoir l’authentification ou les autorisations dans le code |
| `context/context-optimization` | Extrait MIT | Après installation | Codex, Claude Code | Réduire les tokens nécessaires à l’orchestrateur |
| `context/multi-agent-patterns` | Extrait MIT | Après installation | Codex, Claude Code | Examiner la coordination et les transmissions entre agents |
| `context/memory-systems` | Extrait MIT | Après installation | Codex, Claude Code | Concevoir la rétention et le rappel entre sessions |
| `remotion/remotion-best-practices` | Bloqué, droits à clarifier | Non | Aucun dans ce module | Vidéo programmée avec Remotion |

Le dépôt Remotion référence le projet principal depuis son manifeste. La révision auditée ne fournit pas de licence attribuable aux instructions du skill. Une confirmation des droits et une revue des passages requis permettront de réexaminer sa disponibilité. [Source Remotion](https://github.com/remotion-dev/skills/tree/6f55706d1069e512430582ad86e4e57dc07afe1b)

Awesome Claude Skills figure dans `discovery` pour examiner ultérieurement des candidats. Une proposition issue de cette liste requiert sa propre provenance, sa licence et une revue de son contenu. Le catalogue exclut Superpowers et les imports transitifs de collections. [Index de découverte](https://github.com/ComposioHQ/awesome-claude-skills/tree/be2a406907dbc61b73e6827ded415c96139d13a2)

## Interpréter les états

| État | Preuve |
|---|---|
| Installable | Le catalogue approuve le couple source et licence pour une révision et des extraits précis. |
| Installé | Le magasin du projet contient la révision récupérée et son attribution. |
| Activé en configuration | Le projet autorise sa sélection. Le réglage par défaut autorise chaque skill installé. |
| Disponible pour l’agent | La projection installée est valide, autorisée et compatible avec son harnais. |
| Sélectionné | Le brief de la mission contient la référence retenue et sa justification. |
| Chargé | Le chargement à la demande a fourni l’extrait contrôlé pour cette mission. |
| Utilisé | Une preuve de travail ou le handoff relie cet extrait à une action ou un résultat observé. |

## Provenance et maintenance

Pour ajouter une compétence ou actualiser une révision, suivre ces étapes dans une PR de catalogue.

1. Identifier le dépôt, le commit complet et le chemin du `SKILL.md`. Lire la licence applicable à ce chemin. Inspecter les instructions, les scripts et les dépendances demandés sans les exécuter. Vérifier l’origine des copier-coller et les droits des ressources annexes. Toute incertitude sur l’autorisation d’installation conduit à `status: blocked` et `agents: []`.
2. Choisir des passages autonomes compatibles avec les agents cités. Garder hors des extraits les appels réseau, secrets, scripts, hooks, commandes de harnais et nouvelles règles de workflow. Les permissions, la délégation et les validations continuent de relever du projet. Un harnais supplémentaire exige un adaptateur et une vérification de son mode de lecture.
3. Déclarer `id` au format `namespace/nom`, description courte, catégorie, capacité, `repo`, `commit`, `path`, `license`, `terms`, restrictions et agents compatibles. L’attribution conserve la provenance amont et le texte de licence original. Une projection doit être identifiée comme extrait modifié. Pour Systematic Debugging, `terms` désigne le README et `terms_ranges` repère sa déclaration MIT.
4. Calculer les SHA‑256 sur les octets amont du skill et de la licence dans `files_sha256`. Déclarer les intervalles de lignes inclusifs en base 1 dans `ranges`. Pour `extracted_sha256`, conserver les fins de ligne originales et insérer un octet LF entre deux blocs. Exemple reproductible avec des octets locaux déjà vérifiés :

   ```python
   lines = source_bytes.splitlines(keepends=True)
   excerpt = b"\n".join(b"".join(lines[first-1:last]) for first, last in ranges)
   digest = hashlib.sha256(excerpt).hexdigest()
   ```

5. Décrire le besoin dans `triggers` en français et en anglais. Chaque groupe est nécessaire, ses expressions sont des alternatives. `files` contient les motifs de chemins qui corroborent ce besoin. `excludes` précise les contextes à écarter. Renseigner `priority` pour les arbitrages et `depends_on` pour les identifiants réellement requis. Les projections initiales sont indépendantes.
6. Vérifier la distribution avec `python3 -m unittest discover -s tests -p test_skill_catalog.py`. Couvrir également le routage avec une mission pertinente, une mission proche à exclure et un harnais incompatible. Actualiser le tableau et procéder à la revue indépendante du diff, fichiers de licence compris.

La collection SEO fournit des grilles d’analyse applicables aux pièces d’une mission. Les données de trafic, de crawl ou de performance nécessitent des preuves fournies séparément. Canvas utilise les fontes locales de l’environnement. Les skills de contexte réutilisent les checkpoints du framework. Les projections ne distribuent aucun runtime tiers.
