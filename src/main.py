import logging
import sys

from analysis.detection import planet_detector
from data.loader import download_target_data
from processing.cleaners import lc_cleaner
from analysis.metrics import analyze_planets_metrics


# Configuration du logging principal pour l'affichage console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ExoHunter")


def _ask_float(prompt: str, default: float) -> float:
    """
    Sollicite une saisie de type flottant auprès de l'utilisateur avec une valeur par défaut.

    Cette fonction utilitaire affiche un message d'invite dans la console. Si l'utilisateur 
    valide sans rien saisir (chaîne vide), la valeur spécifiée dans l'argument ``default`` 
    est retournée. Elle est particulièrement utile pour les paramètres physiques comme 
    le rayon stellaire ou les seuils de détection.

    :param prompt: Le message d'invite à afficher à l'écran.
    :type prompt: str
    :param default: La valeur flottante à utiliser par défaut.
    :type default: float
    :return: Le nombre flottant saisi par l'utilisateur ou la valeur par défaut.
    :rtype: float
    :raises ValueError: Si la saisie de l'utilisateur contient des caractères non numériques 
                        ne pouvant pas être convertis en flottant.

    **Exemple :**

    .. code-block:: python

        # Demande le rayon de l'étoile avec 1.0 par défaut
        r_star = _ask_float("Rayon de l'étoile (R_sun)", 1.0)
        
        # Si l'utilisateur valide directement, r_star vaudra 1.0
    """
    val = input(f"{prompt} [Défaut: {default}] : ")
    return float(val) if val.strip() else default

def _ask_int(prompt: str, default: int) -> int:
    """
    Sollicite une saisie de type entier auprès de l'utilisateur avec une valeur par défaut.

    Cette fonction utilitaire affiche un message d'invite dans la console et récupère l'entrée 
    standard. Si l'utilisateur valide sans rien saisir (chaîne vide), la valeur fournie 
    dans l'argument ``default`` est retournée.

    :param prompt: Le message d'invite à afficher à l'écran.
    :type prompt: str
    :param default: La valeur entière à utiliser par défaut.
    :type default: int
    :return: L'entier saisi par l'utilisateur ou la valeur par défaut.
    :rtype: int
    :raises ValueError: Si la saisie de l'utilisateur n'est pas convertible en nombre entier.

    **Exemple :**

    .. code-block:: python

        # Demande le nombre de planètes avec 5 par défaut
        nb_planetes = _ask_int("Nombre de planètes à chercher", 5)
        
        # Si l'utilisateur appuie sur Entrée sans saisir de texte, nb_planetes = 5
    """"""
    Sollicite une saisie de type entier auprès de l'utilisateur avec une valeur par défaut.

    Cette fonction utilitaire affiche un message d'invite dans la console et récupère l'entrée 
    standard. Si l'utilisateur valide sans rien saisir (chaîne vide), la valeur fournie 
    dans l'argument ``default`` est retournée.

    :param prompt: Le message d'invite à afficher à l'écran.
    :type prompt: str
    :param default: La valeur entière à utiliser par défaut.
    :type default: int
    :return: L'entier saisi par l'utilisateur ou la valeur par défaut.
    :rtype: int
    :raises ValueError: Si la saisie de l'utilisateur n'est pas convertible en nombre entier.

    **Exemple :**

    .. code-block:: python

        # Demande le nombre de planètes avec 5 par défaut
        nb_planetes = _ask_int("Nombre de planètes à chercher", 5)
        
        # Si l'utilisateur appuie sur Entrée sans saisir de texte, nb_planetes = 5
    """
    val = input(f"{prompt} [Défaut: {default}] : ")
    return int(val) if val.strip() else default


def run_pipeline():
    """
    Orchestre le pipeline complet de détection et de caractérisation d'exoplanètes de manière interactive.

    Cette fonction pilote l'interface utilisateur en ligne de commande (CLI) pour configurer 
    et exécuter les quatre étapes critiques de l'analyse :
    
    1. **Acquisition** : Téléchargement des données via ``download_target_data``.
    2. **Prétraitement** : Nettoyage et détrendage via ``lc_cleaner``.
    3. **Recherche** : Détection itérative par algorithme BLS via ``planet_detector``.
    4. **Caractérisation** : Calcul des rayons et classification physique via ``analyze_planets_metrics``.

    Le pipeline intègre des filtres de sécurité contre les alias harmoniques et fournit une 
    classification automatique des candidats (Super-Terre, Mini-Neptune, etc.) basée sur 
    le rayon planétaire calculé. Des avertissements astrophysiques sont générés en cas de 
    suspicion de faux positifs (binaires à éclipses ou artefacts de bruit).

    :raises ValueError: Si le nom de la cible est manquant ou si les saisies numériques sont invalides.
    :raises KeyboardInterrupt: Permet une interruption propre par l'utilisateur (Ctrl+C).
    :raises Exception: Capture et logue toute erreur systémique ou liée aux bibliothèques astrophysiques.

    **Déroulement technique :**

    .. code-block:: text

        1. Saisie des paramètres cibles (Nom, Mission, Rayon stellaire).
        2. Configuration optionnelle des hyperparamètres experts (Sigma, Window, SNR).
        3. Exécution séquentielle des modules de 'src/'.
        4. Affichage d'un rapport détaillé par candidat détecté.

    **Exemple d'utilisation :**

    .. code-block:: python

        if __name__ == "__main__":
            run_pipeline()
    """
    print("\n" + "="*60)
    print("          EXOHUNTER v2.0")
    print("   Pipeline de détection d'exoplanètes")
    print("="*60 + "\n")

    try:
        # =============================================
        # 1. CIBLE
        # =============================================
        print("--- CIBLE ---\n")

        mission = input("Mission (Kepler, TESS, K2) [Défaut: Kepler] : ").strip() or "Kepler"

        target_star = input("Nom de l'étoile (ex: Kepler-10, Pi Mensae) : ").strip()
        if not target_star:
            raise ValueError("Le nom de l'étoile est obligatoire.")

        print("\n  ℹ️  Le rayon stellaire est crucial pour le calcul du rayon planétaire.")
        print("      Consultez le NASA Exoplanet Archive ou Simbad pour une valeur précise.")
        print("      Une erreur de 10% sur le rayon stellaire = 10% d'erreur sur le rayon planétaire.\n")
        star_radius = _ask_float("Rayon de l'étoile (en R_sun)", 1.0)

        period_label = "Secteur" if mission.lower() == "tess" else "Quarter/Campaign"
        print(f"\n  ℹ️  Plus de {period_label}s = plus de transits = meilleure précision.")
        print("      Mais le temps de calcul augmente fortement (x2 par période ajoutée).")
        print("      Recommandation : 2-4 périodes pour commencer.\n")
        p_index = input(f"  {period_label}(s) (ex: 2 ou 2,5,7 — vide pour TOUT) : ")
        if p_index.strip():
            period_index = [int(x.strip()) for x in p_index.split(",")]
            if len(period_index) == 1:
                period_index = period_index[0]
        else:
            period_index = None

        # =============================================
        # 2. DÉTECTION
        # =============================================
        print("\n--- DÉTECTION ---\n")

        max_p = _ask_int("Nombre max de planètes à chercher", 5)

        print("\n  Voulez-vous configurer les paramètres avancés ?")
        print("  Les valeurs par défaut conviennent à la majorité des cas.\n")
        advanced = input("  Paramètres avancés ? (o/N) : ").strip().lower()

        # --- Valeurs par défaut ---
        # Nettoyage
        sigma_val = 5.0
        win_len = 801
        # Détection BLS
        freq_factor = 10
        min_period = 0.7
        snr_threshold = 7.1
        mask_width = 3.0
        max_alias = 5
        min_transits = 3
        # Métriques
        pts_transit = 70

        if advanced == 'o':
            print("\n" + "-"*50)
            print("  NETTOYAGE DE LA COURBE")
            print("-"*50)

            print("\n  ℹ️  Sigma : seuil de rejet des points aberrants.")
            print("      Plus bas = plus agressif (risque de couper des transits profonds).")
            print("      Plus haut = plus permissif (garde plus de bruit).")
            print("      Standard : 5. Étoile active/bruitée : 3-4. Signal faible : 6-7.")
            sigma_val = _ask_float("  Sigma", 5.0)

            print("\n  ℹ️  Fenêtre de lissage : taille du filtre pour corriger la variabilité stellaire.")
            print("      DOIT être > 3x la durée du transit le plus long attendu.")
            print("      Trop petit = écrase les transits (underfitting dangereux).")
            print("      Trop grand = laisse des tendances longues (bruit résiduel).")
            print("      Standard : 801 (~2j pour Kepler long cadence).")
            win_len = _ask_int("  Fenêtre de lissage (Window Length)", 801)

            print("\n" + "-"*50)
            print("  RECHERCHE BLS")
            print("-"*50)

            print("\n  ℹ️  Frequency factor : densité de la grille de recherche en fréquence.")
            print("      Plus élevé = calcul plus rapide mais grille plus grossière.")
            print("      Trop élevé = risque de rater des signaux faibles (SNR < 15).")
            print("      Standard : 10. Signaux forts (SNR > 30) : 15-20. Signaux faibles : 5-8.")
            print("      Impact direct sur le temps de calcul (x2 si divisé par 2).")
            freq_factor = _ask_int("  Frequency factor", 10)

            print("\n  ℹ️  Transits minimum : nombre minimum de transits exigé dans la baseline.")
            print("      Détermine la période maximale cherchée (baseline / min_transits).")
            print("      3 = conservateur, rejette les faux positifs longue période.")
            print("      2 = nécessaire si la planète a une période > 1/3 de la baseline.")
            print("      Standard : 3. K2 campaigns ou TESS secteur unique : 2.")
            min_transits = _ask_int("  Transits minimum", 3)

            print("\n  ℹ️  Période minimale de recherche (en jours).")
            print("      Standard : 0.7j. Planètes ultra-courtes (USP) : 0.3-0.5j.")
            print("      Baisser cette valeur augmente significativement le temps de calcul.")
            min_period = _ask_float("  Période minimale (jours)", 0.7)

            print("\n  ℹ️  Seuil SNR : signal minimum pour considérer un candidat.")
            print("      Standard scientifique : 7.0-7.5.")
            print("      Plus bas = plus de candidats mais plus de faux positifs.")
            print("      Plus haut = moins de faux positifs mais risque de rater des petites planètes.")
            snr_threshold = _ask_float("  Seuil SNR", 7.1)

            print("\n  ℹ️  Largeur du masque de transit (multiplicateur de la durée).")
            print("      Contrôle la zone masquée autour de chaque transit détecté.")
            print("      Trop petit (< 2) = résidus de transit qui polluent la recherche suivante.")
            print("      Trop grand (> 4) = perte de données, profondeur sous-estimée.")
            print("      Standard : 3.0. Planète à période ultra-courte (beaucoup de transits) : 3-4.")
            print("      Planète à longue période (peu de transits) : 2.0.")
            mask_width = _ask_float("  Largeur du masque", 3.0)

            print("\n  ℹ️  Alias consécutifs max : nombre de faux signaux tolérés avant d'arrêter.")
            print("      Le BLS peut retrouver des résidus de planètes déjà masquées.")
            print("      Standard : 5. Si planète ultra-courte (P < 1j) détectée en premier : 5-8.")
            max_alias = _ask_int("  Alias consécutifs max", 5)

            print("\n" + "-"*50)
            print("  MESURE DES RAYONS")
            print("-"*50)

            print("\n  ℹ️  Points par transit : résolution du repliement de phase pour mesurer la profondeur.")
            print("      Plus élevé = plus précis mais nécessite beaucoup de transits.")
            print("      Standard : 70. Peu de transits (< 5) : 30-50. Beaucoup (> 50) : 100-150.")
            pts_transit = _ask_int("  Points par transit", 70)

        # =============================================
        # 3. RÉSUMÉ DE CONFIGURATION
        # =============================================
        print("\n" + "-"*60)
        print("  RÉSUMÉ DE LA CONFIGURATION")
        print("-"*60)
        print(f"  Cible          : {target_star} ({mission})")
        print(f"  Rayon stellaire: {star_radius} R_sun")
        print(f"  Périodes       : {period_index if period_index else 'TOUTES'}")
        print(f"  Max planètes   : {max_p}")
        if advanced == 'o':
            print(f"  Sigma          : {sigma_val}")
            print(f"  Window length  : {win_len}")
            print(f"  Freq. factor   : {freq_factor}")
            print(f"  Période min    : {min_period}j")
            print(f"  Seuil SNR      : {snr_threshold}")
            print(f"  Largeur masque : {mask_width}x")
            print(f"  Max alias      : {max_alias}")
            print(f"  Pts/transit    : {pts_transit}")
            print(f"  Min transits   : {min_transits}")

        print("-"*60)
        
        confirm = input("\n  Lancer l'analyse ? (O/n) : ").strip().lower()
        if confirm == 'n':
            print("  Analyse annulée.")
            return

        # =============================================
        # 4. EXÉCUTION DU PIPELINE
        # =============================================
        print()

        # Étape 1 : Téléchargement
        logger.info(f"Étape 1/4 : Acquisition des données ({mission})...")
        lc_raw = download_target_data(target_star, author=mission, period_index=period_index)

        # Étape 2 : Nettoyage
        logger.info(f"Étape 2/4 : Nettoyage (Sigma={sigma_val}, Window={win_len})...")
        lc_clean = lc_cleaner(lc_raw, window_length=win_len, sigma=sigma_val)

        # Étape 3 : Détection itérative
        logger.info(f"Étape 3/4 : Recherche itérative (Max {max_p} planètes)...")
        planets_found = planet_detector(
            lc_clean, 
            max_planets=max_p,
            frequency_factor=freq_factor,
            minimum_period=min_period,
            snr_threshold=snr_threshold,
            mask_width=mask_width,
            max_alias=max_alias,
            min_transits=min_transits
        )

        # Étape 4 : Métriques physiques
        if planets_found:
            logger.info(f"Étape 4/4 : Calcul des rayons (Résolution={pts_transit} pts/transit)...")
            final_results = analyze_planets_metrics(
                lc_clean, 
                planets_found, 
                star_radius=star_radius, 
                points_per_transit=pts_transit
            )
            
            # =============================================
            # 5. RÉSULTATS
            # =============================================
            print("\n" + "="*60)
            print(f"  RÉSULTATS — {target_star.upper()} ({mission})")
            print(f"  {len(final_results)} candidat(s) détecté(s)")
            print("="*60)
            
            for i, p in enumerate(final_results):
                print(f"\n  {'─'*50}")
                print(f"  CANDIDAT {i+1}")
                print(f"  {'─'*50}")
                print(f"  Période orbitale  : {p['period']:.4f} jours")
                print(f"  Rayon             : {p['rayon_terrestre']:.2f} R_terre ({p['rayon_km']:.0f} km)")
                print(f"  Profondeur        : {p['depth_ppm']:.0f} ppm")
                print(f"  SNR               : {p['snr']:.2f}")
                print(f"  Ratio pair/impair : {p['odd_even_ratio']:.3f}")
                
                # Classification
                r = p['rayon_terrestre']
                if r < 1.25:
                    nature = "Sous-Terre / Rocheuse"
                elif r < 2.0:
                    nature = "Terre / Super-Terre (probablement rocheuse)"
                elif r < 4.0:
                    nature = "Mini-Neptune (enveloppe gazeuse probable)"
                elif r < 10.0:
                    nature = "Neptune-like (géante de glace)"
                else:
                    nature = "Géante gazeuse (type Jupiter)"
                print(f"  Nature probable   : {nature}")

                # Avertissements
                if p['snr'] < 10:
                    print(f"  ⚠️  SNR faible — candidat à confirmer avec plus de données.")
                if p['odd_even_ratio'] > 1.2 or p['odd_even_ratio'] < 0.8:
                    baseline = lc_clean.time.value.max() - lc_clean.time.value.min()
                    n_tr = baseline / p['period']
                    if n_tr >= 10:
                        print(f"  ⚠️  Ratio pair/impair suspect ({p['odd_even_ratio']:.2f}) — vérifier si binaire à éclipses.")
                    else:
                        print(f"  ℹ️  Ratio pair/impair variable ({p['odd_even_ratio']:.2f}) — normal avec peu de transits ({n_tr:.0f}).")

        else:
            print(f"\n  Aucune planète détectée pour {target_star} avec un SNR > {snr_threshold}.")
            print("  Suggestions :")
            print("    - Ajouter des périodes d'observation pour augmenter le SNR")
            print("    - Baisser le seuil SNR (risque de faux positifs)")
            print("    - Vérifier le nom de la cible et la mission")

    except ValueError as ve:
        logger.error(f"Erreur de saisie : {ve}")
    except KeyboardInterrupt:
        print("\n\n  Analyse interrompue par l'utilisateur.")
    except Exception as e:
        logger.error(f"Erreur système : {e}")

    print("\n" + "="*60)
    print("              ANALYSE TERMINÉE")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_pipeline()
