# Research — #6

RESEARCH: PASS. Entrée PRODUCT, mode STANDARD, complexité élevée.

## Audit avant modification fonctionnelle
Base origin/main 20a2e1b ; worktree /tmp/agentic-codex-context,
branche feat/codex-context. Le checkout utilisateur reste intact.
Inventaire complet via rg --files --hidden, lectures README → METHOD → WORKFLOW
→ COMMITS → produit/ADR (absents initialement) → templates, rôles et scripts.
48 fichiers suivis : méthode Markdown, 3 rôles, 17 templates, installateur Bash,
checker de présence, CI syntaxe/tests, issue/PR templates et hooks documentaires.
Les artefacts historiques DOC-existing-project confirment le contrat à conserver.

## Diagnostic
AGENTS 8 764 octets ; METHOD 4 763 ; WORKFLOW 2 958 ; COMMITS 8 691.
Navigation existante sommaire ; CONTEXT sans checkpoint complet ; modèles décrits
seulement par catégories ; rôles incomplets (mention DossierClé non portable).
Installateur : PRODUCT copie 5 templates ; EXISTING omet produit ; LOCAL exclut
via Git et exige activation explicite. Copie récursive docs/agentic hors work,
mais STATUS potentiellement rempli serait copié : initialiser depuis un template.
Ne copie pas CI ; intention conservée. Checker vérifie seulement présence,
jamais les gates. 10 tests stdlib passent avant changement (2026-10-08).

## Guide et sources
PDF utilisateur guide_limites_gpt6_astra_agence_agentique.pdf, 16 pages,
SHA256 312d654d742de45c61289d0bc45182dbadee9f754b3faba11841d1fd88bebca8.
Extraction locale pdftotext ; PDF non redistribué. Analyse des 26 conseils dans
la future section de CONTEXT. Sources officielles Codex lues pour découverte
AGENTS, modèles, sous-agents et cache ; étude séparée des quatre dépôts tiers
par /root/tools_research, lecture seule. Compatibilités déclarées, non testées.

## Dépendances et sécurité
Aucune nouvelle dépendance runtime. Tests Python/Git/Bash existants.
Auth, tenant, données métier : non applicables. Secrets : ne pas afficher ni
copier credentials ; index/proxy optionnels peuvent exposer des contenus.
Push/PR autorisés ; merge interdit par utilisateur. Stack inchangée.
Risques : règle perdue, lien cassé, état source hérité, outil activé implicitement,
cache dégradé, chiffres non comparables. Tests et reviewer indépendant requis.
Aucun blocker ; pas de quota observable, donc mesures en octets seulement.

Verdict : PASS

## Complément — communication native
Research PASS. Même ticket/PR, approfondissement LIGHT du périmètre déjà cadré.
AGENTS est copié à l'identique dans les trois modes ; CONTEXT contient déjà une
règle concise et le tableau Caveman/I Have ADHD. Aucun nouveau fichier de
politique ni dépendance nécessaire. Risque : appliquer le format conversationnel
aux rapports structurés et supprimer une information critique. Valider héritage,
exceptions et exemples de réponse par revue indépendante ; pas de garantie
universelle sur le comportement d'un modèle.
