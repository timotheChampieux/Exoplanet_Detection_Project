# ExoHunter
### Champieux Timothe
**Pipeline de détection d'exoplanètes par analyse automatisée de courbes de lumière.**

ExoHunter identifie des planètes en orbite autour d'autres étoiles en détectant les micro-baisses de luminosité qu'elles produisent lorsqu'elles passent devant leur étoile hôte. Compatible avec les données des télescopes spatiaux Kepler et TESS.

---

## Aperçu

### Le problème

Une exoplanète est une planète orbitant autour d'une étoile autre que le Soleil. Quand une telle planète passe entre son étoile et un observateur (un **transit**), elle bloque une infime fraction de la lumière stellaire - typiquement entre 0.01% et 1%. En mesurant cette baisse de luminosité de manière répétée, on peut déduire la période orbitale et la taille de la planète.

Le défi : ces signaux sont noyés dans le bruit instrumental et la variabilité naturelle de l'étoile. Il faut les extraire, les valider, et les caractériser.

### La solution

ExoHunter automatise ce processus en quatre étapes :

1. **Acquisition** des données photométriques depuis les archives spatiales
2. **Nettoyage** du signal (correction de la variabilité stellaire, suppression du bruit)
3. **Détection** des transits périodiques par l'algorithme Box Least Squares (BLS)
4. **Caractérisation** physique des candidats (rayon planétaire, profondeur de transit)

Le pipeline est capable de détecter **plusieurs planètes** dans un même système grâce à une approche itérative avec masquage et filtrage des faux positifs.

---

## Démonstration

Un notebook interactif est disponible dans `notebooks/demo_exohunter.ipynb`. Il démontre le pipeline complet sur le système **Kepler-20**, un système à deux planètes confirmées.

Le notebook produit :
- La courbe de lumière brute puis nettoyée (comparaison avant/après)
- La détection séquentielle des deux planètes
- Le repliement de phase avec zoom sur chaque transit
- La comparaison chiffrée avec les valeurs publiées

**Résultats obtenus sur Kepler-20 (quarters 3, 4) :**

| Planète | Période (réf.) | Période (ExoHunter) | Rayon (réf.) | Rayon (ExoHunter) |
|---------|---------------|--------------------:|-------------|------------------:|
| Kepler-20b | 3.696 j | 3.696 j | 1.87 R⊕ | 1.78 R⊕ |
| Kepler-20c | 10.854 j | 10.854 j | 3.07 R⊕ | 2.66 R⊕ |

Précision sur les périodes : < 0.1%. Précision sur les rayons : 5 à 13%.

---

## Fonctionnalités

- **Détection de transits** par algorithme BLS avec grille de fréquences configurable
- **Détection multi-planètes** par masquage itératif des signaux détectés
- **Filtrage des faux positifs** : alias de période, binaires à éclipses (test odd/even), artefacts (ratio négatif)
- **Prétraitement adaptatif** : correction de variabilité stellaire (Savitzky-Golay) + sigma-clipping
- **Calcul des paramètres physiques** : rayon planétaire, profondeur de transit (ppm), période orbitale
- **Support multi-mission** : Kepler, TESS (SPOC), K2
- **Interface configurable** : tous les paramètres critiques sont exposés à l'utilisateur avec guidance contextuelle (mode expert)
- **Contournement des incompatibilités Astropy ≥ 5.0** : traitement numpy pur pour les opérations critiques

---

## Fonctionnement de l'algorithme

### Pipeline global

```
Courbe de lumière brute
        │
        ▼
┌─────────────────┐
│   1. ACQUISITION │  Téléchargement via Lightkurve (archives MAST)
│                  │  Assemblage des segments (quarters/secteurs)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. NETTOYAGE    │  Correction variabilité stellaire (Savitzky-Golay)
│                  │  Suppression des points aberrants (sigma-clipping)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. DÉTECTION    │  Scan BLS sur toute la plage de périodes
│                  │  Masquage du signal → recherche du suivant
│                  │  Filtres anti-faux-positifs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. MÉTRIQUES    │  Repliement de phase + binning
│                  │  Mesure de profondeur → calcul du rayon
└────────┬────────┘
         │
         ▼
    Résultats
```

### Concepts clés

**BLS (Box Least Squares)** : l'algorithme teste des milliers de périodes possibles. Pour chacune, il cherche la meilleure "boîte" rectangulaire périodique qui s'ajuste aux données. Le signal le plus fort (meilleur SNR) est retenu.

**SNR (Signal-to-Noise Ratio)** : rapport entre l'amplitude du transit et le bruit. Un SNR > 7.1 est requis pour une détection statistiquement fiable (standard de la communauté).

**Repliement de phase** : superposition de tous les cycles orbitaux sur une seule période. Les transits s'alignent et le bruit se moyenne, faisant émerger la forme du transit.

**Profondeur de transit (δ)** : fraction de lumière bloquée par la planète. Le rayon planétaire est déduit par la relation Rp = √δ × Rs, où Rs est le rayon de l'étoile hôte.

Un glossaire complet des termes techniques et scientifiques est disponible dans `docs/GLOSSAIRE_EXOHUNTER.md`.

---

## Cas d'utilisation

### Fonctionne bien

| Condition | Pourquoi |
|-----------|----------|
| Profondeur de transit 100-2000 ppm | Au-dessus du bruit, en dessous du seuil d'écrasement par le filtre de lissage |
| Période orbitale 0.7-30 jours | Assez de transits sur 2-4 quarters pour un SNR significatif |
| Étoiles calmes (types F/G/K) | Variabilité stellaire lente, bien corrigée par le Savitzky-Golay |
| Données Kepler ou TESS-SPOC | Courbes bien calibrées, cadence régulière, bruit instrumental maîtrisé |

**Validations réussies :**
- Kepler-10b : 1.42 R⊕ trouvé vs 1.47 R⊕ référence (3% d'écart)
- Kepler-20 b/c : deux planètes détectées dans le même système (5-13% d'écart sur les rayons)
- Pi Mensae c : détection cross-mission validée sur TESS secteur 1

### Limitations connues

| Limitation | Cause | Impact |
|-----------|-------|--------|
| Transits profonds (> 2000 ppm) | Le filtre Savitzky-Golay écrase partiellement les transits répétés profonds | Rayon sous-estimé de 30-50% |
| Étoiles actives (naines M, jeunes) | Les taches stellaires créent une modulation que le lissage ne corrige pas | Fausses périodes (sous-harmoniques) |
| Données K2 | La systématique de pointage (roll motion) nécessite un correcteur dédié non implémenté | Faux positifs instrumentaux |
| Systèmes à forte TTV | Le BLS suppose une périodicité stricte, incompatible avec les décalages gravitationnels | Périodes et rayons biaisés |
| Planètes à longue période | Moins de 3 transits dans la baseline → SNR insuffisant | Non détectées |
| Pas de barres d'erreur | Ni bootstrap ni MCMC implémentés | Confiance non quantifiée |

Un rapport d'audit détaillé est disponible dans `docs/AUDIT_EXOHUNTER.md`.

---

## Installation

```bash
git clone https://github.com/timotheChampieux/ExoHunter.git
cd ExoHunter
pip install -r requirements.txt
```

Dépendances principales : `lightkurve`, `numpy`, `matplotlib`, `astropy`.

---

## Utilisation rapide

### Mode interactif (recommandé)

```bash
cd src
python main.py
```

Le pipeline pose les questions une par une (cible, mission, rayon stellaire, paramètres d'analyse) et affiche les résultats. Un mode expert permet de configurer les paramètres avancés avec guidance contextuelle.

### En script Python

```python
from data.loader import download_target_data
from processing.cleaners import lc_cleaner
from analysis.detection import planet_detector
from analysis.metrics import analyze_planets_metrics

# 1. Télécharger les données
lc_raw = download_target_data("Kepler-10", author="Kepler", period_index=[3, 4])

# 2. Nettoyer
lc_clean = lc_cleaner(lc_raw, window_length=801, sigma=5.0)

# 3. Détecter
planets = planet_detector(lc_clean, max_planets=2, frequency_factor=10)

# 4. Calculer les rayons
results = analyze_planets_metrics(lc_clean, planets, star_radius=1.056)

for p in results:
    print(f"P = {p['period']:.4f}j | R = {p['rayon_terrestre']:.2f} R⊕ | SNR = {p['snr']:.1f}")
```

### Notebook de démonstration

```bash
cd notebooks
jupyter notebook demo_exohunter.ipynb
```

---

## Structure du projet

```
Exoplanet_Detection_Project/
│
├── src/                          # Code source du pipeline
│   ├── main.py                   # Point d'entrée - interface utilisateur interactive
│   ├── data/
│   │   └── loader.py             # Téléchargement et assemblage des courbes de lumière
│   ├── processing/
│   │   └── cleaners.py           # Prétraitement (detrending + sigma-clipping)
│   ├── analysis/
│   │   ├── detection.py          # Détection BLS + masquage itératif + filtres
│   │   └── metrics.py            # Calcul des paramètres physiques (rayon, profondeur)
│   └── visualization/
│       └── sliders.py            # Visualisation interactive (à développer)
│
├── notebooks/
│   ├── demo_exohunter.ipynb      # Démonstration complète avec visualisations
│    └── test_notebook.ipynb       # Premier test manuel avant de  passer a la création de Exohunter (pour prendre en main lightkurve)
│
├── docs/
│   ├── DEFINITIOn.md    # Définitions des termes techniques et scientifiques
│   ├── AUDIT_EXOHUNTER.md        # Rapport d'audit (domaine de validité, limites)
    └── DOCUMENTATION_TECHNIQUE.md #expliquation des fonctions et guide développeur pour reprendre le code.
│
├── requirements.txt
└── README.md
```

---

## Performance et limites techniques

### Temps de calcul

Le BLS est le goulot d'étranglement. Le temps dépend de la taille de la grille de fréquences :

| Configuration | Points dans la grille | Temps par itération |
|---------------|----------------------:|--------------------:|
| 2 quarters, freq_factor=10 | ~70 000 | ~1 min |
| 4 quarters, freq_factor=10 | ~140 000 | ~3 min |
| 4 quarters, freq_factor=6 | ~250 000 | ~6 min |

Un système à 2 planètes avec 3-5 alias consomme 5-7 itérations BLS.

### Scalabilité

Le pipeline traite une étoile à la fois. Le traitement par lot (batch) sur des milliers de cibles nécessiterait une parallélisation non implémentée.

### Robustesse

- **Reproductible** : entièrement déterministe, pas de composante aléatoire
- **Fragile** sur un point : les `MaskedNDArray` d'Astropy ≥ 5.0 peuvent réapparaître si une nouvelle méthode Lightkurve est ajoutée au pipeline. Le contournement actuel (numpy pur) est documenté et testé.

---

## Documentation

| Document | Contenu |
|----------|---------|
| `docs/GLOSSAIRE_EXOHUNTER.md` | Définitions de tous les termes techniques et scientifiques utilisés dans le projet (BLS, SNR, transit, detrending, etc.). Accessible aux non-spécialistes. |
| `docs/AUDIT_EXOHUNTER.md` | Rapport d'audit complet : domaine de validité, cas de succès, cas d'échec, failles techniques, recommandations d'amélioration. |
| `notebooks/demo_exohunter.ipynb` | Démonstration exécutable sur Kepler-20 avec visualisations et comparaison aux valeurs publiées. |

---

## Roadmap

### Priorité haute

- **Barres d'erreur** : estimation d'incertitude par bootstrap sur la mesure de profondeur
- **Detrending pré-masqué** : masquer les transits candidats avant le lissage pour éviter l'écrasement des transits profonds
- **Processus gaussien (GP)** : alternative au Savitzky-Golay pour les étoiles à variabilité rapide

### Priorité moyenne

- **Correcteur K2 (SFF)** : correction de la systématique de pointage pour supporter les données K2
- **Ajustement de modèle de transit** (Mandel-Agol via `batman`) : remplacement du modèle boîte pour une mesure précise du rayon avec limb darkening
- **Test de centroïde** : vérification que le transit provient bien de l'étoile cible

### Priorité future

- **Export structuré** (JSON/CSV) des résultats avec métadonnées
- **Traitement par lot** pour l'analyse de catalogues entiers
- **Visualisation interactive** (module `sliders.py`)

---

## Licence

Ce projet est personnel à usage éducatif et de recherche.

---

## Stack technique

`Python` · `NumPy` · `Lightkurve` · `Astropy` · `Matplotlib`

---

*ExoHunter v2.0 - Pipeline de détection d'exoplanètes par transit*
