import lightkurve as lk
import logging
import numpy as np 
from .detection import mask_planet
##gestion de log
logger = logging.getLogger(__name__)

def _get_bin_size(lc,planet_info, points_per_transit : int = 50 ) : 
    duration = planet_info["duration"]
    points = duration / points_per_transit
    cadence_instrument =np.nanmedian(np.diff(lc.time.value))
    return max(cadence_instrument, points)

def _get_phase(lc,period,epoch_time,bin) : 
    return lc.fold(period = period, epoch_time = epoch_time ).bin(bin)


def analyze_planets_metrics(lc : lk.LightCurve,planets_list : list, star_radius=1 ) : 

    if not planets_list:
        return []
    
    for planet in planets_list : 
        actual_lc = lc

        for planet_a_masquer in planets_list : 
            if planet_a_masquer == planet :
                continue
            actual_lc = mask_planet(actual_lc,planet_a_masquer)

        bin_size = _get_bin_size(actual_lc,planet)
        phase = _get_phase(actual_lc,planet["period"],planet["transit_time"],bin_size)

        pic_min = np.nanpercentile(phase.flux, 1)
        profondeur = 1 - pic_min

        # On évite les racines carrées de nombres négatifs (au cas ou il y eu un faux positif)
        profondeur = max(0, profondeur) 

        ratio_rayons = np.sqrt(profondeur)

        rayon_terrestre = round(ratio_rayons * star_radius * 109.12, 2)
        rayon_km = rayon_terrestre * 6371
       

        planet["rayon_km"] = rayon_km
        planet["rayon_terrestre"] = rayon_terrestre
        #convention scientifique = combien de fois elle cache un millionième de la lumière de son étoile
        planet["depth_ppm"] = round(profondeur * 1e6, 0)

    return planets_list
