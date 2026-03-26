import lightkurve as lk
import logging
import numpy as np 

##gestion de log
logger = logging.getLogger(__name__)

def _run_bls_analysis(lc : lk.LightCurve, frequency_factor: int = 10, minimum_period: float = 0.7,min_transits: int = 3) -> dict :
    """
    Exécute l'algorithme BLS (Box Least Squares) pour détecter des signaux de transits périodiques.

    Cette fonction calcule un périodogramme BLS sur une grille de fréquences optimisée. Elle extrait 
    les paramètres du meilleur candidat (période, époque, durée) et calcule des statistiques 
    de validation, notamment le rapport de profondeur entre les transits pairs et impairs 
    (Odd/Even depth ratio) pour aider à identifier les binaires à éclipses.

    :param lc: La courbe de lumière nettoyée et détrendée à analyser.
    :type lc: lk.LightCurve
    :param frequency_factor: Facteur de suréchantillonnage de la grille de fréquences. 
                             Une valeur plus élevée augmente la précision mais ralentit le calcul.
    :type frequency_factor: int
    :param minimum_period: Période orbitale minimale pour la recherche (en jours).
    :type minimum_period: float
    :param min_transits: Nombre minimum de transits requis dans la durée totale d'observation 
                         pour définir la période maximale de recherche.
    :type min_transits: int
    :return: Un dictionnaire contenant :
        * ``period``: La meilleure période détectée (jours).
        * ``transit_time``: L'époque du premier transit (BJD).
        * ``duration``: La durée du transit (jours).
        * ``snr``: Le rapport signal sur bruit du pic BLS.
        * ``max_power``: La puissance maximale du périodogramme.
        * ``depth_bls``: La profondeur du transit estimée par le modèle BLS.
        * ``odd_even_ratio``: Ratio de profondeur pair/impair (proche de 1.0 pour une planète).
    :rtype: dict

    **Exemple :**

    .. code-block:: python

        # Analyse d'une courbe avec une recherche ciblée sur les périodes courtes
        results = _run_bls_analysis(lc_clean, frequency_factor=20, minimum_period=0.5)
        
        if results["snr"] > 7.1:
            print(f"Signal trouvé à P = {results['period']:.2f} jours")
    """
    # Securité : verifier qu'il ya assez de points pour un BLS
    if len(lc) < 50:
        logger.warning(f"Courbe trop courte ({len(lc)} points) pour un BLS fiable.")
        return {"snr": 0, "period": 0, "transit_time": 0, "duration": 0,
                "max_power": 0, "depth_bls": 0, "odd_even_ratio": 1.0}

     #beaucoup plus précis que np.linspace pour détecter les transits courts.
    bls = lc.to_periodogram(method='bls', minimum_period=minimum_period, maximum_period=(lc.time.value.max() - lc.time.value.min())/min_transits, frequency_factor=frequency_factor)    #on recup le meilleur condidat
    best_period = bls.period_at_max_power
    best_t0 = bls.transit_time_at_max_power
    best_duration = bls.duration_at_max_power

    # Calcul des stats pour obtenir le bon SNR 
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

def mask_planet(lc : lk.LightCurve, planet_info : dict, mask_width: float = 3.0) ->  lk.LightCurve :    
    """
    Masque les transits d'une planète spécifique pour permettre la recherche itérative de signaux plus faibles.

    Cette fonction calcule manuellement la phase orbitale pour identifier et supprimer les points de données 
    situés dans la fenêtre de transit. Elle utilise une approche par tableaux NumPy bruts pour contourner 
    les limitations de protection mémoire d'Astropy, garantissant une reconstruction propre de la 
    courbe de lumière (LightCurve).

    .. note::
        L'utilisation d'un multiplicateur de durée (``mask_width``) permet de couvrir largement 
        les phases d'entrée et de sortie (ingress/egress) ainsi que d'éventuelles variations 
        de l'époque du transit (TTVs mineurs), assurant qu'aucun résidu du signal primaire 
        ne vienne polluer la détection BLS suivante.

    :param lc: La courbe de lumière contenant les signaux à masquer.
    :type lc: lk.LightCurve
    :param planet_info: Dictionnaire contenant les paramètres du transit ('period', 'transit_time', 'duration').
    :type planet_info: dict
    :param mask_width: Facteur multiplicateur appliqué à la durée du transit pour définir la largeur du masque. 
                       Une valeur de 3.0 est un standard robuste (TLS/Kepler).
    :type mask_width: float
    :return: Une nouvelle instance de LightCurve dont les points en transit ont été supprimés.
    :rtype: lk.LightCurve

    **Exemple :**

    .. code-block:: python

        # Informations sur la planète la plus massive détectée
        p1_info = {"period": 10.5, "transit_time": 2457000.5, "duration": 0.12}
        
        # Masquage pour chercher une seconde planète
        lc_multi = mask_planet(lc_clean, p1_info, mask_width=2.5)
        
        # Lancement de la détection suivante sur le signal résiduel
        next_planet = _run_bls_analysis(lc_multi)
    """
    period = planet_info["period"]
    t0 = planet_info["transit_time"]
    mask_half_width = planet_info["duration"] * mask_width
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

def planet_detector(lc : lk.LightCurve, max_planets=10, frequency_factor: int = 10, minimum_period: float = 0.7, snr_threshold: float = 7.1, mask_width: float = 3.0, max_alias: int = 5,min_transits: int = 3) -> list :  
    """
    Exécute une recherche itérative d'exoplanètes par déshabillage de la courbe de lumière (Iterative BLS).

    Cette fonction est le moteur de détection principal. Elle cherche le signal périodique le plus fort, 
    vérifie sa validité via des tests de rapport signal/bruit (SNR), d'alias harmoniques et de symétrie 
    de transit (Odd/Even depth ratio). Si le signal est validé, il est ajouté à la liste des candidats 
    et masqué de la courbe de lumière pour permettre la détection de signaux plus faibles lors de 
    l'itération suivante.

    .. note::
        La fonction intègre deux filtres de protection critiques :
        1. **Filtre d'Alias** : Empêche de compter plusieurs fois la même planète si le BLS accroche une harmonique (ex: 2x ou 3x la période réelle).
        2. **Vetting Odd/Even** : Rejette les binaires à éclipses dont les transits pairs et impairs ont des profondeurs statistiquement différentes.

    :param lc: La courbe de lumière nettoyée et normalisée.
    :type lc: lk.LightCurve
    :param max_planets: Nombre maximum de planètes uniques à rechercher.
    :type max_planets: int
    :param frequency_factor: Précision de la grille de fréquences du périodogramme BLS.
    :type frequency_factor: int
    :param minimum_period: La période orbitale la plus courte à explorer (en jours).
    :type minimum_period: float
    :param snr_threshold: Le seuil de détection (SNR) en dessous duquel la recherche s'arrête. 
                          7.1 est le standard statistique de la mission Kepler.
    :type snr_threshold: float
    :param mask_width: Multiplicateur de la durée du transit pour définir la largeur du masquage.
    :type mask_width: float
    :param max_alias: Nombre maximum d'alias consécutifs autorisés avant l'arrêt de la recherche.
    :type max_alias: int
    :param min_transits: Nombre minimum de transits requis pour valider une période maximale.
    :type min_transits: int
    :return: Une liste de dictionnaires, chaque dictionnaire contenant les paramètres physiques d'un candidat validé.
    :rtype: list

    **Exemple :**

    .. code-block:: python

        # Recherche de 3 planètes max avec un seuil de confiance élevé
        candidates = planet_detector(
            lc_clean, 
            max_planets=3, 
            snr_threshold=8.5, 
            minimum_period=0.5
        )
        
        for p in candidates:
            print(f"Planète validée : P={p['period']:.3f} j, SNR={p['snr']:.1f}")
    """

    planets_found = []
    current_lc = lc
    harmonic_alias_count = 0  # Compteur pour les vrais alias harmoniques 
    max_iterations = 2 * max_planets + 6 
    iteration = 0
    while len(planets_found) < max_planets : 
        iteration += 1
        if iteration > max_iterations:
            logger.info("Fin de recherche : nombre max d'itérations atteint.")
            break

        #analyse de la courbe actuelle
        logger.info(f"Tentative de détection n°{len(planets_found) + 1} (itération {iteration})...")
        result = _run_bls_analysis(current_lc, frequency_factor=frequency_factor, minimum_period=minimum_period,min_transits=min_transits)       
        logger.info(f"Analyse BLS terminée.")
        #critère de validation
        if result["snr"] > snr_threshold :
                        #Filtre alias : rejette si la période est trop proche d'une planète déjà trouver
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
                #Pour ratio+-1, on masque avec la durée de la planète originale
                # car le BLS sur le résidu peut retourner une durée de fou
                if matched_harmonic == 1:
                    result["duration"] = known["duration"]
                current_lc = mask_planet(current_lc, result, mask_width=mask_width)
                if harmonic_alias_count >= max_alias:
                    logger.info(f"Fin de recherche : signal épuisé ({max_alias} alias consécutifs).")
                    break
                continue
            # Test binaire a éclipes avant ajout dans la liste
            baseline = current_lc.time.value.max() - current_lc.time.value.min()
            n_transits = baseline / result["period"]
            if result["odd_even_ratio"] < 0:
                logger.warning(f"Signal rejeté (odd/even ratio = {result['odd_even_ratio']:.3f}) — artefact (ratio négatif).")
                current_lc = mask_planet(current_lc, result, mask_width=mask_width)
                continue

            if n_transits >= 10 and abs(result["odd_even_ratio"] - 1.0) > 0.3:
                logger.warning(f"Signal rejeté (odd/even ratio = {result['odd_even_ratio']}) — probable binaire à éclipses.")
                current_lc = mask_planet(current_lc, result, mask_width=mask_width)
                continue

            logger.info(f"Planète détectée ! Période: {result['period']:.3f} j | SNR: {result['snr']:.2f}")
            planets_found.append(result)
            harmonic_alias_count = 0

            #On masque la planète pour le tour suivant
            if max_planets > 1 :
                logger.info("Début du masquage de la planète...")
                current_lc = mask_planet(current_lc, result, mask_width=mask_width)
                logger.info("Masquage réussi.")
                
        else : 
            if len(planets_found) == 0 : 
                logger.info("Fin de recherche : aucun signal significatif.")
            else : 
                logger.info("Fin de recherche : aucun signal supplémentaire significatif.")
            break

    return planets_found


      


