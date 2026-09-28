# Architecture — <Produit>

## Status

`ARCHITECTURE: DRAFT | PASS | BLOCKED`

## Contexte

- type de produit :
- utilisateurs / charge attendue :
- contraintes majeures :
- contraintes d'hébergement :
- contraintes de résidence des données :
- contraintes légales / conformité :
- budget / coûts récurrents :
- compétences de l'équipe :
- vitesse de livraison attendue :
- intégrations incontournables :
- hypothèses :

## Stack decision

### Requirements

Décrire les besoins qui doivent guider la stack.

- performance :
- scalabilité :
- time-to-market :
- disponibilité :
- sécurité :
- maintenabilité :
- observabilité :
- coût :
- portabilité :
- compétences disponibles :

### Options considered

#### Option A — <nom>
- frontend :
- backend :
- database :
- auth :
- infra :
- avantages :
- limites :

#### Option B — <nom>
- frontend :
- backend :
- database :
- auth :
- infra :
- avantages :
- limites :

Ajouter d'autres options si nécessaire.

### Selected stack

- language(s) :
- frontend :
- backend :
- API style / protocol :
- database :
- ORM / data access :
- authentication :
- authorization :
- cache :
- queue / jobs :
- object storage :
- email / notifications :
- search :
- observability :
- secrets :
- infrastructure :
- hosting :
- CI/CD :
- testing :
- package manager / build tooling :

### Why this stack

<Pourquoi cette combinaison répond le mieux aux contraintes du projet.>

### Trade-offs

<Compromis acceptés.>

### Rejected alternatives

- <option> — rejetée parce que …
- <option> — rejetée parce que …

## Repository structure

```text
<tree>
```

## Boundaries / modules

- …

## Data model

- …

## API / contracts

- …

## Authentication

- …

## Authorization

- …

## Tenant isolation

- …

## Async / queues / jobs

- …

## External integrations

- …

## Security

- …

## Secrets

- …

## Logging / observability

- …

## Environments

- local :
- test :
- staging :
- production :

## CI/CD

- …

## Deployment

- …

## Testing strategy

- unit :
- integration :
- contract :
- e2e :
- security :
- load/performance si pertinent :

## ADR required

Lister toutes les décisions structurantes qui nécessitent un ADR.

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | … | TODO/PASS |

Les ADR sont stockés dans `docs/adr/` et créés depuis
`docs/agentic/templates/ADR.md`.

## Architecture Gate

- [ ] contraintes de choix explicitées
- [ ] au moins les alternatives raisonnables considérées
- [ ] stack complète sélectionnée
- [ ] raisons et compromis documentés
- [ ] alternatives rejetées documentées
- [ ] boundaries définies
- [ ] data définie
- [ ] interfaces définies
- [ ] auth/authz définies
- [ ] sécurité définie
- [ ] stratégie de tests définie
- [ ] deployment défini
- [ ] ADR structurants créés ou planifiés
- [ ] aucune décision structurante bloquante

Verdict : PASS / BLOCKED
