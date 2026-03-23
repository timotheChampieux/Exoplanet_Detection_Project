import lightkurve as lk
import logging
import numpy as np 
from .detection import mask_planet

##gestion de log
logger = logging.getLogger(__name__)

def _get_bin_size(lc : lk.LightCurve, planet_info : dict, points_per_transit : int ) -> float: 
    """
    Calcule la taille optimale des bins pour le repliement de phase
    permet d'avoir une résolution suffisament precise et respectant la cadence de l'appareil
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
    Calcule les caractéristiques(rayon, profondeur) pour chaque 
    planète de la liste en masquant les signaux concurrents (autres planètes)
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
            # On ne masque que les planètes de période proche (ratio < 5)
            # Les périodes très différentes s'annulent dans le repliement de phase
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
        
        # Mise à jour du dictionnaire
        planet["rayon_terrestre"] = round(rayon_terrestre, 2)
        planet["rayon_km"] = round(rayon_terrestre * 6371, 0)
        #convention scientifique = combien de fois elle cache un millionième de la lumière de son étoile
        planet["depth_ppm"] = round(profondeur * 1e6, 0)

        logger.info(f"Planète {i+1} : Rayon = {rayon_terrestre} R_earth (Profondeur: {planet['depth_ppm']} ppm)")

    return planets_list
