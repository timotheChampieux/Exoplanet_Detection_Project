import lightkurve as lk
import logging
import numpy as np
##gestion d'erreur
logger = logging.getLogger(__name__)

def _strip_astropy_masks(lc: lk.LightCurve) -> lk.LightCurve:
    """
    Convertit les tableaux masqués d'Astropy en tableaux NumPy standards pour résoudre les conflits d'écriture mémoire.

    Cette fonction technique extrait les valeurs brutes (time, flux, flux_err) afin de contourner le bug
    'cannot write to unmasked output' introduit par les MaskedQuantity dans Astropy 5.0+.
    Elle garantit que la courbe de lumière est reconstruite sur une nouvelle allocation mémoire, 
    permettant des opérations itératives de masquage sans erreurs de protection de données.

    :param lc: La courbe de lumière source contenant des données potentiellement masquées par Astropy.
    :type lc: lk.LightCurve
    :return: Une nouvelle instance de LightCurve reconstruite avec des tableaux NumPy classiques (non masqués).
    :rtype: lk.LightCurve

    **Exemple :**

    .. code-block:: python

        # Après avoir appliqué un masque de transit
        lc_filtree = lc[~mon_masque]
        
        # Nettoyage de la structure mémoire pour permettre une nouvelle détection BLS
        lc_propre = _strip_astropy_masks(lc_filtree)
    """
   
    return lk.LightCurve(
        time=np.asarray(lc.time.value, dtype=float),
        flux=np.asarray(lc.flux.value, dtype=float),
        flux_err=np.asarray(lc.flux_err.value, dtype=float),
        meta=lc.meta
    )

def lc_cleaner(lc : lk.LightCurve, window_length:int = 801, sigma: float = 5) -> lk.LightCurve :
    """
    Nettoie et détrend la courbe de lumière pour isoler les signaux de transit.

    Cette fonction applique un filtre de Savitzky-Golay via la méthode ``flatten()`` pour corriger 
    les variations de flux à basse fréquence (variabilité stellaire, dérives instrumentales). 
    Elle procède ensuite à un sigma-clipping pour supprimer les points aberrants (outliers).
    Enfin, elle appelle ``_strip_astropy_masks`` pour garantir une structure mémoire NumPy propre.

    .. note::
        Pour préserver l'intégrité du signal, ``window_length`` doit impérativement être supérieur 
        à 3 fois la durée attendue du transit le plus long. Une fenêtre trop courte risque de 
        "lisser" le transit et d'en réduire artificiellement la profondeur.

    :param lc: La courbe de lumière brute ou pré-traitée à nettoyer.
    :type lc: lk.LightCurve
    :param window_length: Nombre de points pour la fenêtre de lissage (doit être un entier impair).
    :type window_length: int
    :param sigma: Seuil d'écarts-types utilisé pour le rejet des points aberrants.
    :type sigma: float
    :return: Une courbe de lumière normalisée, détrendée et sans outliers.
    :rtype: lk.LightCurve
    :raises Exception: Si une erreur survient lors du processus de filtrage ou de normalisation.

    **Exemple :**

    .. code-block:: python

        # Nettoyage avec une fenêtre large pour une étoile stable
        lc_propre = lc_cleaner(lc_raw, window_length=801, sigma=5.0)
        
        # Pour une étoile très active, on pourrait réduire window_length
        # tout en restant vigilant sur la durée du transit.
    """
    try: 
        #On garde le nombre de point pour verifier que le cleaner n'a pas enlevé tout la courbe par erreur
        initial_length = len(lc)
        
        #on nettoie (outliers retire les pics de lumière parasite et flatten corrige les variation de l'etoile
        lc_clean = lc.flatten(window_length=window_length).remove_outliers(sigma=sigma)
        
        final_length = len(lc_clean)
        
        logger.info(f"Nettoyage terminé : {initial_length - final_length} points retirés.")

        return _strip_astropy_masks(lc_clean)
    
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de la courbe : {e}")
        raise