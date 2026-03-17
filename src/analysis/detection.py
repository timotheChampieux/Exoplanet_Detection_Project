import lightkurve as lk
import logging
import numpy as np 

##gestion de log
logger = logging.getLogger(__name__)

def _get_search_params(lc : lk.LightCurve) -> int:
    """
    Calcule les meilleurs paramètres  pour la recherche BLS 
    en fonction de la durée des données (nombre de quarter donné par l'user).
    """
    #durée en jour
    observation_time = lc.time.value.max() - lc.time.value.min()


    max_period = observation_time/3
    min_period = 0.5
    

    if max_period <= min_period:
        logger.warning("Durée d'observation trop courte. Ajustement des périodes.")
        max_period = min_period + 1

    #Nombre de tests proportionnel à la durée
    steps = int(observation_time * 500)

    return min_period, max_period, steps

def _run_bls_analysis(lc : lk.LightCurve) -> dict : 
    """
    Exécute l'algorithme BLS et extrait les 
    statistiques du meilleur pic.
    """
    min_p, max_p, steps = _get_search_params(lc)

    periods =  np.linspace(min_p,max_p,steps)

    #calcul du periodigramme bls
    bls = lc.to_periodogram(method='bls',period=periods)
    
    #on recup le meilleur condidat
    best_period = bls.period_at_max_power
    best_t0 = bls.transit_time_at_max_power
    best_duration = bls.duration_at_max_power

    #calcul stat detaillees
    stats = bls.compute_stats(period=best_period, 
                            duration=best_duration, 
                            transit_time=best_t0)
    best_snr = np.nanmax(bls.snr).value
    result = {
        "period": best_period.value,
        "transit_time": best_t0.value,
        "duration": best_duration.value,
        #si le snr > 7 on decrete que il y a une planète
        "snr":  best_snr,
        "max_power": bls.max_power.value
    }
    return result

def mask_planet(lc : lk.LightCurve, planet_info : dict) ->  lk.LightCurve :
    """
    Masque les transits d'une planète pour permettre 
    la recherche de signaux plus faibles (d'autre planètes).
    """
    #On utilise un facteur de 3 sur la durée pour etre sur de bien masquer le transit
    masque = lc.create_transit_mask(
        period=planet_info["period"], 
        transit_time=planet_info["transit_time"], 
        duration=planet_info["duration"] * 3
    )

    #On garde que les point qui ne sont pas le masque 
    return  lc[~masque].copy()

def planet_detector(lc : lk.LightCurve, max_planets=10 ) -> list : 
    """
    fonction principale : Cherche des planètes jusqu'à ce que 
    le signal soit trop faible ou le maximum atteint (sécurité contre les boucles infinies).
    """

    planets_found = []
    current_lc = lc

    while len(planets_found)<max_planets : 
        #analyse de la courbe actuelle
        result = _run_bls_analysis(current_lc)
        
        #critère de validation
        if result["snr"] > 7 : 
            logger.info(f"Planète détectée ! Période: {result['period']:.3f} j | SNR: {result['snr']:.2f}")
            planets_found.append(result)

            #On masque la planète pour le tour suivant
            current_lc = mask_planet(current_lc,result)
        else : 
            if len(planets_found) == 0 : 
                logger.info("Fin de recherche : aucun signal significatif.")
            logger.info("Fin de recherche : aucun signal supplémentaire significatif.")
            break

    return planets_found


      


