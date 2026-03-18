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
    print(f"---------------------------Points per transit : {points_per_transit}---------------------")
    duration = planet_info["duration"]

    points = duration / points_per_transit
    print(f"---------------------------Points : {points}---------------------")
    #on mesure la cadence de l'instrument
    cadence_instrument =np.nanmedian(np.diff(lc.time.value))
    print(f"---------------------------cadence_instrument : {cadence_instrument}---------------------")
    #on evite de biner plus fin que la mesure de base 
    return max(cadence_instrument, points)

def _get_phase(lc: lk.LightCurve, period: float, epoch_time : float, bin : float) -> lk.LightCurve : 
    """
    Replie la courbe de lumière et applique le bin pour réduire le bruit et améliorer la précision
    """
    folded = lc.fold(period=period, epoch_time=epoch_time)
    
    #On creer une nouvelle lc pour eviter chevauchement de masque
    clean_folded = lk.LightCurve(
        time=folded.time.value, 
        flux=np.array(folded.flux.value),    
        flux_err=np.array(folded.flux_err.value)
    ).remove_nans()
    print(f"---------------------------BIN : {bin}---------------------")
    return clean_folded.bin(time_bin_size=bin)


def analyze_planets_metrics(lc : lk.LightCurve,planets_list : list, star_radius: float=1 ,points_per_transit : int = 1440) -> list : 
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
        actual_lc = lk.LightCurve(time=lc.time.value, flux=np.array(lc.flux.value), flux_err=np.array(lc.flux_err.value))

        #On masque toute les autres planètes
        for planet_a_masquer in planets_list : 
            if planet_a_masquer == planet :
                continue
            actual_lc = mask_planet(actual_lc,planet_a_masquer)
            actual_lc = lk.LightCurve(time=actual_lc.time.value, flux=np.array(actual_lc.flux.value), flux_err=np.array(actual_lc.flux_err.value))

        #calcul résolution et repliement
        bin_size = _get_bin_size(actual_lc,planet,points_per_transit)
        phase = _get_phase(actual_lc,planet["period"],planet["transit_time"],bin_size)

        phase_values = phase.time.value
        
        # On définit une zone 1% de la phase autour du centre
        mask_fond = (phase_values > -0.01) & (phase_values < 0.01)
        
        # Calcul du flux moyen au fond
        # On utilise la médiane sur ces points précis pour ignorer le bruit
        if len(phase.flux[mask_fond]) > 0:
            pic_min = np.nanmedian(phase.flux[mask_fond])
        else:
            # Sécurité si aucun point n'est dans la zone
            pic_min = np.nanpercentile(phase.flux, 1)

        profondeur = 1.0 - pic_min
        profondeur = max(0, profondeur)

        # On évite les racines carrées de nombres négatifs (au cas ou il y eu un faux positif : profondeur negativ = augmentation de lumière)
        

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
