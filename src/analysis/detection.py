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
        return observation_time,max_period+=min_period,steps,min_period 
    return observation_time,max_period,steps,min_period 
    

def planet_detector(lc : lk.Light_Curve) : 
    pass