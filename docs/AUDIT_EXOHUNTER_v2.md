# ExoHunter v2.0 - Rapport d'Audit Technique et Scientifique

## 1. Vue d'ensemble du fonctionnement

### Architecture du pipeline

ExoHunter est un pipeline séquentiel de détection d'exoplanètes par la méthode des transits. Il opère en quatre étapes :

1. **Acquisition** (`loader.py`) : téléchargement des courbes de lumière via Lightkurve depuis les archives MAST (Kepler, TESS, K2). Les courbes de différentes périodes d'observation sont assemblées par `stitch()` avec normalisation par quarter/secteur.

2. **Nettoyage** (`cleaners.py`) : correction de la variabilité stellaire par filtre Savitzky-Golay (`flatten`), puis suppression des points aberrants par sigma-clipping (`remove_outliers`). Les tableaux masqués Astropy sont purgés en numpy pur pour éviter les incompatibilités.

3. **Détection itérative** (`detection.py`) : recherche de signaux périodiques par l'algorithme Box Least Squares (BLS). Chaque planète détectée est masquée avant de chercher la suivante. Des filtres anti-faux-positifs éliminent les alias de période, les binaires à éclipses (ratio pair/impair), et les artefacts (ratio négatif).

4. **Mesure physique** (`metrics.py`) : repliement de phase et binning en numpy pur, mesure de la profondeur du transit par médiane, conversion en rayon planétaire via la relation Rp/Rs = √δ.

### Hypothèses implicites

- La planète transite (inclinaison orbitale ≈ 90°).
- Le transit est modélisable par une forme rectangulaire (approximation BLS).
- La variabilité stellaire est lisse et de longueur d'onde supérieure à la fenêtre de lissage.
- Le flux est normalisé autour de 1.0 (pas de flux négatif ou centré sur zéro).
- L'étoile est unique (pas de binaire non résolue contaminant la photométrie).
- Le rayon stellaire fourni par l'utilisateur est correct.


## 2. Cas où l'outil fonctionne bien

### Conditions optimales

| Critère | Plage optimale | Justification |
|---------|---------------|---------------|
| Profondeur du transit | 100–2000 ppm | Au-dessus du bruit instrumental, en dessous du seuil d'écrasement par `flatten` |
| Période orbitale | 0.7–30 jours | Assez de transits sur 2-4 quarters, grille BLS de taille raisonnable |
| Nombre de transits | ≥ 5 | Statistique suffisante pour le BLS et la mesure de profondeur par binning |
| Type d'étoile | G/K calme | Variabilité stellaire faible, bien corrigée par le Savitzky-Golay |
| Mission | Kepler long cadence, TESS SPOC | Données bien calibrées, cadence régulière, bruit instrumental maîtrisé |

### Résultats validés

| Cible | Période trouvée | Rayon trouvé | Écart rayon | Verdict |
|-------|----------------|-------------|-------------|---------|
| Kepler-10b | 0.8375 j | 1.42 R⊕ | ~3% | Excellent |
| Kepler-20b | 3.696 j | 1.78 R⊕ | ~5% | Très bon |
| Kepler-20c | 10.854 j | 2.66 R⊕ | ~13% | Correct |
| Pi Men c (TESS) | 6.27 j | détecté | - | Cross-mission validé |

### Pourquoi ces cas fonctionnent

**Physiquement** : les transits de planètes rocheuses et mini-Neptunes autour d'étoiles calmes produisent des signaux de 100-1000 ppm, périodiques, stables d'un transit à l'autre. Le modèle box du BLS est une bonne approximation de cette forme de signal.

**Algorithmiquement** : le filtre Savitzky-Golay à fenêtre large (801 points ≈ 16 jours pour Kepler) élimine les tendances longues sans toucher les transits courts (durée typique 2-6 heures). Le sigma-clipping à σ=5 après `flatten` retire les éruptions stellaires sans couper les transits. Le BLS avec `frequency_factor=10` et `minimum_period=0.7j` produit une grille de recherche suffisamment fine pour des SNR > 7.


## 3. Limites et cas d'échec

### 3.1 Planètes non détectables

**Planètes non transitantes** : par construction, seules les planètes dont l'orbite est inclinée de manière à croiser la ligne de visée sont détectables. Pour une orbite aléatoire, la probabilité géométrique de transit est P = Rs/a. Pour une Terre à 1 UA d'une étoile solaire, P ≈ 0.5%. ExoHunter ne détecte donc qu'une infime fraction des planètes existantes. Ce n'est pas une limitation de l'outil mais de la méthode des transits elle-même.

**Planètes de type Terre en zone habitable** : une Terre autour d'une étoile G a une profondeur de transit de ~84 ppm et une période de ~365 jours. Le SNR sur un seul transit est de l'ordre de 1. Il faut ~10 transits (10 ans d'observation) pour atteindre un SNR de ~3 - toujours sous le seuil de détection de 7.1. Seul Kepler avec sa baseline de 4 ans et un traitement multi-quarter optimisé s'en approche. ExoHunter ne peut pas détecter ces planètes.

**Planètes à longue période (P > baseline/2)** : le BLS nécessite au minimum 2-3 transits pour détecter un signal. Si la période orbitale dépasse un tiers à la moitié de la baseline d'observation, la détection devient impossible ou non fiable.

### 3.2 Transits profonds (> 2000 ppm)

**Phénomène observé** : sur Kepler-7b (Jupiter chaud, transit ~8000 ppm), le rayon est sous-estimé de 47%.

**Cause** : le filtre Savitzky-Golay de `flatten` ajuste une courbe lisse à travers les données, y compris les transits profonds répétés. Quand la profondeur du transit est comparable à l'amplitude de la variabilité stellaire corrigée, le filtre "absorbe" une partie du transit dans sa tendance. La profondeur mesurée après `flatten` est systématiquement réduite.

**Quantification** : l'effet est négligeable pour δ < 1000 ppm, mesurable pour 1000 < δ < 3000 ppm, et sévère pour δ > 3000 ppm. Le biais croît avec le rapport durée_transit / window_length et avec le nombre de transits dans la fenêtre.

### 3.3 Étoiles actives

**Phénomène observé** : sur HAT-P-11 (étoile K active), le BLS détecte un sous-harmonique à 10× la vraie période.

**Cause** : les taches stellaires (spots) créent une modulation quasi-périodique de luminosité. `flatten` avec une fenêtre de 801 points ne peut pas corriger cette modulation si sa période est inférieure à la fenêtre. La modulation résiduelle interagit avec le signal de transit : la profondeur varie d'un transit à l'autre selon la position des spots. Le BLS, qui suppose une profondeur constante, ajuste mieux un modèle à longue période qui sélectionne uniquement les transits coïncidant avec les minima de spots.

**Étoiles concernées** : naines K et M actives, étoiles jeunes (< 1 Gyr), étoiles à forte rotation (Prot < 10 jours).

### 3.4 Systématiques instrumentales K2

**Phénomène observé** : sur K2-18, détection d'une période artéfactuelle à 15.47j au lieu de 32.9j.

**Cause** : après la perte de deux roues de réaction, K2 utilise la pression de radiation solaire pour se stabiliser. Il en résulte une oscillation de pointage de ~6 heures (roll motion) qui introduit une systématique photométrique périodique. `flatten` ne corrige pas ce type de bruit corrélé au pointage - il faudrait un correcteur dédié (SFF, EVEREST, ou un modèle de position du centroïde).

### 3.5 Systèmes avec TTV

**Phénomène observé** : sur Kepler-9 b/c, les périodes sont fausses de 10-12% et les rayons sous-estimés.

**Cause** : les Transit Timing Variations sont des décalages temporels des transits causés par l'interaction gravitationnelle entre planètes en résonance. Le BLS suppose une périodicité stricte. Quand les TTV sont de l'ordre de la durée du transit (~minutes à ~heures pour des systèmes fortement couplés comme Kepler-9), le repliement de phase n'aligne pas les transits correctement, ce qui dilue la profondeur mesurée et biaise la période.


## 4. Détection de plusieurs planètes (multi-transits)

### Méthode séquentielle

ExoHunter utilise une détection séquentielle : détecter la planète la plus forte, la masquer, chercher la suivante. Cette approche introduit plusieurs biais.

### Résidus de masquage

Pour une planète à période ultra-courte (ex: Kepler-10b, P=0.84j), le masquage génère des centaines de zones supprimées. Même avec un masque large (3× la durée), les bords de chaque transit laissent des micro-résidus qui s'additionnent. Le BLS retrouve ces résidus comme un signal de SNR significatif, consommant des itérations inutiles. Le filtre d'alias (ratio ≈ 1) gère ce cas mais au prix de 3-5 itérations supplémentaires.

### Confusion entre harmoniques et vraies planètes

Le filtre d'alias rejette les signaux dont le ratio de période avec une planète déjà trouvée est proche de 1, 2, ou 3. Mais certaines vraies planètes ont des rapports de période proches de ces valeurs (résonances orbitales 2:1, 3:1). Le pipeline actuel ne rejette que les ratios 1, 2, 3 - les sous-harmoniques 1/2, 1/3 ont été retirés de la liste après un faux rejet de Kepler-20b (ratio ~1/3 avec Kepler-20c).

### Masquage croisé dans les métriques

Lors de la mesure du rayon, chaque planète est mesurée après masquage des autres. Pour des planètes de périodes très différentes (ratio > 5), le masquage est inutile (les transits de l'autre planète tombent à des phases aléatoires et s'annulent dans la médiane) et potentiellement nuisible (il retire des points utiles). Le pipeline ignore le masquage dans ce cas.

### Ordre de détection

La détection séquentielle dépend de l'ordre. La planète de plus fort SNR est toujours détectée en premier. Si deux planètes ont des SNR proches, le masquage de la première peut altérer le signal de la seconde. Il n'y a pas de détection simultanée ni d'ajustement multi-planètes.


## 5. Problèmes de performance

### Goulot d'étranglement : le BLS

Le BLS est le composant le plus coûteux du pipeline. Sa complexité est O(N × M), où N est le nombre de points de la courbe et M le nombre de fréquences testées. M est déterminé par la formule :

M ≈ (1/Pmin − 1/Pmax) × baseline × frequency_factor

Pour une configuration typique Kepler (4 quarters, ~360 jours, frequency_factor=10, Pmin=0.7j) :
M ≈ 70 000 fréquences → ~2 minutes par itération

Pour 4 quarters avec frequency_factor=6 :
M ≈ 250 000 fréquences → ~6 minutes par itération

### Impact de la détection itérative

Chaque itération (planète trouvée, alias rejeté) relance un BLS complet. Un système avec 2 planètes et 3-5 alias consomme 5-7 itérations BLS, soit 10-40 minutes selon les paramètres.

### Optimisations disponibles

- `frequency_factor` : le levier le plus direct. Factor 10-15 divise le temps par 2-3 pour les signaux forts (SNR > 20).
- `minimum_period` : remonter de 0.7 à 1.0j retire ~30% de la grille.
- `min_transits=3` au lieu de 2 : réduit la plage de recherche d'un tiers.
- Le binning dans `metrics.py` est O(N × B) avec B le nombre de bins, négligeable face au BLS.


## 6. Exactitude et fiabilité des résultats

### Faux positifs

| Source | Risque | Mécanisme de protection |
|--------|--------|------------------------|
| Binaires à éclipses | Moyen | Filtre odd/even (ratio > 0.3, si ≥ 10 transits) |
| Artefacts instrumentaux | Moyen | Filtre ratio négatif (rejet inconditionnel) |
| Alias de période | Moyen | Filtre harmonique (ratio ≈ 1, 2, 3) |
| Bruit longue période | Faible | max_period = baseline / min_transits |
| Contamination stellaire | Non détecté | Aucune vérification de centroïde |

**Risque global de faux positifs : moyen.** Les binaires à éclipses avec peu de transits (< 10) échappent au filtre. La contamination par une étoile d'arrière-plan n'est pas vérifiée. Un candidat ExoHunter n'est pas une planète confirmée - il nécessite une validation par d'autres méthodes (vélocité radiale, imagerie, BLENDER, vespa).

### Faux négatifs

| Source | Risque | Impact |
|--------|--------|--------|
| Seuil SNR trop haut | Faible | Réglable par l'utilisateur (défaut 7.1) |
| `flatten` écrase le transit | Élevé pour transits profonds | Systématique, non corrigeable par paramètre |
| Sigma-clipping sur transits | Faible (corrigé) | `flatten` avant `remove_outliers` |
| Alias rejeté à tort | Faible | Seuls ratios 1, 2, 3 sont rejetés |

**Risque global de faux négatifs : moyen.** Principalement sur les transits profonds (> 2000 ppm) et les planètes à longue période.

### Robustesse globale

| Critère | Évaluation |
|---------|-----------|
| Précision des périodes | Élevée (< 1% d'erreur dans le domaine optimal) |
| Précision des rayons | Moyenne (3-13% dans le domaine optimal, > 30% hors domaine) |
| Stabilité face aux paramètres | Moyenne (sensible à mask_width, window_length) |
| Reproductibilité | Élevée (déterministe, pas de composante aléatoire) |


## 7. Problèmes liés aux télescopes / instruments

### Kepler (long cadence, 29.4 min)

Meilleure compatibilité. Données bien calibrées, cadence régulière, 4 ans de baseline. Le pipeline Kepler officiel produit des courbes PDCSAP déjà partiellement décontaminées. Les quarters 0-1 sont parfois plus bruités (phase de commissionnement).

### TESS (SPOC, 2 min / 30 min)

Compatible avec le filtre `mission="TESS", author="SPOC"`. Les secteurs de 27 jours limitent la baseline - seules les planètes de période < 9-13 jours sont détectables sur un secteur. La cadence à 2 minutes produit ~13 000 points par secteur, ce qui alourdit le BLS. Les pipelines non-SPOC (QLP, TESS-SPOC) produisent des flux centrés sur zéro qui cassent la normalisation.

### K2

Non compatible en l'état. La systématique de roll motion domine le signal et produit des faux positifs. Un module de correction SFF (Self-Flat-Fielding) ou l'utilisation de courbes EVEREST serait nécessaire.


## 8. Failles techniques du code

### Incompatibilité Astropy MaskedNDArray

Astropy ≥ 5.0 a introduit des `MaskedNDArray` qui se propagent silencieusement à travers les opérations Lightkurve. Certaines opérations (`fold`, `bin`, indexation `lc[mask]`) réintroduisent des masques même sur des données initialement purgées. Le pipeline contourne ce problème dans `mask_planet` (numpy pur) et `metrics.py` (repliement/binning manuels), mais tout nouvel appel à une méthode Lightkurve sur des données intermédiaires peut réintroduire le bug. C'est une fragilité structurelle qui nécessite une vigilance constante.

### Dépendance au rayon stellaire

Le rayon planétaire est proportionnel au rayon stellaire (Rp = √δ × Rs × 109.12). Aucune validation n'est faite sur la valeur fournie par l'utilisateur. Un rayon stellaire faux de 50% produit un rayon planétaire faux de 50%. Le pipeline devrait idéalement interroger un catalogue (NASA Exoplanet Archive, TIC) pour vérifier la cohérence.

### Pas d'estimation d'incertitude

Aucune barre d'erreur n'est calculée sur la période, le rayon, ou la profondeur. Le BLS fournit un SNR mais pas une incertitude sur la période. La profondeur est mesurée par une médiane sur un échantillon réduit sans estimation de la variance. Un résultat "1.42 R⊕" devrait être "1.42 ± 0.15 R⊕".

### Fallback par percentiles non robuste

Dans `metrics.py`, si les masques in-transit ou hors-transit sont vides, la profondeur est calculée via `np.nanpercentile(flux, 1)`. Ce fallback est fragile : le 1er percentile sur un échantillon bruité ne représente pas la profondeur du transit. Le fallback devrait utiliser `depth_bls` du dictionnaire BLS.


## 9. Recommandations d'amélioration

### Priorité critique

1. **Barres d'erreur** : implémenter un bootstrap sur la mesure de profondeur. Ré-échantillonner les points dans le transit 1000 fois, mesurer la profondeur à chaque fois, prendre l'écart-type comme incertitude.

2. **Detrending pré-masqué pour transits profonds** : effectuer une première passe BLS rapide (frequency_factor élevé), masquer les transits candidats, puis appliquer `flatten` sur la courbe masquée avant de relancer le BLS. C'est la méthode standard du pipeline Kepler officiel.

3. **Correcteur K2 (SFF)** : implémenter ou importer un module Self-Flat-Fielding qui utilise la position du centroïde pour corriger la systématique de roll motion.

### Priorité haute

4. **Processus gaussien (GP) pour étoiles actives** : remplacer `flatten` par un GP quand la variabilité stellaire est rapide (période de rotation < window_length). Les bibliothèques `celerite2` ou `george` sont adaptées.

5. **Test de centroïde** : vérifier que la source du transit est bien l'étoile cible et non un contaminant, en mesurant le décalage du centroïde pendant et hors transit.

6. **Interrogation automatique du rayon stellaire** : requêter le TIC (TESS Input Catalog) ou le Kepler Stellar Properties Catalog pour pré-remplir le rayon stellaire.

### Priorité moyenne

7. **Ajustement de modèle de transit** : remplacer la mesure de profondeur par binning par un ajustement Mandel-Agol (via `batman` ou `exoplanet`). Cela fournit directement Rp/Rs, l'inclinaison, et le paramètre de limb-darkening avec leurs incertitudes.

8. **Détection simultanée multi-planètes** : au lieu de la détection séquentielle, utiliser un ajustement multi-boîte ou TLS (Transit Least Squares) qui gère mieux les systèmes compacts.

9. **Export structuré des résultats** : produire un fichier JSON/CSV avec tous les paramètres, incertitudes, et métadonnées pour faciliter la comparaison avec les catalogues existants.


## 10. Conclusion - Documentation utilisateur

### Ce que l'outil fait bien

ExoHunter détecte de manière fiable les exoplanètes en transit avec une profondeur de 100 à 2000 ppm et une période de 0.7 à 30 jours, autour d'étoiles calmes de type F/G/K observées par Kepler ou TESS-SPOC. La précision sur la période est typiquement meilleure que 1%. La précision sur le rayon planétaire est de 3 à 15% dans ce domaine, dépendant du nombre de transits et de la qualité du rayon stellaire. Le pipeline est capable de détecter plusieurs planètes dans un même système, avec des filtres anti-faux-positifs pour les alias de période et les binaires à éclipses.

### Quand utiliser ExoHunter

- Recherche de planètes rocheuses et mini-Neptunes autour d'étoiles Kepler calmes.
- Exploration rapide de systèmes multi-planètes sur quelques quarters.
- Validation croisée de candidats connus sur des données TESS-SPOC.
- Outil pédagogique pour comprendre la détection de transit par BLS.

### Quand ne pas utiliser ExoHunter

- Détection de planètes telluriques en zone habitable (profondeur trop faible, période trop longue).
- Analyse d'étoiles actives (naines M, étoiles jeunes) sans module GP dédié.
- Caractérisation de Jupiters chauds (transit trop profond, biais de `flatten`).
- Données K2 sans correction préalable des systématiques de pointage.
- Publication scientifique sans validation complémentaire (pas de barres d'erreur, pas de test de centroïde, pas de vérification par vélocité radiale).

### Limitations connues

| Limitation | Impact | Contournement possible |
|-----------|--------|----------------------|
| Pas de barres d'erreur | Impossible d'évaluer la confiance | À implémenter (bootstrap) |
| `flatten` écrase les transits profonds | Rayon sous-estimé de 30-50% pour δ > 3000 ppm | Detrending pré-masqué |
| Étoiles actives | Fausses périodes (sous-harmoniques) | Module GP |
| Données K2 | Faux positifs instrumentaux | Correcteur SFF ou données EVEREST |
| TTV | Périodes et rayons biaisés | Analyse photodynamique (hors périmètre) |
| Contamination stellaire | Faux positifs non détectés | Test de centroïde |
| Dépendance Astropy ≥ 5.0 | Bug MaskedNDArray résurgent | Maintenir le contournement numpy pur |
