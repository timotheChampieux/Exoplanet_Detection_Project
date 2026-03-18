import lightkurve as lk
import logging

##gestion d'erreur
logger = logging.getLogger(__name__)

def download_target_data(star_name : str, period_index: int = None, author: str="Kepler") -> lk.LightCurve :         
    """ 
    Recherche, telecharge, assemble data d'une étoile pour un quarter donné et s'adapte a la mission (Kepler, TESS,K2)
    """
    try :

        search_args = {"author": author}

        if period_index is not None:
            # TESS utilise 'sector', Kepler utilise 'quarter', K2 utilise 'campaign'
            if author.lower() == "tess":
                search_args["sector"] = period_index
            elif author.lower() == "k2":
                search_args["campaign"] = period_index
            else:
                search_args["quarter"] = period_index
        #si quarter est none search renvoie tout les quarter
        search = lk.search_lightcurve(star_name, **search_args)
        
        #si la recherche est vide on renvoie une error
        if len(search) == 0 :
            raise ValueError(f"Aucune donnée trouvée pour {star_name} ({author}).")


        lc_collection = search.download_all()
        lc = lc_collection.stitch(corrector_func=lambda x: x.normalize())        
        #on informe que c'est tout bon
        logger.info(f"Données {author} téléchargées pour {star_name}")
        
        return lc

    except Exception as e :
            #si jamais erreur reseau ou autre
        logger.error(f"Erreur lors du téléchargement : {e}")
        raise