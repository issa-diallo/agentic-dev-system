# Design — DOC-readme

Design PASS après Research. README présente objectif, échelles, cycle complet,
démarrage et trois installations, héritage, rôles, concision et liens ciblés.
Règles détaillées restent dans leurs documents canoniques. Distinguer héritage
à l'installation, mises à jour manuelles, activation LOCAL et contrôle de présence.

Design PASS : introduction orientée bénéfices, exemple de fonctionnalité et tableau
séparant isolation du code, environnement d'exécution et indépendance de review.
Expliquer ce qui est installé et ce que le projet doit encore configurer.

## Extension — Lead Tech de PR
Design PASS après Research. Profil REVIEWER : synthèse finale indépendante,
attachée à base/head SHA et CI. STANDARD/LARGE : second agent distinct implementer
et premier reviewer ; LIGHT : reviewer indépendant peut remplir les deux missions.
Critical/Major ou preuve indispensable absente empêchent la livraison. Corrections
puis revalidation du diff concerné ; head/base modifié rend avis précédent périmé.
Pas d'auto-merge, correction directe, publication GitHub ou nouvel outil implicites.
