import lightkurve as lk
import logging
import numpy as np 
##gestion d'erreur
logger = logging.getLogger(__name__)

def _get_search_params(lc : lk.LightCurve) :

    observation_time = lc.time.value.max() - lc.time.value.min()

    max_period = observation_time/3
    min_period = 0.5
    steps = int(observation_time * 500)

    if max_period < min_period :
        return max_period+=min_period,steps,min_period

    return max_period,steps,min_period 
    
def _mask_planet(lc, planet_info) :

    period,transit_time,duration = planet_info["period"],planet_info["transit_time"],planet_info["duration"]

    masque = lc.create_transit_mask(period=period, transit_time=transit_time*2, duration=duration)
    
    lc_propre = lc[~masque]
    return lc_propre

def planet_detector(lc : lk.LightCurve) : 

    max_p, steps,min_p  = _get_search_params(lc)

    periods =  np.linspace(min_p,max_p,steps)
    bls = lc.to_periodogram(method='bls',period=periods)
    
    best_period = bls.period_at_max_power
    best_t0 = bls.transit_time_at_max_power
    best_duration = bls.duration_at_max_power

    stats = bls.compute_stats(period=best_period, 
                              duration=best_duration, 
                              transit_time=best_t0)

    snr = stats['snr']

    result = {
        "period": best_period.value,
        "transit_time": best_t0.value,
        "duration": best_duration.value,
        "snr": snr,
        "max_power": bls.max_power.value
    }
    
    return result


