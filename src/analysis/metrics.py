import lightkurve as lk
import logging
import numpy as np 
from .detection import mask_planet

##gestion de log
logger = logging.getLogger(__name__)

def _get_bin_size(lc : lk.LightCurve, planet_info : dict, points_per_transit : int = 50 ) -> float: 
    """
    Calcule la taille optimale des bins pour le repliement de phase
    permet d'avoir une résolution suffisament precise et respectant la cadence de l'appareil
    """
    duration = planet_info["duration"]

    points = duration / points_per_transit
    #on mesure la cadence de l'instrument
    cadence_instrument =np.nanmedian(np.diff(lc.time.value))
    #on evite de biner plus fin que la mesure de base 
    return max(cadence_instrument, points)

def _get_phase(lc: lk.LightCurve, period: float, epoch_time : float, bin : float) -> lk.LightCurve : 
    """
    Replie la courbe de lumière et applique le bin pour réduire le bruit et améliorer la précision
    """
    folded = lc.fold(period=period, epoch_time=epoch_time)
    
    #On nettoie les résidus du masquage pour eviter une erreur fréquente
    folded = folded.remove_nans()
    
    return folded.bin(time_bin_size=bin)


def analyze_planets_metrics(lc : lk.LightCurve,planets_list : list, star_radius: float=1 ) -> list : 
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
        actual_lc = lc

        #On masque toute les autres planètes
        for planet_a_masquer in planets_list : 
            if planet_a_masquer == planet :
                continue
            actual_lc = mask_planet(actual_lc,planet_a_masquer)

        #calcul résolution et repliement
        bin_size = _get_bin_size(actual_lc,planet)
        phase = _get_phase(actual_lc,planet["period"],planet["transit_time"],bin_size)

        #On mesure la profondeur du transit (nanpercentile pour eviter les points morts)
        pic_min = np.nanpercentile(phase.flux, 1)
        profondeur = 1 - pic_min

        # On évite les racines carrées de nombres négatifs (au cas ou il y eu un faux positif : profondeur negativ = augmentation de lumière)
        profondeur = max(0, profondeur) 

        # Rp/Rs = sqrt(profondeur)
        ratio_rayons = np.sqrt(profondeur)

        # 1 Rsun = 109.12 Rearth. Formule : Rp = Ratio * Rs * 109.12
        rayon_terrestre = round(ratio_rayons * star_radius * 109.12, 2)
        rayon_km = round(rayon_terrestre * 6371,0)
       
        #Mis a jour du dict de la planete
        planet["rayon_km"] = rayon_km
        planet["rayon_terrestre"] = rayon_terrestre
        #convention scientifique = combien de fois elle cache un millionième de la lumière de son étoile
        planet["depth_ppm"] = round(profondeur * 1e6, 0)

        logger.info(f"Planète {i+1} : Rayon = {rayon_terrestre} R_earth (Profondeur: {planet['depth_ppm']} ppm)")

    return planets_list
