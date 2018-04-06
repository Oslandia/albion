Albion
######

Construction de coupes et volumes à partir de données de sondages


Introduction 
************

La construction volumétrique d’objets géologiques (lithologie, minéralisation…)  est  une tache chronophage, réalisée traditionnellement dans des logiciels miniers de type modeleur. Ces derniers, permettent une représentation 3D, à partir de données de sondages, de coupes. Ces logiciels, souvent complexes sont assez peu ouverts aux données cartographiques et aux outils modernes développés au sein des logiciels de type SIG, rendant les modélisations 3D laborieuses et non reproductibles. 

Albion est un logiciel développé dans QGIS, simplifiant la modélisation d’un gisement minier de type stratiforme à partir de coupes bidirectionnelles, en couplant toutes les données cartographiques acquises par le géologue ainsi que les données de sondages. La construction de coupes est grandement facilitée en utilisant la notion de graphe, où chaque donnée géologique observée le long du sondage est interprétée comme le sommet d’un graphe. Cette approche permet de simplifier le travail de digitalisation, elle fournit aux coupes un caractère évolutive, permettant une adaptation rapide des géométries au fur et à mesure de l’acquisition de nouvelles données, ou de nouveaux concepts géologiques et miniers. 

La construction volumétrique s’effectue automatiquement par addition de volumes élémentaires. Cette approche innovante permet de créer des volumes complexes, en parfaite adéquation avec les données acquises et les contraintes géologiques. Le  temps de modélisation est ainsi grandement économisé, tout en offrant des volumes parfaitement reproductible et facilement évolutif. Les données d’entrée du logiciel sont au format standard, les données de coupes et de volumes sont facilement exportable vers les logiciels géostatistiques classiques utilisés pour le calcul des ressources et des réserves. 


Quelques notions de base
************************

Définition d’un nœud [node]
===========================


La donnée de sondage constitue la donnée d’entrée,  elle  correspond aussi bien à des données numériques d’enregistrements continus le long de sondage (exemple de données diagraphiques), qu’à des observations  ou commentaires géologiques faits lors de la description de carotte ou de cutting. La nature de ces données et format sont exposés  au chapitre Format des données de sondages C’est à partir de ces informations observées/enregistrées que sont établit les passes  géologiques (lithologie, formation, faciès, minéralisation) qui seront l’élément de base pour la construction de coupes. Une passe (on utilise aussi le terme génératrice)  correspond géométriquement à un segment définit par un point toit et un point mur correspondant à la limite supérieure et inférieure de l’objet géologique intersecté en  sondage.  Les passes, regroupent des informations géologiques de même nature. Dans Albion, une passe géologique est un nœud.

Définition d’un graphe [graph] et d’un segment [edge]
=====================================================

La corrélation d’une passe  de sondages  à un autre sondage, le long d’un plan (en général plutôt vertical) constitue une coupe (Erreur : source de la référence non trouvéeA).  Afin de définir le plus justement possible en 3D la géométrie des objets géologiques modélisés, les coupes seront de nature pluridirectionnelle, en plan elles formeront un graphe (Erreur : source de la référence non trouvée). Un graphe est composé de segment ou [edge] joignant les nœuds entres eux. 

Les graphes sont   non orientés et présentent une  topologie de type homogène.   



Notion d’héritage
=================

Les corps géologiques modélisés ont des propriétés géométriques parfois dépendantes de la géométrie de d’autres corps géologique modélisé :

 - la  minéralisation d’un gisement à une teneur [A] doit par définition s’emboiter dans le volume minéralisé construit à une teneur supérieure[A*2].

- une minéralisation doit être contenue dans le volume de la formation géologique portant cette minéralisation.

- un volume de faciès oxydé doit suivre la géométrie du faciès réduit et les volumes doivent oxydé-réduit doivent s’emboiter parfaitement. 

Il est ainsi pertinent pour mieux contraindre le volume modélisé, de tenir compte de cette relation géométrique des objets géologiques entres eux. Ainsi se définit la notion de parent  ou d’héritage afin d’inscrire cette dépendance géométrique des corps géologiques entres eux, dans le processus de construction de coupes puis de volumes.  


Figure 1. – : Vue en coupe un graphe (ligne bleue-grise), reliant des passes géologiques (bleu foncé). Les passes géologiques  correspondent à la formation géologique B. 


Figure 2.  La  formation géologique B est tracée automatiquement à partir du graphe


Figure 3. - Cas des passes minéralisées à partir des mesures gamma. La minéralisation est portée par la formation géologique B. Le graphe minéralisation est donc hérité du graphe formation B


Figure 4. – Le graphe de la minéralisation porté par la formation est tracé automatiquement, la minéralisation suit la géométrie de la formation.   


Notion de volumes élémentaires
==============================

Au même titre que la passe (génératrice) constitue la brique élémentaire de  la construction des coupes, les polygones coupes sont les éléments de base de la construction volumétrique. La modélisation 3D s’effectue par  une approche additive, où au droit d’un minimum de trois passes est construit automatiquement un volume « élémentaire », épousant parfaitement la géométrie des polygones coupes en contact avec les passes.  Les volumes élémentaires sont composés d’une surface de type Toit correspondant à une surface triangulée reliant les points Toit des polygones coupes en contact avec les génératrices du volume élémentaire. De même une surface de type Mur construite à partir des points Mur des polygones en contact est créée, ces surfaces Toit/Mur reliées par une surface verticale décrivant  le pourtour des deux surfaces Toit/Mur constituent un volume élémentaire qui par addition des autres volumes correspond au volume que l’on cherche à modéliser et  ceci quelques soit la complexité du volume construit.    


Tutorial
########


Préambule
*********

Afin de faciliter la prise en main du logiciel, des données sont à la disposition des utilisateurs, pour suivre plus facilement ce tutoriel

Données : 
  - N_T_deviation.txt : fichier des données de déviation du sondage
  - N_T_collar.txt : fichier de l localisation des têtes de sondages
  - N_T_formation.txt : fichier de la table formation
  - N_T_lithology.txt : fichier de la table lithologie
  - NT_avp.txt et NT_RESI.txt : fichiers de diagraphie.


Figure 5. - Les principales étapes de construction volumétrique sous Albion



Importation des données
***********************

Création d’un projet
====================

    1) Avant toutes constructions de coupes, de volumes, il est impératif de créer un projet où seront stockées les données. Cette étape passe par la création d’une base de données PostgreSQL

        a. Dans le menu Albion\New projet 
        b. Entrer le nom du nouveau projet
        c. Entrer le système de projection


Figure 6. - Menu importation des données


Figure 7. - Fenêtre de dialogue pour créer un projet


Figure 8. Fenêtre de dialogue sélection du système de projection


Importation des données de modélisation
=======================================

L’importation des données s’effectue automatiquement en allant dans Albion menu Import  Data. Sélectionner la directorie dans laquelle se trouvent toutes les données utilisées pour la modélisation. En fonction du nom des tables Albion reconnait la nature des données. Suivant la présence de mesures de diagraphie, et déviation, le chargement des données peut prendre un certain temps, dans le cas des données de ce tutoriel, compter 5 minutes….


Figure 9. Menu Importer les données


Une fois les données chargées, une visualisation des données en carte s’affiche dans la fenêtre principale de QGIS (voir figure ci-dessous).

Durant le chargement des données, Albion a calculé la trace des sondages à partir des mesures de déviations chargées, aussi il a effectué une triangulation de type de Delaunay à partir  des données têtes de sondages (fichier collar.txt).

Cette triangulation constitue le premier maillage  ou graphe primaire qui permet définir les relations de corrélation possible  de sondages à sondages. Cette triangulation permettra de construire les sections dans le chapitre suivant.


Figure 10. - Vue de la représentation de la triangulation à partir des données têtes de sondages


Figure 11 . - Fenêtre couche


Ajout de nouvelles couches 
==========================

Les couches présentent dans la fenêtre couches ne sont pas toujours présentent, il est parfois nécessaire d’en ajouter.



Figure 12. –Etape n°1 :   Aller dans le menu Couche/Ajouter une couche/Ajouter couche PostGis



Figure 13. -Etape n°2 : connecter la base de données. Appuyer sur nouveau. Etape n°3 Créer une nouvelle connexion Post GIS en remplissant les champs comme indiqués. Etape °4 tester la connexion à la base



Figure 14. Etape n°5 : connecter à la base de données. Etape n°6 sélectionner la couche que vous souhaitez ajouter, cliquer dur identifiant puis ajouter la couche

Afficher un log de sondage
==========================

A ce stade l’ensemble des données chargées dans Albion sont visualisables dans les différentes fenêtres.   

Un outil log permet une visualisation d’un log de sondage


Figure 15. - outil log de sondage


Figure 16. Sélectionner avec le curseur (croix) sur la vue en carte une tête de sondage, une fenêtre log apparait.



Calcul de passes minéralisées
*****************************

Généralité
==========

Une passe minéralisée (génératrice) est définie en fonction des paramètres économiques (cut off, ouverture de chantier et intervalle de dilution). Dans Albion le calcul des passes minéralisées  s’effectue à partir des données de radiométrie (champ [eu]) avec les enregistrements de mesures régulières (dans le cas de ce tutorial les données sont dans le fichier avp, elles sont renseignées suivant un pas de 10cm). 


Calcul de la passe minéralisée
==============================

La minéralisation telle qu’elle est utilisée pour une estimation, ou la simple compréhension géologique d’un gisement intègre des contraintes géologiques et technico-économiques via la définition de passes minéralisées ou génératrices sur les sondages disponibles.

Dans le cas du logiciel Albion les passes minéralisées  sont déterminées par :
    1. la coupure sur la radiométrie normalisée, tc (les AVP exprimés en ppm)
    2. l’épaisseur minimale d’une passe minéralisée, OC (exprimé en mètres)
    3. l’épaisseur minimale d’un intercalaire stérile, IC (exprimé en mètres)


La détermination des limites des génératrices utilise l’algorithme décrit par J.M. Marino (MARINO et al. 1988). Pour chaque sondage, les limites sont définies en maximisant par programmation dynamique la valeur récupérée :


Pour un sondage, la valeur est maximisée sur l’ensemble des indicatrices de chantiers vérifiant les contraintes sur les épaisseurs minimales. Il faut noter :
    1. l’optimisation est faite sur la valeur (i.e. accumulation – tc puissance) et non sur l’accumulation 
    2. Ce choix d’optimisation assure que la teneur moyenne de chacune des passes soit supérieure à la teneur de coupure.

Le calcul des génératrices mis en œuvre par le script reprend la publication initiale : les trois contraintes : 
  - Teneur moyenne de la passe,
  - Épaisseur des passes minéralisées,
  - Intercalaires stériles


Outil calcul des passes minéralisées
====================================


Figure 17. Menu calcul des passes minéralisées


Figure 18. - Fenêtre de dialogue permettant de renseigner les paramètres économique définissant  la minéralisation


Figure 19.  Table minéralisation issue du calcul des passes minéralisées. OC :ouverture de chantier, c'est la puissance de la passe minéralisée, accu est la teneur moyenne de la passe multiplié par la puissance,. Grade correspond à la teneur moyenne de la passe. Si cette table n’apparait pas, aller chercher cette couche suivant la procédure décrite au chapitre précédent.


Création des sections
*********************

A ce stade, il est nécessaire de créer les sections qui permettront de définir les plans de corrélation de sondages à sondages. Ces plans verticaux de corrélation sont directement guidés par le maillage effectué dès le chargement des données du projet (voir chapitre importation des données).

Nettoyage du maillage 
=====================

Les relations de connexion de sondages à sondages sont réalisé par le biais d’un maillage de type Delaunay, celui-ci permet de relier entres eux les sondages situé dans le voisinage le plus proche (distance euclidienne). Ce maillage réalisé automatiquement nécessite, pour être parfaitement rigoureux une étape de nettoyage à la périphérie du modèle, où quelques liens entres sondages doivent être effacés (voir figure ci-dessous).


Figure 20. - Exemple de deux sondages situés sur la périphérie du modèle, où leur connexion n'apporte aucune pertinence au modèle.


Figure 21. Exemple de triangles à effacer


Figure 22. Les triangles de la couche [cell] sont dans un premier temps sélectionnés, la couche [cell] doit être en mode edition, de manière à effacer ces triangles, la couche est ensuite sauvegardée.

Construction des sections (séquence mandala)
============================================

    Le mandala est un support de méditation. Il est le plus souvent représenté en deux dimensions mais on trouve également des mandalas réalisés en trois dimensions. Ce sont des œuvres d'art d'une grande complexité. Le méditant se projette dans le mandala avec lequel il se fond dans le yáng et yīn de la bouddhéité fondamentale. Disposées en plusieurs quartiers, les déités expriment la compassion, la douceur, d'autres l'intelligence, le discernement, d'autres encore l'énergie, la force de vaincre tous les aspects négatifs du subconscient samsarique. 
        D’après Wikipedia


Les sections vont mettre de contrôler et de modifier les volumes crées par Albion. Leur géométrie est un gage de qualité dans la construction volumétrique. Cette étape fait appel un travail manuel facile à réalisé une fois que l’on bien compris la problématique. Cette étape peut être assimilée à une scéance de mandala. Dans le cas des données du tutoriel il faut compter 30 minutes pour la réalisation des coupes NS et EW. 


Figure 23. Etape n°1 : Sélectionner dans le menu déroulant la direction de coupes que vous souhaitez créer en premier


Figure 24. La couche [cell] est en mode edition, deux triangles sont sélectionné,  ils vont servir à construire la première section EW


Figure 25. - Les deux triangles sélectionnés appuyer sur les touches Ctrl-Alt-K pour créer la première section


Figure 26. Création de section. Vous pouvez dès maintenant visualiser la première section, en allant dans le menu Create section


Figure 27. - Visualisation de la section. La section correspond à la bordure extérieure des 2 triangles. Utiliser les flèches de l'outils Albion pour faire défiler les coupes E-W


Figure 28. - Exemple d'une séance Mandala où 8 sections E-W ont été construites


Figure 29. Exemple d'une sélection d polygone maladroite pour construire une section EW dans la mesure où les deux extrémité de la coupe sont orientés N-S donc la corrélation des sondages extrêmes sera peu pertineente le long de la coupe EW


Création de  coupes
*******************


Introduction
============

Le graphe est l’élément de base des corrélations des passes géologiques dans Albion., il est la colonne vertébrale des coupes et des volumes. Il est constitué de segments [edge] reliant les passes, géologiques, nœud [node]. Dans Albion chaque objet géologique (minéralisation, formation, facies etc…) correspond à un graphe différent. Une minéralisation définit à partir d’un cut of @100 aura un graphe différent de la minéralisions défini au cut off @200.  


Figure 30. - Les principales étapes de construction du graphe et de coupes


Création d’un graphe (étape n°1 Figure 30)
==========================================


Figure 31. Menu création d'un nouveau graphe dans Albion


Création du graphe Formation D
==============================

Avant de représenter la minéralisation en coupe, il est nécessaire de représenter en coupe la formation géologique qui porte la minéralisation. Dans le cas de ce tutorial, il s’agit de la formation D présent dans la table formation.



Figure 32. - Indiquer le nom du graphe dans cette fenêtre de dialogue

La formation D, n’est pas une formation géologique contenue à l’intérieure d’une autre formation, ou portée par une autre formation, il s’agit d’une formation sans degré hiérarchique, sans graphe parent.   


Figure 33 . Dans le cas de la formation D pas de graphe parent. Laisser le champ vide, Appuyer sur OK


Figure 34 . Noter l'apparition d'un nouveau graphe dans la liste des graphes disponible


Création des nœuds [node] (étape n°2, Figure 30)
================================================

Un graphe est composé de nœuds, reste maintenant à créer ceux de la formation D


Figure 35. - Sélectionner la couche formation- bouton gauche de la souris, un menu s'ouvre aller dans Ouvrir la table d’attributs


Figure 36. Sélection des entitées formation dont le code est égal à 330


Figure 37. Copier dans le presse papier les nœuds de la formation D


Création des segments [edge] (étapes n°3 et 4)
==============================================


Figure 38. On colle dans la table [node], l'ensemble des passes formation de type Formation D


Figure 39. - l'ensemble des passes désignant la formation D sont placées dans la couche [node] et sont renseignées comme appartenant au graphe Form_D. On utilise le copier coller, la couche [node] doit être éditable le champ graph_id de la table [node] est mis à jour manuellement en indiquant le nom du graphe. Sauvegarder ensuite la couche [node]


Figure 40. La couche [Possible edge] est alors mise à jour de manière dynamique en fonction de la table [node] et de la table des paramètres de corrélation renseignés dans la table [metadata].


Modification du graphe de manière dynamique  (étape n°5 Figure 30)
==================================================================


Figure 41. La couche  [metadata] permet de modifier  les paramètres de corrélation de sondage afin de construire le graphe des formations géologiques


Figure 42. Sélectionner toutes les segments de graphes  du graphe  Form_D de la taple [possible_edge] avec le filte selection, puis copier ces enregistrements


Edition de la coupe en vue de modifier le graphe (Etape n°6, Figure 30)
=======================================================================

Figure 43. L'ensemble des edge de la couche [possible_edge] est collé dans la coupe [edge] afin d'être editésur une vue  en coupe


Figure 44. La couche [Section_Edge] est actualisée d'une manière dynamique et permet de visionner le graphe en coupe.


Figure 45. Le graphe peut être modifie, facilement en utilisant les outils de QGIS


Figure 46. Edition d'un graphe ajout d'un segment (edge)


Figure 47. - Représentation dynamique du polygone de corrélation


Ajout des terminaisons
======================

Les terminaisons  des polygones géologiques correspondent dans Albion à des éléments traités de manière indépendante de la construction du graphe. Elles sont construite automatiquement puis éditable avec les outils de QGIS.  


Figure 48. - Menu Création terminaisons


Figure 49. Exemple de polygones de type minéralisation sans fermeture


Figure 50. Exemple de polygones de type minéralisation avec fermeture. 


Figure 51. - Modification manuelle d'une terminaison


Figure 52. Exemple de superposition de polygone liée à la terminaison d'un polygone. La superposition est symbolisée par un polygone rouge situé dans la couche [current section_intersection]

Il peut arriver que la création d’une terminaison conduise à une superposition de deux polygones appartenant à un même objet géologique. Ces cas de figure ne permettent pas la création d’un modèle volumétrique par addition de volumes élémentaires parfaitement propre d’un point de vue topologique (existence de mur au sein du volume), ainsi Albion signale automatiquement ce genre de problème afin que l’utilisateur corrige manuellement le polygone en déplaçant la terminaison. L’ensemble de zone intersectée est visible dans la couche [current section_intersection]  


Création de volume
******************

Dans Albion, les volumes sont construits automatiquement à partir des coupes multidirectionnelles réalisées pendant l’étape construction de coupe. Le volume est construit à partir de volume élémentaires additionnels, où au droit de chaque passe géologique un volume élémentaire parfaitement contraint par la donnée de sondage et des coupes multidirectionnelles est calculé et défini par Albion. La somme de tous ces volumes élémentaires permet de constituer des volumes complexes à l’image de la représentation 3D des objets géologiques. Enfin soulignons le fait que l’optimisation de la triangulation héritée de la triangulation réalisée lors de l’étape de l’importation des données (voir § Importation d données) assure la parfaite cohérence géométrique du volume créer.   

Création du volume
==================
   
Figure 53. Menu création de volume


Figure 54. Représentation du volume 3D, possibilité d’afficher ou non des couches dans la barre d’outils d’Albion 

Edition  du volume
==================

Figure 55. - Outils d’édition du graphe dans la fenêtre 3D


Export du volume
================

Le volume construit sous Albion peut être exporté au format dxf et obj. Ce dernier format de fichier permet une utilisation des volumes construit sous Albion dans le logiciel libre Paraview. L’export des volumes s’effectue en utilisant le menu volume export. 


Figure 56. Menu Export volume


Figure 57. Exemple d'un export de volume au format dxf. Les tests de cohérence géométrique de triangulation indiquent un wirframe de qualité


Figure 58. Exemple de volume crée sous Albion et visualisable sous le logiciel Paraview


Annexe
######

Format des données de sondages
******************************


Introduction
============

Les données d’entrées sont de natures différentes, elles correspondent aussi bien à des données numériques d’enregistrements (exemple de données diagraphique), que des descriptions ou commentaires de données  géologiques. 

Les fichiers d’entrées sont des fichiers Ascii dont les noms, extensions et les formats de champs sont normalisés afin d’automatiser l’entrée des données. Cinq catégories de données ont été distinguées. Elles sont présentées dans la figure ci-dessous. Chaque catégorie peuvent contenir différentes tables qui sont décrites dans cette note. 

Figure 59 . Résumé des différents types de données nécessaires pour visualiser en carte, coupes et 3D des données de sondages avec  Albion 

Collar
======

La table collar correspond à la localisation X,Y,Z de la tête de sondage sur la surface topographique dans le système de projection indiqué par le modélisateur dans QGIS. Le fichier tête de sondage est unique, chaque sondage est définit par son nom holeid qui lui aussi est unique.


Figure 60. - Description du fichier "collar" (en rouge données obligatoires en bleu, données facultatives)


Déviation
=========

La géométrie du sondage sera définie à partir des données de déviation. Le fichier déviation correspond à l’enregistrement pente et azimut du sondage, pour un intervalle donné. Ce fichier avec le fichier collar permet de définir en coordonnées cartésienne  la représentation spatiale du sondage.


Figure 61. - Description du fichier "déviation" (en rouge données obligatoires en bleu, données facultatives)


Figure 62. – Représentation en coupe d’un sondage dévié 


Calcul des coordonnées des passes de sondages
*********************************************

C’est à partir du fichier déviation et du fichier collar que sont calculés les paramètres FromX,FromY,FromZ , ToX,ToY,ToZ (en vert dans les chapitres suivants). Ces paramètres sont nécéssaire pour la représentation en coupe les données de sondages. La méthode utilisée pour calculer les coordonnées des passes à partir des données de profondeur et de la position de la tête de sondage est présenté ci-dessous :

Balanced tangential method (HTTPS://WWW.SPEC2000.NET/19-DIP13.HTM)

The balanced tangential method uses the inclination and direction angles at the top and bottom of the course length to tangentially balance the two sets of measured angles. This method combines the trigonometric functions to provide the average inclination and direction angles which are used in standard computational procedures. The values of the inclination at WD2 and WD1 are combined in the proper sine-cosine functions and averaged. This method did not lend itself to hand calculations in the early days, but modern programmable scientific calculators make the job easy.

This technique provides a smoother curve which should more closely approximate the actual wellbore between surveys. The longer the distance between survey stations, the greater the possibility of error. The formula are:

 North =  SUM (MD2 - MD1) * ((Sin WD1 * Cos HAZ1 + Sin WD2 * Cos HAZ2) / 2)
  
 East =  SUM (MD2 - MD1) * ((Sin WD1 * Sin HAZ1 + Sin WD2 * Sin HAZ2) / 2)
  
 TVD = SUM ((MD2 - MD1) * (Cos WD2 + Cos WD1) / 2)


Where: 
  - East = easterly displacement (feet or meters) -- negative = West
  - HAZ1 = hole azimuth at top of course (degrees)
  - HAZ2 = hole azimuth at bottom of course (degrees)
  - MD1 = measured depth at top of course (feet or meters)
  - MD2 = measured depth at bottom of course (feet or meters)
  - North = northerly displacement (feet or meters) -- negative = South
  - TVD = true vertical depth (feet or meters)


Figure 63. - Déscription méthode calcul de coordonnées à partir des données de profondeur et données tête de sondage

Cas particulier d’absence de mesure déviation:
  A) Présence d’un sondage sans aucune mesure de déviation : -> une déviation fictive est attribuée le sondage est considéré comme parfaitement vertical,
  B)  Dans le cas « d’une absence ponctuelle » de mesure de déviation ( ex : aucune mesure entre 20-25m alors que les déviation ont été correctement mesurée sur le reste du sondage) -> la dernière déviation est utilisée comme mesure déviation manquante. Dans le cas où la donnée de déviation manquante est en tête de sondage, alors la déviation égale à  0 (verticale) sera utilisée.


Type de sondage
***************

La table renseigne la nature du sondage (Diamond drill, Reverse Circulation…) en fonction de la profondeur, permettant ainsi de gérer la présence de sondage mixte au sein d’un même sondage.



Figure 64. - Description du fichier "drillhole type" (en rouge données obligatoires)

Equipement de forage
********************

Afin de stabilisé le trou de sondage dans les premiers mètres et éviter tout risque déboulement, il est parfois nécessaire d’installé un casing, celui-ci est renseigné dans la table « casing » en fonction de la profondeur à laquelle il est installé.



Figure 65. - Description équipement "casing" (en rouge données obligatoires)



Récupération
************

On indique dans cette table le pourcentage de récupération d’un échantillon le long du sondage.


Figure 66. - Description table récupération, "recovery" (en rouge données obligatoires en bleu)


Radiométrie
***********

La mesure dont on dispose traditionnellement correspond à un enregistrement tous le 10cm de la mesure gamma elle est enregistrée à l’aide de sondes radiométrique divers (NGRS, GT etc…)



Figure 67. - Description du fichier "radiométrie"(en rouge données obligatoires en vert les données calculées par Albion)


Résistivité
***********

La mesure dont on dispose traditionnellement correspond à un enregistrement tous les 10cm mesure avec une sonde de résistivité.



Figure 68. - Description du fichier "résistivité"(en rouge données obligatoires en vert les données calculées par Albion)


Formation  (table pouvant être multiple)
****************************************

La table formation permet de décrire le long des sondages les formations géologiques reconnues par le géologue lors de la description de cuttings ou de carottes. Les différentes formations intersectées sont codifiées (numérique) avec un champ texte permettant des observations complémentaires sur les passes codées identifiées.


Figure 69. - Description du fichier "formation"(en rouge données obligatoire en vert les données calculées par Albion, en bleu données facultatives)


Lithologie 
**********

La table lithologie décrit les différentes lithologies intersectées lors de la foration. Les lithologies sont codifiées (numérique). Un champ texte permet de complété ces  observations par une description naturaliste de la roche.



Figure 70. - Description du fichier "lithologie"(en rouge données obligatoire en vert les données calculées par Albion, en bleu données facultatives)


Facies (table multiple)
***********************

Il s’agit ici de donnée de type facies, de la roche intersectée par sondage : 


Figure 71. - Description du fichier "facies" (en rouge données obligatoire en vert les données calculées par Albion, en bleu données facultatives)


