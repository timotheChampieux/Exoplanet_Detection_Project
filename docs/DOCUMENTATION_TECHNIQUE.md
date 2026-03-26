# ExoHunter - Documentation Technique

## 1. Introduction technique

ExoHunter est un pipeline de détection d'exoplanètes par la méthode des transits photométriques. Il ingère des séries temporelles de flux stellaire (courbes de lumière) issues des missions Kepler et TESS, les nettoie, y recherche des signaux périodiques en forme de boîte via l'algorithme Box Least Squares (BLS), et caractérise les candidats détectés en termes de paramètres physiques (période orbitale, rayon planétaire, profondeur de transit).

Le pipeline est conçu pour la détection itérative multi-planètes : après chaque détection, le signal est masqué et la recherche reprend sur la courbe résiduelle.

> Pour les définitions des termes techniques (BLS, SNR, transit, detrending, etc.), consulter `docs/GLOSSAIRE_EXOHUNTER.md`.
> Pour le domaine de validité et les limitations détaillées, consulter `docs/AUDIT_EXOHUNTER.md`.

---

## 2. Architecture globale

### Diagramme du pipeline

```
                    ┌──────────────┐
                    │   main.py    │  Interface utilisateur + orchestration
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌──────────────┐ ┌───────────┐ ┌────────────┐
    │  loader.py   │ │cleaners.py│ │detection.py│
    │  (data/)     │ │(process/) │ │(analysis/) │
    └──────┬───────┘ └─────┬─────┘ └──────┬─────┘
           │               │              │
           │               │              ▼
           │               │       ┌────────────┐
           │               │       │ metrics.py │
           │               │       │(analysis/) │
           │               │       └────────────┘
           ▼               ▼              ▼
        Archives        Courbe         Candidats
         MAST          nettoyée      caractérisés
```

### Modules

| Module | Chemin | Responsabilité |
|--------|--------|---------------|
| `main.py` | `src/main.py` | Point d'entrée, saisie des paramètres, orchestration du pipeline, affichage des résultats |
| `loader.py` | `src/data/loader.py` | Téléchargement des courbes de lumière, assemblage multi-segments, normalisation |
| `cleaners.py` | `src/processing/cleaners.py` | Detrending (Savitzky-Golay), sigma-clipping, purge des MaskedNDArray Astropy |
| `detection.py` | `src/analysis/detection.py` | Périodogramme BLS, détection itérative, masquage, filtres anti-faux-positifs |
| `metrics.py` | `src/analysis/metrics.py` | Repliement de phase, binning, mesure de profondeur, calcul du rayon planétaire |

---

## 3. Pipeline de traitement - Détail par étape

### Étape 1 : Acquisition - `loader.download_target_data()`

```python
def download_target_data(star_name: str, period_index=None, author: str = "Kepler") -> lk.LightCurve:
    """
    Recherche, télécharge et assemble les courbes de lumière d'une étoile cible.

    La fonction adapte automatiquement la requête à la mission :
    - Kepler : filtre par ``quarter``
    - TESS : filtre par ``sector`` avec pipeline ``SPOC``
    - K2 : filtre par ``campaign``

    Les segments sont assemblés par ``stitch()`` avec normalisation individuelle
    (``corrector_func=lambda x: x.normalize()``) pour compenser les discontinuités
    de calibration entre segments.

    :param star_name: Nom de l'étoile (ex: "Kepler-10", "pi Men").
    :type star_name: str
    :param period_index: Numéro(s) de quarter/secteur/campaign. ``None`` = tout télécharger.
    :type period_index: int, list[int] ou None
    :param author: Nom de la mission ("Kepler", "TESS", "K2").
    :type author: str
    :return: Courbe de lumière assemblée et normalisée.
    :rtype: lk.LightCurve
    :raises ValueError: Si aucune donnée n'est trouvée pour la cible.
    """
```

**Source de données** : archives MAST via Lightkurve. Le flux utilisé est le PDCSAP (Pre-search Data Conditioning Simple Aperture Photometry), déjà partiellement corrigé des systématiques instrumentales par le pipeline officiel de la mission.

**Choix technique - séparation mission/author** : pour TESS, le paramètre `author="SPOC"` est utilisé dans `search_lightcurve` pour ne garder que les courbes du pipeline officiel. Sans ce filtre, Lightkurve retourne aussi les courbes QLP et TESS-SPOC dont certaines sont centrées sur zéro et cassent la normalisation.

### Étape 2 : Nettoyage - `cleaners.lc_cleaner()`

```python
def lc_cleaner(lc: lk.LightCurve, window_length: int = 801, sigma: float = 5) -> lk.LightCurve:
    """
    Nettoie la courbe de lumière par correction de la variabilité stellaire et rejet des outliers.

    Deux opérations successives, dans cet ordre précis :

    1. **flatten** (Savitzky-Golay) : ajuste un polynôme local glissant sur la courbe
       et divise le flux par cette tendance. La variabilité stellaire lente est supprimée,
       le flux est recentré autour de 1.0.

    2. **remove_outliers** (sigma-clipping) : élimine les points dont le flux s'écarte
       de plus de ``sigma`` écarts-types de la médiane.

    .. warning::
        L'ordre est critique. Inverser les opérations (outliers avant flatten)
        risque de supprimer les transits profonds qui apparaissent comme des outliers
        sur la courbe brute non corrigée.

    La fonction termine par un appel à ``_strip_astropy_masks()`` qui convertit
    les ``MaskedNDArray`` d'Astropy en tableaux numpy purs, contournant le bug
    ``cannot write to unmasked output`` introduit par Astropy >= 5.0.

    :param lc: Courbe de lumière brute assemblée.
    :type lc: lk.LightCurve
    :param window_length: Nombre de points de la fenêtre Savitzky-Golay. Doit être impair
                          et > 3× la durée du transit le plus long attendu.
    :type window_length: int
    :param sigma: Seuil de rejet en nombre d'écarts-types.
    :type sigma: float
    :return: Courbe nettoyée avec tableaux numpy purs.
    :rtype: lk.LightCurve
    """
```

**Fonction interne - `_strip_astropy_masks()`** :

```python
def _strip_astropy_masks(lc: lk.LightCurve) -> lk.LightCurve:
    """
    Convertit les colonnes MaskedNDArray d'Astropy en tableaux numpy standard.

    Astropy >= 5.0 convertit silencieusement les colonnes ``flux`` et ``flux_err``
    en ``MaskedNDArray`` lors de certaines opérations (``stitch``, ``flatten``,
    ``remove_outliers``). Ces masques internes ne sont pas visibles par ``np.isnan``
    et provoquent l'erreur ``cannot write to unmasked output`` dans les opérations
    downstream.

    :param lc: Courbe potentiellement contaminée par des MaskedNDArray.
    :type lc: lk.LightCurve
    :return: Courbe avec des ndarray purs (float64, C-contiguous).
    :rtype: lk.LightCurve
    """
```

### Étape 3 : Détection - `detection.planet_detector()`

```python
def planet_detector(lc: lk.LightCurve, max_planets=10, frequency_factor: int = 10,
                    minimum_period: float = 0.7, snr_threshold: float = 7.1,
                    mask_width: float = 3.0, max_alias: int = 5,
                    min_transits: int = 3) -> list:
    """
    Exécute une recherche itérative d'exoplanètes par déshabillage de la courbe de lumière.

    Cette fonction est le moteur de détection principal. Elle cherche le signal périodique
    le plus fort, vérifie sa validité via des tests de rapport signal/bruit (SNR), d'alias
    harmoniques et de symétrie de transit (Odd/Even depth ratio). Si le signal est validé,
    il est ajouté à la liste des candidats et masqué de la courbe de lumière pour permettre
    la détection de signaux plus faibles lors de l'itération suivante.

    .. note::
        La fonction intègre trois filtres de protection :
        1. **Filtre d'Alias** : Empêche de compter plusieurs fois la même planète
           si le BLS accroche une harmonique (ratio ≈ 1, 2, ou 3 avec une planète déjà trouvée).
        2. **Filtre Odd/Even** : Rejette les binaires à éclipses dont les transits pairs et
           impairs ont des profondeurs statistiquement différentes (|ratio - 1| > 0.3).
           Désactivé si < 10 transits (statistique insuffisante).
        3. **Filtre ratio négatif** : Rejette inconditionnellement les signaux dont le ratio
           pair/impair est négatif (artefact, physiquement impossible).

    :param lc: La courbe de lumière nettoyée et normalisée.
    :type lc: lk.LightCurve
    :param max_planets: Nombre maximum de planètes uniques à rechercher.
    :type max_planets: int
    :param frequency_factor: Densité de la grille de fréquences du BLS. Plus élevé = grille
                             plus grossière = calcul plus rapide. Voir section Paramètres.
    :type frequency_factor: int
    :param minimum_period: La période orbitale la plus courte à explorer (en jours).
    :type minimum_period: float
    :param snr_threshold: Le seuil de détection en dessous duquel la recherche s'arrête.
    :type snr_threshold: float
    :param mask_width: Multiplicateur de la durée du transit pour la largeur du masquage.
    :type mask_width: float
    :param max_alias: Nombre maximum d'alias consécutifs avant l'arrêt de la recherche.
    :type max_alias: int
    :param min_transits: Nombre minimum de transits pour définir la période maximale
                         cherchée (max_period = baseline / min_transits).
    :type min_transits: int
    :return: Liste de dictionnaires, chacun contenant les paramètres d'un candidat validé.
    :rtype: list[dict]

    **Exemple :**

    .. code-block:: python

        candidates = planet_detector(
            lc_clean,
            max_planets=3,
            snr_threshold=8.5,
            minimum_period=0.5
        )

        for p in candidates:
            print(f"P={p['period']:.3f} j, SNR={p['snr']:.1f}")
    """
```

**Fonction interne - `_run_bls_analysis()`** :

```python
def _run_bls_analysis(lc: lk.LightCurve, frequency_factor: int = 10,
                      minimum_period: float = 0.7, min_transits: int = 3) -> dict:
    """
    Exécute un périodogramme BLS sur la courbe de lumière et extrait les statistiques
    du meilleur pic.

    Construit une grille de fréquences entre ``minimum_period`` et
    ``baseline / min_transits``, exécute le BLS, puis appelle ``compute_stats()``
    pour obtenir la profondeur, le ratio pair/impair et d'autres diagnostics.

    .. warning::
        Si la courbe contient moins de 50 points, la fonction retourne un dictionnaire
        nul (SNR=0) sans exécuter le BLS, pour éviter les erreurs numériques.

    :param lc: Courbe de lumière à analyser.
    :type lc: lk.LightCurve
    :param frequency_factor: Densité de la grille de fréquences.
    :type frequency_factor: int
    :param minimum_period: Période minimale de recherche (jours).
    :type minimum_period: float
    :param min_transits: Nombre minimum de transits pour la période maximale.
    :type min_transits: int
    :return: Dictionnaire contenant les clés ``period``, ``transit_time``, ``duration``,
             ``snr``, ``max_power``, ``depth_bls``, ``odd_even_ratio``.
    :rtype: dict
    """
```

**Fonction - `mask_planet()`** :

```python
def mask_planet(lc: lk.LightCurve, planet_info: dict,
               mask_width: float = 3.0) -> lk.LightCurve:
    """
    Masque les transits d'une planète détectée pour permettre la recherche de signaux plus faibles.

    Le masquage est réalisé entièrement en numpy pur (pas d'appel à ``create_transit_mask()``
    ni d'indexation Lightkurve) pour contourner le bug Astropy MaskedNDArray.

    Le calcul du masque utilise le repliement de phase :
    ``phase = (time - t0 + P/2) % P - P/2``. Tout point avec ``|phase| < duration × mask_width``
    est supprimé.

    .. note::
        Pour les alias de ratio ≈ 1 (résidus du même signal), la durée est remplacée
        par celle de la planète originale avant l'appel, car le BLS sur un résidu peut
        retourner une durée aberrante qui vide la courbe.

    :param lc: Courbe de lumière à masquer.
    :type lc: lk.LightCurve
    :param planet_info: Dictionnaire issu de ``_run_bls_analysis`` contenant
                        ``period``, ``transit_time``, ``duration``.
    :type planet_info: dict
    :param mask_width: Multiplicateur de la durée du transit. 3.0 = marge de 3× la durée
                       de chaque côté du centre du transit.
    :type mask_width: float
    :return: Courbe de lumière dont les points en transit sont supprimés.
    :rtype: lk.LightCurve
    """
```

### Étape 4 : Métriques - `metrics.analyze_planets_metrics()`

```python
def analyze_planets_metrics(lc: lk.LightCurve, planets_list: list,
                            star_radius: float = 1,
                            points_per_transit: int = 70) -> list:
    """
    Calcule les paramètres physiques (rayon, profondeur) pour chaque candidat détecté.

    Pour chaque planète de la liste :

    1. Masque les signaux des autres planètes (sauf si leur ratio de période > 5,
       car le signal se moyenne en phase et le masquage est inutile voire nuisible).
    2. Replie la courbe en phase sur la période du candidat.
    3. Bine les données en numpy pur avec une taille adaptée à la cadence et à la durée.
    4. Mesure la profondeur δ par médiane du flux en transit vs hors transit.
    5. Calcule le rayon planétaire : ``Rp = √δ × Rs × 109.12 R⊕``.

    .. warning::
        Le repliement de phase et le binning sont réalisés entièrement en numpy pur.
        Les méthodes Lightkurve ``fold()`` et ``bin()`` réintroduisent des MaskedNDArray
        qui corrompent les calculs de médiane.

    :param lc: Courbe de lumière nettoyée (utilisée comme référence pour chaque mesure).
    :type lc: lk.LightCurve
    :param planets_list: Liste de dictionnaires candidats issus de ``planet_detector``.
    :type planets_list: list[dict]
    :param star_radius: Rayon de l'étoile hôte en rayons solaires.
    :type star_radius: float
    :param points_per_transit: Nombre de bins souhaité dans la durée du transit.
    :type points_per_transit: int
    :return: La même liste enrichie des clés ``rayon_terrestre``, ``rayon_km``, ``depth_ppm``.
    :rtype: list[dict]
    """
```

**Fonction interne - `_get_bin_size()`** :

```python
def _get_bin_size(lc: lk.LightCurve, planet_info: dict,
                  points_per_transit: int) -> float:
    """
    Calcule la taille optimale des bins pour le repliement de phase.

    Garantit que le binning est assez fin pour résoudre le transit (``duration / period / points_per_transit``)
    mais jamais plus fin que la cadence de l'instrument (sinon on crée de faux détails).

    :param lc: Courbe de lumière pour mesurer la cadence.
    :type lc: lk.LightCurve
    :param planet_info: Dictionnaire contenant ``duration`` et ``period``.
    :type planet_info: dict
    :param points_per_transit: Nombre de bins souhaité dans la durée du transit.
    :type points_per_transit: int
    :return: Taille du bin en unité de phase (fraction de période).
    :rtype: float
    """
```

---

## 4. Algorithmes - Décisions de conception

### Détection séquentielle vs simultanée

Le pipeline utilise une détection **séquentielle** : trouver le signal le plus fort, le masquer, recommencer. L'alternative (ajustement multi-planètes simultané) est plus précise mais considérablement plus complexe et coûteuse.

**Conséquences** :
- L'ordre de détection dépend des SNR relatifs (le plus fort en premier).
- Le masquage de la planète N peut altérer le signal de la planète N+1.
- Les résidus de masquage d'une planète ultra-courte (centaines de transits) peuvent dominer le signal de planètes à longue période, nécessitant un `mask_width` élevé (3.0×) et une tolérance d'alias élevée.

### Masquage en numpy pur

Les opérations Lightkurve `lc[~mask]` et `create_transit_mask()` passent par les internes d'Astropy `TimeSeries.__getitem__` qui convertissent les colonnes en `MaskedNDArray`. Ce type de tableau résiste à `np.asarray()` (les valeurs masquées deviennent 0.0, pas NaN) et provoque l'erreur `cannot write to unmasked output` au tour suivant.

Le contournement consiste à extraire les trois colonnes (`time`, `flux`, `flux_err`) en `np.ndarray` via `.value` avant toute opération, et à reconstruire un `LightCurve` à partir de tableaux purs. Ce pattern est appliqué dans `mask_planet()`, `_strip_astropy_masks()`, et le binning de `metrics.py`.

### Filtre d'alias - choix des harmoniques

Seuls les ratios 1, 2, 3 sont testés. Les sous-harmoniques (0.5, 1/3) ont été retirés après un faux rejet de Kepler-20b (ratio ~1/3 avec Kepler-20c) - certaines vraies planètes ont des rapports de période proches de fractions simples par coïncidence ou par résonance orbitale.

### Mesure de profondeur - zones in/out

La profondeur est mesurée par le rapport des médianes entre deux zones de phase :
- **Zone in-transit** : |phase| < 0.4 × phase_duration (80% central, évite les bords d'ingress/egress)
- **Zone hors-transit** : 0.6 × phase_duration < |phase| < 1.5 × phase_duration (zone proche mais hors transit)

La zone hors-transit est volontairement proche du transit pour minimiser l'influence des tendances résiduelles à longue échelle de phase.

---

## 5. Structures de données

### Dictionnaire candidat

Chaque planète détectée est représentée par un dictionnaire enrichi au fil du pipeline :

```python
# Après _run_bls_analysis() :
{
    "period": float,          # Période orbitale (jours)
    "transit_time": float,    # Époque du premier transit (BKJD/BTJD)
    "duration": float,        # Durée du transit (jours)
    "snr": float,             # Rapport signal/bruit du pic BLS
    "max_power": float,       # Puissance maximale du périodogramme
    "depth_bls": float,       # Profondeur estimée par le modèle BLS (flux relatif)
    "odd_even_ratio": float   # Ratio profondeur transits impairs / pairs
}

# Après analyze_planets_metrics(), clés ajoutées :
{
    ...
    "rayon_terrestre": float,  # Rayon planétaire (R⊕)
    "rayon_km": float,         # Rayon planétaire (km)
    "depth_ppm": float         # Profondeur mesurée (ppm)
}
```

### Flux de données entre modules

```
download_target_data() → lk.LightCurve (brut)
        │
lc_cleaner() → lk.LightCurve (nettoyé, numpy pur)
        │
planet_detector() → list[dict] (candidats avec période, SNR, durée)
        │
analyze_planets_metrics() → list[dict] (candidats + rayon, profondeur)
```

---

## 6. Paramètres configurables

Tous les paramètres sont exposés dans `main.py` via le mode avancé. Leur valeur par défaut est propagée via les signatures des fonctions.

| Paramètre | Défaut | Module | Impact |
|-----------|--------|--------|--------|
| `sigma` | 5.0 | `cleaners` | Seuil de rejet des outliers. ↓ = plus agressif, risque de couper des transits profonds. ↑ = plus permissif, garde plus de bruit. |
| `window_length` | 801 | `cleaners` | Fenêtre Savitzky-Golay (points). Doit être > 3× durée du transit. ↓ = risque d'écraser les transits. ↑ = laisse des tendances longues. |
| `frequency_factor` | 10 | `detection` | Densité de la grille BLS. ↑ = plus rapide, grille plus grossière. ↓ = plus lent, meilleure résolution. Impact direct ×2 sur le temps de calcul. |
| `minimum_period` | 0.7 j | `detection` | Période minimale de recherche. ↓ = détection de planètes ultra-courtes, mais grille BLS beaucoup plus grande. |
| `snr_threshold` | 7.1 | `detection` | Seuil de détection. ↓ = plus de candidats + plus de faux positifs. ↑ = moins de faux positifs, risque de rater des signaux faibles. |
| `mask_width` | 3.0 | `detection` | Multiplicateur de la durée pour le masquage. ↓ = résidus de transit polluent la recherche suivante. ↑ = perte de données. |
| `max_alias` | 5 | `detection` | Tolérance d'alias consécutifs. ↑ = nécessaire si planète ultra-courte en premier (beaucoup de résidus). |
| `min_transits` | 3 | `detection` | Nombre minimum de transits. Détermine `max_period = baseline / min_transits`. 2 = détection longue période mais risque de faux positifs. |
| `points_per_transit` | 70 | `metrics` | Résolution du binning. ↑ = plus précis mais nécessite beaucoup de transits. ↓ = utilisable avec peu de transits. |
| `star_radius` | 1.0 | `metrics` | Rayon stellaire (R☉). Erreur de X% = X% d'erreur sur le rayon planétaire. |

---

## 7. Performance

### Complexité algorithmique

| Composant | Complexité | Variable dominante |
|-----------|-----------|-------------------|
| BLS | O(N × M) | N = points de données, M = fréquences testées |
| Masquage | O(N) | Linéaire en nombre de points |
| Binning | O(N × B) | B = nombre de bins (négligeable vs BLS) |
| Pipeline complet | O(I × N × M) | I = nombre d'itérations (planètes + alias) |

### Temps de calcul mesurés

| Configuration | Points grille | Temps/itération | Total (2 planètes + 3 alias) |
|---------------|-------------:|----------------:|-----------------------------:|
| 2 quarters, ff=10 | ~70k | ~1 min | ~5 min |
| 4 quarters, ff=10 | ~140k | ~3 min | ~15 min |
| 4 quarters, ff=6 | ~250k | ~6 min | ~30 min |

Le `frequency_factor` est le levier principal de performance.

---

## 8. Limites techniques

> Un rapport d'audit complet est disponible dans `docs/AUDIT_EXOHUNTER.md`.

**Résumé des cas d'échec validés par les tests :**

| Cas | Cible testée | Symptôme | Cause racine |
|-----|-------------|----------|-------------|
| Transit profond | Kepler-7b | Rayon -47% | `flatten` absorbe le transit dans la tendance |
| Étoile active | HAT-P-11 | Fausse période (×10) | Spots stellaires non corrigés |
| Données K2 | K2-18 | Fausse période | Systématique de roll non corrigée |
| Forte TTV | Kepler-9 | Période -10% | BLS suppose périodicité stricte |
| Longue période | Kepler-10c (2 quarters) | Non détectée | < 3 transits, SNR insuffisant |

---

## 9. Dépendances

| Bibliothèque | Version min. | Rôle dans le pipeline |
|-------------|-------------|----------------------|
| `lightkurve` | ≥ 2.4 | Téléchargement des données, objets LightCurve, périodogramme BLS |
| `numpy` | ≥ 1.24 | Calculs numériques, contournement MaskedNDArray |
| `astropy` | ≥ 5.0 | Sous-dépendance de Lightkurve (gestion du temps, unités) |
| `matplotlib` | ≥ 3.5 | Visualisations dans le notebook de démonstration |

Installation :

```bash
pip install lightkurve numpy matplotlib
```

`astropy` et `scipy` sont installés automatiquement comme dépendances de `lightkurve`.

---

## 10. Guide développeur

### Ajouter un nouveau filtre anti-faux-positifs

Les filtres sont dans `planet_detector()`, entre le test SNR (`if result["snr"] > snr_threshold`) et `planets_found.append(result)`. Chaque filtre suit le même pattern :

```python
# 1. Calculer le critère
critere = ...

# 2. Tester
if critere_invalide:
    logger.warning(f"Signal rejeté - raison : {critere}")
    current_lc = mask_planet(current_lc, result, mask_width=mask_width)
    continue

# 3. Si validé, le signal tombe vers planets_found.append()
```

Le `continue` est critique - il relance la boucle `while` sans ajouter le signal à la liste. Le `mask_planet` avant le `continue` empêche le BLS de retrouver le même signal au tour suivant.

### Ajouter un nouveau paramètre configurable

Trois endroits à modifier :

1. **Signature de la fonction** : ajouter le paramètre avec sa valeur par défaut
2. **`planet_detector()`** : propager le paramètre vers l'appel interne (ex: `_run_bls_analysis`)
3. **`main.py`** : ajouter la saisie utilisateur avec guidance, l'initialisation par défaut, et le passage à `planet_detector()`

### Points sensibles - ne pas toucher sans comprendre

- **L'ordre `flatten` → `remove_outliers`** dans `cleaners.py`. L'inverser produit des faux négatifs silencieux.
- **`np.asarray(lc.flux.value, dtype=float)`** partout dans `mask_planet` et `metrics.py`. Retirer `.value` ou `dtype=float` réintroduit le bug MaskedNDArray.
- **`result["duration"] = known["duration"]`** dans le traitement des alias ratio=1. Sans ça, le masquage d'un résidu avec une durée aberrante vide la courbe entière.
- **Le compteur `harmonic_alias_count`** doit être remis à 0 après chaque vraie planète trouvée, sinon les alias de la planète N-1 comptent vers la limite de la planète N.

---

## 11. Tests et validation

### Cibles de validation

Le pipeline a été validé empiriquement sur des systèmes confirmés. Pas de suite de tests unitaires automatisés.

| Cible | Mission | Planètes | Résultat | Ce que ça valide |
|-------|---------|----------|----------|-----------------|
| Kepler-10 | Kepler | 10b | 1.42 R⊕ (3% erreur) | Détection basique, mesure de rayon |
| Kepler-20 | Kepler | 20b, 20c | 1.78 + 2.66 R⊕ | Multi-planètes, masquage itératif |
| Pi Men | TESS | c | Détecté | Support TESS, filtre SPOC |
| Kepler-9 | Kepler | 9b, 9c | Périodes biaisées | Limite TTV (résultat attendu) |
| HAT-P-11 | Kepler | b | Fausse période | Limite étoile active (résultat attendu) |
| K2-18 | K2 | b | Fausse période | Limite K2 (résultat attendu) |

### Vérification rapide

Pour vérifier que le pipeline fonctionne après une modification :

```python
from data.loader import download_target_data
from processing.cleaners import lc_cleaner
from analysis.detection import planet_detector
from analysis.metrics import analyze_planets_metrics

lc = download_target_data("Kepler-10", author="Kepler", period_index=3)
lc = lc_cleaner(lc)
planets = planet_detector(lc, max_planets=1)
results = analyze_planets_metrics(lc, planets, star_radius=1.056)

assert len(results) == 1
assert abs(results[0]["period"] - 0.8375) < 0.01
assert abs(results[0]["rayon_terrestre"] - 1.47) < 0.3
print("Validation OK")
```

---

## 12. Améliorations possibles

> Voir la roadmap complète dans `README.md`.

### Axe 1 : Précision scientifique

- **Barres d'erreur** (bootstrap sur la profondeur) - priorité critique
- **Modèle Mandel-Agol** (limb darkening) via `batman` - remplace le modèle boîte
- **Detrending pré-masqué** - masquer les transits avant `flatten` pour les transits profonds

### Axe 2 : Couverture instrumentale

- **Correcteur K2 (SFF)** - correction du roll motion
- **Processus gaussien** - alternative à Savitzky-Golay pour étoiles actives
- **Test de centroïde** - filtrer la contamination stellaire

### Axe 3 : Ingénierie

- **Tests unitaires** (pytest) avec les assertions de la section 11
- **Export JSON/CSV** des résultats avec métadonnées
- **Parallélisation** pour le traitement par lot

---

*Documentation générée à partir des docstrings du code source et des tests de validation empiriques.*
