import lightkurve as lk
import logging
import numpy as np 

##gestion de log
logger = logging.getLogger(__name__)

def _run_bls_analysis(lc : lk.LightCurve) -> dict : 
    """
    Exécute l'algorithme BLS et extrait les 
    statistiques du meilleur pic.
    """
    #min_p, max_p, steps = _get_search_params(lc)

     #beaucoup plus précis que np.linspace pour détecter des transits courts.
    bls = lc.to_periodogram(method='bls', minimum_period=0.5, maximum_period=(lc.time.value.max() - lc.time.value.min()) / 2)
    
    #on recup le meilleur condidat
    best_period = bls.period_at_max_power
    best_t0 = bls.transit_time_at_max_power
    best_duration = bls.duration_at_max_power

    # Calcul des stats pour obtenir le SNR correct
    stats = bls.compute_stats(period=best_period, duration=best_duration, transit_time=best_t0)
    
    odd_even_ratio = stats["depth_odd"][0] / stats["depth_even"][0] if stats["depth_even"][0] != 0 else float('inf')    
    return {
        "period": best_period.value,
        "transit_time": best_t0.value,
        "duration": best_duration.value,
        "snr": np.nanmax(bls.snr).value,
        "max_power": bls.max_power.value,
        "depth_bls": stats["depth"][0],           #profondeur mesurée par le BLS
        "odd_even_ratio": round(odd_even_ratio, 3) #ratio pair/impair pour filtrer les faux positifs
    }

def mask_planet(lc : lk.LightCurve, planet_info : dict) ->  lk.LightCurve :
    """
    Masque les transits d'une planète pour permettre 
    la recherche de signaux plus faibles (d'autre planètes).
    """
    #On utilise un facteur de 2 sur la durée pour etre sur de bien masquer le transit
    mask = lc.create_transit_mask(
        period=planet_info["period"], 
        transit_time=planet_info["transit_time"], 
        duration=planet_info["duration"] * 2
    )

    lc_masked = lc[~mask].remove_nans()

     #On filtre la courbe
    return lk.LightCurve(
        time=lc_masked.time.copy(), 
        flux=lc_masked.flux.copy(), 
        flux_err=lc_masked.flux_err.copy(),
        meta=lc_masked.meta 
    )

def planet_detector(lc : lk.LightCurve, max_planets=10 ) -> list : 
    """
    fonction principale : Cherche des planètes jusqu'à ce que 
    le signal soit trop faible ou le maximum atteint (sécurité contre les boucles infinies).
    """

    planets_found = []
    current_lc = lc

    while len(planets_found)<max_planets : 
        #analyse de la courbe actuelle
        logger.info(f"Tentative de détection n°{len(planets_found) + 1}...")
        result = _run_bls_analysis(current_lc)
        logger.info(f"Analyse BLS terminée.")
        #critère de validation
        if result["snr"] > 7.1 : 
            logger.info(f"Planète détectée ! Période: {result['period']:.3f} j | SNR: {result['snr']:.2f}")
            planets_found.append(result)
            
            if abs(result["odd_even_ratio"] - 1.0) > 0.3:
                logger.warning(f"Signal rejeté (odd/even ratio = {result['odd_even_ratio']}) — probable binaire à éclipses.")
                current_lc = mask_planet(current_lc, result)
                continue
            #On masque la planète pour le tour suivant
            if max_planets > 1 :
                logger.info("Début du masquage de la planète...")
                current_lc = mask_planet(current_lc,result)
                logger.info("Masquage réussi.")
                
        else : 
            if len(planets_found) == 0 : 
                logger.info("Fin de recherche : aucun signal significatif.")
            else : 
                logger.info("Fin de recherche : aucun signal supplémentaire significatif.")
            break

    return planets_found


      


