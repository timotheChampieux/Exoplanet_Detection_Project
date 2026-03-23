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
    # Sécurité : vérifier qu'il reste assez de points pour un BLS
    if len(lc) < 50:
        logger.warning(f"Courbe trop courte ({len(lc)} points) pour un BLS fiable.")
        return {"snr": 0, "period": 0, "transit_time": 0, "duration": 0,
                "max_power": 0, "depth_bls": 0, "odd_even_ratio": 1.0}

     #beaucoup plus précis que np.linspace pour détecter des transits courts.
    bls = lc.to_periodogram(method='bls', minimum_period=0.7, maximum_period=(lc.time.value.max() - lc.time.value.min())/3, frequency_factor=10)    
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
    Marge de 1.5x la durée du transit pour couvrir l'ingress/egress
    et les résidus de bord (standard TLS/Kepler Pipeline).
    """
    period = planet_info["period"]
    t0 = planet_info["transit_time"]
    mask_half_width = planet_info["duration"] * 2.0  # marge 1.5x pour supprimer les résidus d'ingress/egress

    #numpy pur aucun passage par Astropy creant des soucis a priori inévitables
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)
    flux_err = np.asarray(lc.flux_err.value, dtype=float)

    #Calcul du masque de transit en phase
    #On replie le temps sur la période, centré sur t0
    phase = (time - t0 + period / 2) % period - period / 2

    #On masque tout point dans la fenêtre de transit élargie
    mask_transit = np.abs(phase) < mask_half_width

    # On garde tout ce qui n'est PAS dans le transit
    keep = ~mask_transit

    return lk.LightCurve(
        time=time[keep],
        flux=flux[keep],
        flux_err=flux_err[keep],
        meta=lc.meta
    )

def planet_detector(lc : lk.LightCurve, max_planets=10 ) -> list : 
    """
    fonction principale : Cherche des planètes jusqu'à ce que 
    le signal soit trop faible ou le maximum atteint (sécurité contre les boucles infinies).
    """

    planets_found = []
    current_lc = lc
    harmonic_alias_count = 0  # Compteur pour les vrais alias harmoniques (2x, 3x...)
    max_iterations = 2 * max_planets + 6  # Sécurité anti-boucle infinie
    iteration = 0
    while len(planets_found) < max_planets : 
        iteration += 1
        if iteration > max_iterations:
            logger.info("Fin de recherche : nombre max d'itérations atteint.")
            break

        #analyse de la courbe actuelle
        logger.info(f"Tentative de détection n°{len(planets_found) + 1} (itération {iteration})...")
        result = _run_bls_analysis(current_lc)
        logger.info(f"Analyse BLS terminée.")
        #critère de validation
        if result["snr"] > 7.1 :
            #Filtre alias : rejette si la période est trop proche d'une planète déjà trouvée
            is_alias = False
            matched_harmonic = None
            for known in planets_found:
                ratio = result["period"] / known["period"]
                #On vérifie si le ratio est proche d'un entier ou d'une fraction simple
                for harmonic in [1, 2, 3]:
                    if abs(ratio - harmonic) < 0.02:
                        is_alias = True
                        matched_harmonic = harmonic
                        break
                if is_alias:
                    break
            if is_alias:
                logger.warning(f"Signal rejeté (P={result['period']:.4f}j) — alias de P={known['period']:.4f}j (ratio={matched_harmonic}).")
                harmonic_alias_count += 1
                # Pour ratio≈1, on masque avec la durée de la planète originale
                # car le BLS sur le résidu peut retourner une durée aberrante
                if matched_harmonic == 1:
                    result["duration"] = known["duration"]
                current_lc = mask_planet(current_lc, result)
                if harmonic_alias_count >= 5:
                    logger.info("Fin de recherche : signal épuisé (3 alias consécutifs).")
                    break
                continue
            # Test binaire à éclipses AVANT ajout dans la liste
            baseline = current_lc.time.value.max() - current_lc.time.value.min()
            n_transits = baseline / result["period"]
            if n_transits >= 10 and abs(result["odd_even_ratio"] - 1.0) > 0.3:
                logger.warning(f"Signal rejeté (odd/even ratio = {result['odd_even_ratio']}) — probable binaire à éclipses.")
                current_lc = mask_planet(current_lc, result)
                continue

            logger.info(f"Planète détectée ! Période: {result['period']:.3f} j | SNR: {result['snr']:.2f}")
            planets_found.append(result)
            harmonic_alias_count = 0

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


      


