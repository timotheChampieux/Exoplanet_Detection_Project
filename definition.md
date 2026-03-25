# Glossaire Technique et Scientifique — ExoHunter

Ce document définit les termes clés utilisés dans le pipeline de détection d'exoplanètes par la méthode des transits. Il est destiné à faciliter la compréhension du projet pour tout chercheur ou ingénieur, quel que soit son domaine d'expertise initial.

---

# Astrophysique

## BJD (Barycentric Julian Date)
**Définition :** Jour julien corrigé pour le centre de masse du système solaire (le barycentre). Contrairement au temps terrestre, il supprime les variations de temps de parcours de la lumière dues au mouvement de la Terre autour du Soleil.
**Variantes missions :** Kepler utilise le BKJD (BJD − 2454833), TESS utilise le BTJD (BJD − 2457000). Ces décalages sont des conventions pour réduire le nombre de chiffres.
**Dans ExoHunter :** Unité de temps de l'axe `time` des objets `LightCurve`. Le pipeline travaille sur les valeurs numériques brutes sans se soucier de l'offset — seules les différences de temps comptent.

## Binaire à éclipses
**Définition :** Système de deux étoiles orbitant l'une autour de l'autre. Si leur plan orbital est aligné avec notre ligne de visée, elles s'éclipsent mutuellement, créant une chute de luminosité périodique.
**Pourquoi c'est un problème :** L'éclipse primaire (grande étoile cachée par la petite) imite un transit planétaire. L'éclipse secondaire (petite étoile cachée par la grande) a une profondeur différente — c'est cette asymétrie que le test odd/even exploite.
**Dans ExoHunter :** Principal faux positif, filtré par le ratio pair/impair dans `detection.py`.
**Alias :** EB, Eclipsing Binary.

## Contamination stellaire
**Définition :** Lumière parasite d'une étoile voisine (ou d'arrière-plan) qui se mélange au flux de l'étoile cible dans le même pixel du détecteur.
**Pourquoi c'est un problème :** Si l'étoile contaminante est elle-même une binaire à éclipses, sa variation de flux est diluée dans le flux total et peut imiter un transit planétaire peu profond sur l'étoile cible.
**Dans ExoHunter :** Non détecté. Nécessiterait un test de centroïde (vérifier que la position du centre lumineux se décale pendant le transit).

## Courbe de lumière
**Définition :** Série temporelle de la luminosité (flux) d'un objet céleste mesurée sur une période donnée. Chaque point est une mesure de flux à un instant donné.
**Dans ExoHunter :** La donnée d'entrée brute traitée par le pipeline. Téléchargée via Lightkurve depuis les archives MAST.
**Alias :** Light Curve, LC.

## Durée de transit
**Définition :** Temps (en heures ou jours) que met une planète pour traverser le disque stellaire vu depuis l'observateur. Dépend de la taille de l'étoile, du rayon orbital, et de l'inclinaison.
**Ordres de grandeur :** ~1-2h pour une planète ultra-courte, ~3-6h pour une planète type Terre, ~10-15h pour un Jupiter froid.
**Dans ExoHunter :** Paramètre extrait par le BLS, utilisé pour dimensionner le masque de transit et le binning.

## Époque (T0)
**Définition :** Moment précis du centre du premier transit observé dans les données. Sert de référence temporelle pour prédire les transits suivants.
**Dans ExoHunter :** Utilisé comme point de référence pour le repliement de phase dans `metrics.py` et pour le masquage dans `detection.py`.
**Alias :** Transit Time, Centre du transit.

## Exoplanète
**Définition :** Planète orbitant autour d'une étoile autre que le Soleil. Plus de 5 700 sont confirmées (mars 2025).
**Méthodes de détection :** Transits (ExoHunter), vélocités radiales, imagerie directe, microlentilles gravitationnelles, astrométrie.
**Dans ExoHunter :** L'objet de la recherche.

## Flux
**Définition :** Quantité d'énergie lumineuse reçue par unité de surface et de temps, mesurée en électrons/seconde par le détecteur CCD du télescope.
**Dans ExoHunter :** Valeur mesurée (axe Y) des courbes de lumière. Après normalisation, le flux de base est ~1.0 et un transit apparaît comme une baisse temporaire.

## Inclinaison orbitale
**Définition :** Angle entre le plan de l'orbite planétaire et le plan du ciel (perpendiculaire à la ligne de visée). Une inclinaison de 90° signifie que l'orbite est vue par la tranche.
**Pourquoi c'est important :** Un transit n'est visible que si l'inclinaison est suffisamment proche de 90°. La probabilité géométrique est P = Rs/a (rayon stellaire / demi-grand axe).
**Dans ExoHunter :** Hypothèse implicite — le pipeline ne peut détecter que les planètes qui transitent.

## Ingress / Egress
**Définition :** L'ingress est la phase d'entrée de la planète devant le disque stellaire (début de la chute du flux). L'egress est la phase de sortie (fin de la remontée du flux). Entre les deux se trouve le fond plat du transit.
**Dans ExoHunter :** Le paramètre `mask_width` inclut une marge pour couvrir ces phases et éviter les résidus de bord lors du masquage.

## L'assombrissement centre-bord (Limb Darkening)
**Définition :** Effet optique qui rend le centre du disque stellaire plus brillant que ses bords. Le gaz stellaire en bordure est vu sous un angle rasant, donc à travers des couches plus froides et moins lumineuses.
**Conséquence sur les transits :** Le transit a une forme en "U" arrondi plutôt qu'une boîte rectangulaire parfaite. La profondeur dépend de la position de la planète sur le disque stellaire.
**Dans ExoHunter :** Non modélisé. Le BLS utilise un modèle de boîte rectangulaire, ce qui introduit une légère sous-estimation de la profondeur. Un ajustement Mandel-Agol (bibliothèque `batman`) corrigerait cet effet.

## Missions spatiales

### Kepler (2009–2013)
Télescope spatial ayant observé ~150 000 étoiles dans une zone fixe du Cygne pendant 4 ans. Cadence longue : 29.4 minutes. A découvert ~2 700 exoplanètes confirmées. Données organisées en **quarters** (~90 jours chacun, Q0 à Q17).

### K2 (2014–2018)
Mission étendue de Kepler après la perte de 2 roues de réaction. Observe des champs différents pendant ~80 jours chacun. Données organisées en **campaigns** (C0 à C19). Systématique de pointage (roll motion) nécessitant une correction spécifique non implémentée dans ExoHunter.

### TESS (2018–présent)
Transiting Exoplanet Survey Satellite, balayant quasi tout le ciel. Cadence : 2 minutes (cibles prioritaires) ou 30 minutes (FFI). Données organisées en **secteurs** (~27 jours). Pipeline officiel : SPOC.

**Dans ExoHunter :** Les trois missions sont supportées via `loader.py`. K2 nécessite un correcteur dédié non encore implémenté.

## Période orbitale
**Définition :** Temps nécessaire à une planète pour effectuer une révolution complète autour de son étoile.
**Ordres de grandeur :** 0.5-1j (ultra-courte), 1-10j (courte), 10-100j (modérée), >100j (longue). La Terre : 365.25j.
**Dans ExoHunter :** Paramètre principal détecté par le BLS. La précision est typiquement < 1% dans le domaine optimal.

## Profondeur de transit (δ)
**Définition :** Fraction de lumière bloquée par la planète. Directement proportionnelle au rapport des surfaces : δ ≈ (Rp/Rs)². Une Terre devant le Soleil : ~84 ppm. Un Jupiter chaud : ~10 000 ppm.
**Dans ExoHunter :** Mesurée dans `metrics.py` par médiane du flux en transit vs hors transit, puis convertie en rayon planétaire.
**Alias :** Depth, Transit Depth.

## Rayon stellaire (Rs)
**Définition :** Taille physique de l'étoile hôte, exprimée en rayons solaires (R☉ = 696 000 km).
**Pourquoi c'est critique :** Le rayon planétaire est Rp = √δ × Rs × 109.12 R⊕. Une erreur de X% sur Rs produit exactement X% d'erreur sur Rp.
**Dans ExoHunter :** Paramètre d'entrée fourni par l'utilisateur. Aucune vérification automatique — à consulter sur le NASA Exoplanet Archive ou Simbad.

## Transit astronomique
**Définition :** Passage d'un corps céleste entre un observateur et une source lumineuse, occultant une fraction de cette source. La baisse de luminosité est périodique et de profondeur constante (à l'assombrissement centre-bord près).
**Dans ExoHunter :** La signature physique recherchée par le pipeline.

## Transit Timing Variations (TTV)
**Définition :** Décalages temporels des transits par rapport à une périodicité stricte, causés par l'interaction gravitationnelle entre planètes d'un même système. L'amplitude peut aller de quelques secondes à plusieurs heures.
**Pourquoi c'est un problème :** Le BLS suppose une périodicité stricte. Des TTV importants étalent le signal en phase, diluent la profondeur mesurée, et biaisent la période.
**Dans ExoHunter :** Non modélisé. Les systèmes à forte TTV (résonances 2:1 comme Kepler-9) produisent des résultats biaisés.

## Zone habitable
**Définition :** Plage de distances orbitales autour d'une étoile où l'eau liquide peut exister en surface. Dépend de la luminosité de l'étoile.
**Dans ExoHunter :** Non calculée. Pourrait être estimée à partir de la période orbitale et de la masse stellaire.

---

# Traitement du Signal et Statistiques

## Alias / Harmoniques
**Définition :** Signaux parasites apparaissant à des multiples ou des fractions de la fréquence réelle dans un périodogramme. Un signal à période P peut produire des pics à 2P, 3P, P/2, P/3.
**Cause :** L'échantillonnage discret et la forme non-sinusoïdale du transit (boîte rectangulaire) génèrent naturellement des harmoniques dans l'espace des fréquences.
**Dans ExoHunter :** Filtrés dans `planet_detector` par comparaison des ratios de période avec les valeurs 1, 2, 3 (tolérance 2%).

## BLS (Box Least Squares)
**Définition :** Algorithme de détection de signaux périodiques en forme de boîte rectangulaire dans une série temporelle. Pour chaque période testée, il cherche la position, la durée et la profondeur de boîte qui minimisent les résidus.
**Avantage :** Optimal pour les transits (forme quasi-rectangulaire), plus sensible que Lomb-Scargle pour ce type de signal.
**Limitation :** Suppose une profondeur constante (échoue avec TTV ou variabilité stellaire forte) et une forme de boîte (ne modélise pas le limb darkening).
**Complexité :** O(N × M) où N = points de données, M = fréquences testées.
**Dans ExoHunter :** Cœur de la détection via `lc.to_periodogram(method='bls')`.
**Référence :** Kovács, Zucker & Mazeh (2002).

## Binning
**Définition :** Regroupement de points de données en intervalles (bins) et calcul d'une valeur représentative (médiane ou moyenne) par bin. Réduit le bruit au prix d'une perte de résolution temporelle.
**Dans ExoHunter :** Utilisé dans `metrics.py` après le repliement de phase. La taille des bins est adaptée à la cadence de l'instrument et à la durée du transit (`_get_bin_size`).

## Bootstrap
**Définition :** Méthode statistique de ré-échantillonnage pour estimer l'incertitude d'une mesure. On tire aléatoirement N points parmi les N disponibles (avec remise), on recalcule la mesure, et on répète ~1000 fois. L'écart-type des résultats donne l'incertitude.
**Dans ExoHunter :** Non implémenté. Recommandé pour fournir des barres d'erreur sur la profondeur et le rayon.

## Detrending
**Définition :** Retrait des tendances à long terme d'une série temporelle pour stabiliser la ligne de base autour d'une valeur constante (1.0 après normalisation).
**Méthodes :** Savitzky-Golay (ExoHunter), processus gaussien (GP), spline, médiane glissante.
**Risque :** Un detrending trop agressif (fenêtre trop courte) absorbe les transits dans la tendance corrigée — c'est l'overfitting.
**Dans ExoHunter :** Effectué par `flatten(window_length)` dans `cleaners.py`.

## Faux positif
**Définition :** Signal détecté qui ressemble à un transit planétaire mais a une origine différente (binaire à éclipses, contamination stellaire, artefact instrumental).
**Dans ExoHunter :** Filtré partiellement par le test odd/even, le filtre de ratio négatif, et le filtre d'alias. Non filtré : contamination stellaire, binaires diluées.

## Faux négatif
**Définition :** Planète réelle qui existe dans les données mais n'est pas détectée par le pipeline (SNR insuffisant, transit écrasé par le detrending, période hors plage de recherche).
**Dans ExoHunter :** Risque élevé pour les transits profonds (> 2000 ppm, écrasés par `flatten`) et les planètes à longue période.

## Frequency factor
**Définition :** Paramètre contrôlant la densité de la grille de fréquences testées par le BLS. Un factor élevé produit une grille plus grossière (moins de fréquences, calcul rapide). Un factor bas produit une grille fine (plus de fréquences, calcul lent).
**Compromis :** Un factor trop élevé peut faire "sauter" le pic BLS d'un signal faible. Un factor trop bas augmente le temps de calcul sans gain pour les signaux forts.
**Dans ExoHunter :** Paramètre configurable dans le mode avancé (défaut : 10).

## Masquage de transit
**Définition :** Suppression des points de données situés dans et autour d'un transit détecté. Permet de chercher des signaux plus faibles cachés en dessous.
**Risque :** Un masque trop large retire des données utiles (réduit le SNR des planètes suivantes). Un masque trop étroit laisse des résidus que le BLS retrouve comme de faux signaux.
**Dans ExoHunter :** Implémenté en numpy pur dans `mask_planet`, avec un paramètre `mask_width` configurable (défaut : 3.0× la durée du transit).

## MaskedNDArray (bug Astropy)
**Définition :** Type de tableau introduit par Astropy ≥ 5.0 qui porte un masque booléen interne marquant les valeurs invalides. Certaines opérations Lightkurve (`fold`, `bin`, indexation) convertissent silencieusement les colonnes en ce type.
**Pourquoi c'est un problème :** Les opérations numpy standard (`np.nanmedian`, comparaisons) ne gèrent pas correctement ces masques internes, produisant l'erreur `cannot write to unmasked output` ou des valeurs incorrectes (0.0 au lieu de NaN).
**Dans ExoHunter :** Contourné en extrayant systématiquement les valeurs via `np.asarray(lc.flux.value, dtype=float)` et en évitant les méthodes Lightkurve pour les calculs critiques (masquage, binning).

## Normalisation
**Définition :** Division du flux par sa valeur médiane pour que la luminosité de base de l'étoile soit ~1.0. Permet de comparer des étoiles de luminosités différentes et d'exprimer la profondeur en fraction.
**Dans ExoHunter :** Effectuée dans `stitch(corrector_func=lambda x: x.normalize())` au moment de l'assemblage des quarters/secteurs.

## Odd/Even Depth Ratio
**Définition :** Rapport entre la profondeur des transits de rang impair et celle des transits de rang pair. Pour une vraie planète, ce ratio est ~1.0 (tous les transits ont la même profondeur). Pour une binaire à éclipses, l'éclipse primaire et secondaire ont des profondeurs différentes, produisant un ratio ≠ 1.
**Fiabilité :** Le test nécessite au minimum ~10 transits (5 pairs, 5 impairs) pour être statistiquement significatif. En dessous, la variance domine.
**Dans ExoHunter :** Calculé par `compute_stats` du BLS. Utilisé comme filtre dans `planet_detector` (seuil : |ratio − 1| > 0.3, désactivé si < 10 transits). Un ratio négatif est rejeté inconditionnellement (artefact).

## Outliers
**Définition :** Points de données aberrants causés par des rayons cosmiques frappant le détecteur, des éruptions stellaires (flares), ou des dysfonctionnements instrumentaux.
**Dans ExoHunter :** Supprimés via `remove_outliers(sigma)` après `flatten`. Le seuil sigma est configurable (défaut : 5).

## Périodogramme
**Définition :** Représentation graphique de la puissance (ou du SNR) d'un signal en fonction de la période (ou fréquence). Un pic dans le périodogramme indique une périodicité dans les données.
**Dans ExoHunter :** Produit par `to_periodogram(method='bls')`. Le pipeline extrait automatiquement le pic le plus fort.

## Phase / Repliement de phase
**Définition :** Transformation qui superpose tous les cycles orbitaux sur une seule période. Chaque point reçoit une coordonnée de phase φ = ((t − T0 + P/2) mod P) − P/2, comprise entre −P/2 et +P/2. Le transit apparaît centré à φ = 0.
**Intérêt :** En moyennant N transits, le bruit diminue d'un facteur √N tandis que le signal reste constant. La forme du transit émerge du bruit.
**Dans ExoHunter :** Calculé manuellement en numpy pur dans `metrics.py` pour éviter les problèmes de MaskedNDArray.

## ppm (parts per million)
**Définition :** Unité de mesure de profondeur de transit. 1 ppm = 10⁻⁶. 10 000 ppm = 1%.
**Ordres de grandeur :** Terre/Soleil ~84 ppm, Super-Terre ~200-500 ppm, Mini-Neptune ~500-2000 ppm, Jupiter chaud ~5000-20 000 ppm.
**Dans ExoHunter :** Unité d'affichage de la profondeur dans les résultats.

## Savitzky-Golay
**Définition :** Filtre numérique qui lisse les données en ajustant un polynôme local (généralement d'ordre 2 ou 3) sur une fenêtre glissante. Préserve mieux la forme des pics que la moyenne glissante.
**Paramètre critique :** `window_length` — doit être impair et supérieur à 3× la durée du transit le plus long attendu pour éviter d'écraser les transits.
**Dans ExoHunter :** Utilisé par `flatten(window_length)` dans `cleaners.py` (défaut : 801 points ≈ 16.7 jours pour Kepler long cadence).

## Sigma-clipping
**Définition :** Méthode de rejet itératif des valeurs dont l'écart à la médiane dépasse un seuil de σ fois l'écart-type. Simple mais efficace pour les distributions quasi-gaussiennes.
**Dans ExoHunter :** Utilisé par `remove_outliers(sigma)` dans `cleaners.py`. Appliqué après `flatten` pour éviter de couper les transits.

## SNR (Signal-to-Noise Ratio)
**Définition :** Rapport entre l'amplitude du signal (profondeur du transit) et l'écart-type du bruit photométrique. Un SNR plus élevé signifie un signal plus clair.
**Formule simplifiée :** SNR ≈ δ × √(N_transits) / σ_bruit, où δ est la profondeur, N le nombre de transits, et σ le bruit par point.
**Seuil de détection :** La communauté utilise SNR > 7.0-7.5 comme standard (probabilité de faux positif aléatoire < 10⁻¹²).
**Dans ExoHunter :** Critère principal de détection (seuil configurable, défaut : 7.1).

---

# Informatique et Bibliothèques

## Astropy
**Définition :** Bibliothèque Python fondamentale pour l'astronomie. Fournit la gestion des unités physiques, des coordonnées célestes, des formats de temps, et des structures de données tabulaires.
**Dans ExoHunter :** Utilisée en arrière-plan par Lightkurve. Source du bug MaskedNDArray contourné dans le pipeline.

## Lightkurve
**Définition :** Bibliothèque Python spécialisée pour l'analyse des courbes de lumière Kepler et TESS. Fournit le téléchargement des données, les objets `LightCurve` et `Periodogram`, et de nombreuses méthodes de traitement.
**Dans ExoHunter :** Cœur technologique du projet. Utilisé pour l'acquisition (`search_lightcurve`, `download_all`), l'assemblage (`stitch`), le nettoyage (`flatten`, `remove_outliers`), et la détection (`to_periodogram`).
**Version recommandée :** ≥ 2.4.

## MAST (Mikulski Archive for Space Telescopes)
**Définition :** Archive publique hébergée par le Space Telescope Science Institute contenant les données de Kepler, TESS, K2, Hubble, JWST et d'autres missions.
**Dans ExoHunter :** Source de toutes les données téléchargées par Lightkurve dans `loader.py`.

## NumPy
**Définition :** Bibliothèque de calcul numérique pour Python. Fournit les tableaux multidimensionnels et les opérations vectorisées.
**Dans ExoHunter :** Utilisée pour tous les calculs critiques en remplacement des méthodes Lightkurve/Astropy (masquage, repliement de phase, binning, mesure de profondeur).

## PDCSAP Flux
**Définition :** Pre-search Data Conditioning Simple Aperture Photometry. Flux déjà partiellement corrigé des systématiques instrumentales par le pipeline officiel de la mission (Kepler ou TESS-SPOC).
**Dans ExoHunter :** Type de flux téléchargé par défaut via Lightkurve.

## SPOC (Science Processing Operations Center)
**Définition :** Pipeline officiel de traitement des données TESS, opéré par le MIT et le NASA Ames Research Center. Produit les courbes de lumière calibrées.
**Dans ExoHunter :** Filtre `author="SPOC"` dans `loader.py` pour garantir des données homogènes sur TESS.

## Stitching
**Définition :** Assemblage de plusieurs segments de courbes de lumière (quarters Kepler, secteurs TESS, campaigns K2) en une série temporelle continue. Chaque segment est normalisé individuellement avant assemblage pour compenser les différences de calibration.
**Dans ExoHunter :** Effectué dans `loader.py` via `stitch(corrector_func=lambda x: x.normalize())`.

---

# Annexes : Concepts approfondis

## Le dilemme du window_length
Le `window_length` du filtre Savitzky-Golay est le compromis le plus critique du pipeline. Trop court : le filtre traite les transits répétés comme de la variabilité stellaire et les écrase (overfitting). Trop long : les tendances basse fréquence (variabilité stellaire, dérive instrumentale) ne sont pas corrigées, augmentant le bruit résiduel (underfitting).

**Règle pratique :** window_length > 3 × durée du transit le plus long attendu. Pour Kepler long cadence (29.4 min), 801 points ≈ 16.7 jours, adapté à la majorité des planètes avec des transits de quelques heures.

## L'impact de la cadence
La cadence d'observation détermine la résolution temporelle minimale. Un transit de 2 heures observé à 30 min de cadence ne contient que ~4 points dans le transit — la forme est à peine résolue. À 2 min de cadence (TESS short cadence), le même transit contient ~60 points, permettant une mesure précise de l'ingress/egress et de la profondeur.

**Dans ExoHunter :** La fonction `_get_bin_size` dans `metrics.py` interdit de binner plus fin que la cadence de l'instrument pour éviter de créer de faux détails.

## Pipeline de détection séquentielle
ExoHunter détecte les planètes une par une, de la plus forte (SNR le plus élevé) à la plus faible. Après chaque détection, le signal est masqué et la recherche reprend sur la courbe résiduelle. Cette approche est simple et robuste mais introduit un biais : le masquage de la première planète peut altérer le signal des suivantes, et l'ordre de détection dépend des SNR relatifs.

**Alternative :** Détection simultanée multi-planètes (TLS, modèle photodynamique), non implémentée.

## Méthodes de validation d'un candidat
Un candidat ExoHunter n'est pas une planète confirmée. La validation complète nécessite :
- **Vélocité radiale :** mesurer le mouvement de l'étoile induit par la planète pour confirmer sa masse.
- **BLENDER/vespa :** analyse statistique pour éliminer les scénarios de faux positifs.
- **Test de centroïde :** vérifier que le transit provient bien de l'étoile cible.
- **Observation multi-bande :** vérifier que la profondeur est achromatique (même profondeur en infrarouge et en visible), ce qui élimine les binaires à éclipses diluées.
