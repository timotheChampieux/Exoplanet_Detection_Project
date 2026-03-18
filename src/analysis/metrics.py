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
            actual_lc = mask_planet(actual_lc, planet_a_masquer)
            

        #calcul résolution et repliement
        folded = actual_lc.fold(period=planet["period"], epoch_time=planet["transit_time"])
        
        bin_size = _get_bin_size(actual_lc,planet,points_per_transit)
        phase_binned = folded.bin(time_bin_size=bin_size).remove_nans()
        
        
        phase_duration = planet["duration"] / planet["period"]
        phase_values = phase_binned.time.value

        #fond du transit, 80% de la durée pour éviter les bords
        mask_in = np.abs(phase_values) < (phase_duration * 0.4)
        
        #Masque exterieur du transit (entre 0.6x et 1.5x la durée)
        mask_out = (np.abs(phase_values) > (phase_duration * 0.6)) & (np.abs(phase_values) < (phase_duration * 1.5))
        
        # Calcul du flux moyen au fond
        # On utilise la médiane sur ces points précis pour ignorer le bruit
        if np.sum(mask_in) > 0 and np.sum(mask_out) > 0:
            flux_in = np.nanmedian(phase_binned.flux[mask_in])
            flux_out = np.nanmedian(phase_binned.flux[mask_out])
            profondeur = max(0, 1.0 - (flux_in / flux_out))
        else:
            # Sécurité si aucun point n'est dans la zone
            logger.warning(f"Candidat {i+1}: Binning trop large, calcul via percentiles.")
            profondeur = max(0, 1.0 - np.nanpercentile(phase_binned.flux, 1))

        

        # On évite les racines carrées de nombres négatifs (au cas ou il y eu un faux positif : profondeur negativ = augmentation de lumière)
        # Rp/Rs = sqrt(profondeur)
        ratio_rayons = np.sqrt(profondeur)

        # 1 Rsun = 109.12 Rearth. Formule : Rp = Ratio * Rs * 109.12
        ratio_rayons = np.sqrt(profondeur)
        rayon_terrestre = ratio_rayons * star_radius * 109.12
        
        # Mise à jour du dictionnaire
        planet["rayon_terrestre"] = round(rayon_terrestre, 2)
        planet["rayon_km"] = round(rayon_terrestre * 6371, 0)
        #convention scientifique = combien de fois elle cache un millionième de la lumière de son étoile
        planet["depth_ppm"] = round(profondeur * 1e6, 0)

        logger.info(f"Planète {i+1} : Rayon = {rayon_terrestre} R_earth (Profondeur: {planet['depth_ppm']} ppm)")

    return planets_list
