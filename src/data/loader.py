import lightkurve as lk
import logging

##gestion d'erreur
logger = logging.getLogger(__name__)

def download_target_data(star_name : str, period_index: None, author: str="Kepler") -> lk.LightCurve :         
    """
    Recherche, télécharge et assemble les données de courbe de lumière d'une cible spécifique pour différentes missions.

    Cette fonction s'adapte automatiquement à la mission spécifiée (Kepler, TESS ou K2) 
    en associant l'indice 'period_index' à l'unité temporelle correcte (Quarter, Sector ou Campaign).
    Les données sont normalisées individuellement avant d'être fusionnées (stitched) en une série temporelle unique.

    :param star_name: Le nom ou l'identifiant de l'étoile cible (ex: 'Kepler-10', 'TIC 261136679').
    :type star_name: str
    :param period_index: L'indice de la fenêtre d'observation. Si None, toutes les données disponibles sont récupérées.
    :type period_index: int, optionnel
    :param author: La mission ou le fournisseur de données ('Kepler', 'TESS' ou 'K2'). Par défaut "Kepler".
    :type author: str
    :return: Un objet LightCurve unique, fusionné et normalisé, contenant la photométrie de la cible.
    :rtype: lk.LightCurve
    :raises ValueError: Si aucune donnée n'est trouvée pour la cible et les paramètres de mission fournis.
    :raises Exception: Pour les erreurs liées au réseau ou spécifiques à la bibliothèque Lightkurve lors du téléchargement.

    **Exemple :**

    .. code-block:: python

        # Télécharger tous les quarters Kepler pour Kepler-10
        lc = download_target_data("Kepler-10", author="Kepler")
        
        # Télécharger un secteur TESS spécifique
        lc_tess = download_target_data("Pi Mensae", period_index=1, author="TESS")
    """
    try :

        mission_authors = {
            "kepler": "Kepler",
            "tess": "SPOC",
            "k2": "K2"
        }
        search_args = {
            "mission": author,
            "author": mission_authors.get(author.lower(), author)
        }

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