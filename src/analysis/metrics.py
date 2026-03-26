import lightkurve as lk
import logging
import numpy as np 
from .detection import mask_planet

##gestion de log
logger = logging.getLogger(__name__)

def _get_bin_size(lc : lk.LightCurve, planet_info : dict, points_per_transit : int ) -> float: 
    """
    Calcule la taille de bin optimale (en unité de phase) pour le repliement de la courbe de lumière.

    Cette fonction détermine la largeur des bacs (bins) nécessaire pour obtenir un nombre précis de points 
    de mesure à l'intérieur de la durée du transit. Elle assure un compromis entre la réduction du bruit 
    par moyennage et la préservation de la morphologie du transit.

    .. note::
        La fonction intègre une sécurité par rapport à la cadence de l'instrument : la taille du bin 
        ne peut pas être inférieure à la résolution temporelle réelle des données originales. Cela 
        empêche le sur-échantillonnage artificiel (interpolation) qui n'apporterait aucune information 
        scientifique réelle.

    :param lc: La courbe de lumière utilisée pour mesurer la cadence instrumentale.
    :type lc: lk.LightCurve
    :param planet_info: Dictionnaire contenant les paramètres orbitaux ('duration', 'period').
    :type planet_info: dict
    :param points_per_transit: Nombre de points de mesure souhaités à l'intérieur de la fenêtre du transit.
    :type points_per_transit: int
    :return: La taille du bin en unité de phase (comprise entre 0 et 1).
    :rtype: float

    **Exemple :**

    .. code-block:: python

        p_info = {"period": 3.52, "duration": 0.12}
        
        # Calcul du bin pour avoir 50 points dans le transit de HD 209458b
        bin_phase = _get_bin_size(lc_clean, p_info, points_per_transit=50)
        
        # Application lors du repliement
        lc_folded = lc_clean.fold(period=3.52).bin(time_bin_size=bin_phase)
    """
    duration = planet_info["duration"]
    period = planet_info["period"]

    #Duree du transit en unité de phase et non en jours
    phase_duration = duration / period

    bin_size_phase = phase_duration / points_per_transit

    #on mesure la cadence de l'instrument
    cadence_jours =np.nanmedian(np.diff(lc.time.value))
    cadence_phase = cadence_jours / period

    #on evite de biner plus fin que la mesure de base 
    return max(cadence_phase, bin_size_phase)




def analyze_planets_metrics(lc : lk.LightCurve,planets_list : list, star_radius: float=1 ,points_per_transit : int = 70) -> list : 
    """
    Calcule les métriques physiques (rayon, profondeur) pour chaque planète candidate détectée.

    Cette fonction affine les paramètres de chaque planète en utilisant un repliement de phase 
    manuel et un binning adaptatif. Elle gère les systèmes multi-planétaires en masquant les signaux 
    des autres planètes lorsque leurs périodes sont suffisamment proches pour risquer une 
    interférence (ratio < 5). La profondeur est mesurée en comparant le flux médian au fond du 
    transit (*in-transit*) par rapport au flux de la ligne de base locale (*out-of-transit*).

    .. note::
        Pour garantir la stabilité numérique et contourner les limitations de protection mémoire 
        d'Astropy, le repliement de phase et le binning sont effectués via NumPy. Le rayon 
        terrestre est calculé à partir de la relation : :math:`R_p = \sqrt{\delta} \cdot R_s`, 
        où :math:`\delta` est la profondeur du transit.

    :param lc: La courbe de lumière nettoyée servant de base aux mesures.
    :type lc: lk.LightCurve
    :param planets_list: Liste de dictionnaires contenant les paramètres de détection BLS.
    :type planets_list: list
    :param star_radius: Rayon de l'étoile hôte en rayons solaires (:math:`R_{\odot}`). Par défaut 1.0.
    :type star_radius: float
    :param points_per_transit: Nombre de points de mesure souhaités dans la fenêtre du transit. 
                               Définit la résolution du binning.
    :type points_per_transit: int
    :return: La liste des planètes mise à jour avec les clés ``rayon_terrestre``, ``rayon_km`` 
             et ``depth_ppm``.
    :rtype: list

    **Exemple :**

    .. code-block:: python

        # Après détection de deux candidats sur Kepler-10
        candidates = [
            {"period": 0.837, "transit_time": 2454964.5, "duration": 0.021},
            {"period": 45.29, "transit_time": 2454980.2, "duration": 0.28}
        ]
        
        # Calcul des caractéristiques physiques avec le rayon réel de l'étoile (1.056 Rsun)
        results = analyze_planets_metrics(lc_clean, candidates, star_radius=1.056)
        
        for p in results:
            print(f"P={p['period']} j -> Rayon={p['rayon_terrestre']} R_earth")
    """
    if not planets_list:
        logger.info("Aucune métrique à calculer (liste vide).")
        return []
    
    logger.info(f"Calcul des métriques physiques pour {len(planets_list)} planète(s)...")

    for i, planet in enumerate(planets_list):
        # On repart de la courbe originale pour chaque mesure 
        actual_lc = lc.copy()

        #On masque toute les autres planètes
        for j, planet_a_masquer in enumerate(planets_list):
            if j == i:
                continue
            # on masque que les planètes de période proche (ratio < 5)
            ratio = max(planet["period"], planet_a_masquer["period"]) / min(planet["period"], planet_a_masquer["period"])
            if ratio < 5:
                actual_lc = mask_planet(actual_lc, planet_a_masquer)
            else:
                logger.info(f"Masquage ignoré pour planète {j+1} (ratio de période = {ratio:.1f}x — moyenne en phase).")
            

        #calcul résolution et repliement
             # Extraction numpy pure
        time = np.asarray(actual_lc.time.value, dtype=float)
        flux = np.asarray(actual_lc.flux.value, dtype=float)

        # Repliement de phase manuel (centré sur le transit)
        phase = (time - planet["transit_time"] + planet["period"] / 2) % planet["period"] - planet["period"] / 2
        # Conversion en unité de phase (fraction de période)
        phase_norm = phase / planet["period"]

        # Binning manuel
        bin_size = _get_bin_size(actual_lc, planet, points_per_transit)
        bin_edges = np.arange(-0.5, 0.5 + bin_size, bin_size)
        bin_flux = np.full(len(bin_edges) - 1, np.nan)
        bin_phase = np.full(len(bin_edges) - 1, np.nan)

        for k in range(len(bin_edges) - 1):
            in_bin = (phase_norm >= bin_edges[k]) & (phase_norm < bin_edges[k + 1])
            if np.sum(in_bin) > 0:
                bin_flux[k] = np.nanmedian(flux[in_bin])
                bin_phase[k] = (bin_edges[k] + bin_edges[k + 1]) / 2

        # Nettoyage des bins vides
        valid = np.isfinite(bin_flux)
        bin_flux = bin_flux[valid]
        bin_phase = bin_phase[valid]

        # Calcul de profondeur
        phase_duration = planet["duration"] / planet["period"]
        mask_in = np.abs(bin_phase) < (phase_duration * 0.4)
        mask_out = (np.abs(bin_phase) > (phase_duration * 0.6)) & (np.abs(bin_phase) < (phase_duration * 1.5))

        if np.sum(mask_in) > 0 and np.sum(mask_out) > 0:
            flux_in = np.nanmedian(bin_flux[mask_in])
            flux_out = np.nanmedian(bin_flux[mask_out])
            profondeur = max(0, 1.0 - (flux_in / flux_out))
        else:
            logger.warning(f"Candidat {i+1}: Binning insuffisant, fallback sur depth_bls.")
            profondeur = planet["depth_bls"]

                # Rp/Rs = sqrt(profondeur)
        ratio_rayons = np.sqrt(profondeur)

        # 1 Rsun = 109.12 Rearth. Formule : Rp = Ratio * Rs * 109.12
        rayon_terrestre = ratio_rayons * star_radius * 109.12
        
        # Mise à jour du dico
        planet["rayon_terrestre"] = round(rayon_terrestre, 2)
        planet["rayon_km"] = round(rayon_terrestre * 6371, 0)
        #convention scientifique = combien de fois elle cache un millionième de la lumière de son étoile
        planet["depth_ppm"] = round(profondeur * 1e6, 0)

        logger.info(f"Planète {i+1} : Rayon = {rayon_terrestre} R_earth (Profondeur: {planet['depth_ppm']} ppm)")

    return planets_list
