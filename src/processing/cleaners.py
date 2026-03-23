import lightkurve as lk
import logging
import numpy as np
##gestion d'erreur
logger = logging.getLogger(__name__)

def _strip_astropy_masks(lc: lk.LightCurve) -> lk.LightCurve:
    """
    Convertit les maskedNDArray Astropy en numpy arrays 
    pour eviter le bug 'cannot write to unmasked output'
    introduit par Astropy 5.0 avec les MaskedQuantity
    """
   
    return lk.LightCurve(
        time=np.asarray(lc.time.value, dtype=float),
        flux=np.asarray(lc.flux.value, dtype=float),
        flux_err=np.asarray(lc.flux_err.value, dtype=float),
        meta=lc.meta
    )

def lc_cleaner(lc : lk.LightCurve, window_length:int = 801, sigma: float = 5) -> lk.LightCurve :
    """ 
    Nettoie la courbe de lumière. Attention : window_length doit être > 3x la durée d'un transit. 
    """
    try: 
        #On garde le nombre de point pour verifier que le cleaner n'a pas enlevé tout la courbe par erreur
        initial_length = len(lc)
        
        #on nettoie (outliers retire les pics de lumière parasite et flatten corrige les variation de l'etoile)
        lc_clean = lc.flatten(window_length=window_length).remove_outliers(sigma=sigma)
        
        final_length = len(lc_clean)
        
        logger.info(f"Nettoyage terminé : {initial_length - final_length} points retirés.")

        return _strip_astropy_masks(lc_clean)
    
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de la courbe : {e}")
        raise