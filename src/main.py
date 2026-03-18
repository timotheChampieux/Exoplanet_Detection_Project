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

def run_pipeline():
    """
    Exécute le pipeline complet de détection d'exoplanètes.
    """
    print("\n" + "="*60)
    print("    EXOHUNTER v1.0    ")
    print("="*60 + "\n")

    try:
        #CONFIGURATION DE LA CIBLE 
        print("--- CONFIGURATION DE LA CIBLE ---")

        mission = input("Mission (Kepler, TESS, K2) [Défaut: Kepler] : ") or "Kepler"

        target_star = input("Nom de l'étoile (ex: Kepler-10, Pi Mensae) : ")
        if not target_star:
            raise ValueError("Le nom de l'étoile est obligatoire.")

        star_radius = input("Rayon de l'étoile (en R_sun) [Défaut: 1.0] : ")
        star_radius = float(star_radius) if star_radius else 1.0
        
        period_label = "Secteur" if mission.lower() == "tess" else "Quarter/Campaign"
        p_index = input(f"Sur quel {period_label} travaillons nous ? (laissez vide pour TOUT attention travailler sur beaucoup de donné demande beaucoup de ressources !) : ")
        period_index = int(p_index) if p_index else None

        # --- 2. CONFIGURATION DE L'ANALYSE ---
        print("\n--- CONFIGURATION DE L'ANALYSE ---")
        max_p = input("Nombre max de planètes à chercher [Défaut: 5] : (Si il y a beaucoup de planètes a trouver cela demandera beaucoup de ressources) ")
        max_p = int(max_p) if max_p else 5
        
        advanced = input("Modifier les paramètres experts ? (o/N) : ").lower()

        # Valeurs par défaut (Standard de recherche)
        sigma_val = 5
        win_len = 801
        pts_transit = 70

        if advanced == 'o':
            sigma_val = int(input("  > Seuil de nettoyage (Sigma) [Défaut: 5] : ") or 5)
            win_len = int(input("  > Fenêtre de lissage (Window Length) [Défaut: 401] : ") or 801)
            pts_transit = int(input("  > Résolution (Points par transit) [Défaut: 150] : ") or 70)

        # --- 3. EXÉCUTION DU PIPELINE ---
        
        # Étape A : Téléchargement
        logger.info(f"Étape 1 : Acquisition des données ({mission})...")
        lc_raw = download_target_data(target_star, author=mission, period_index=period_index)

        # Étape B : Nettoyage (Utilisation de win_len et sigma)
        logger.info(f"Étape 2 : Nettoyage (Sigma={sigma_val}, Window={win_len})...")
        lc_clean = lc_cleaner(lc_raw, window_length=win_len, sigma=sigma_val)

        # Étape C : Détection itérative
        logger.info(f"Étape 3 : Recherche itérative (Max {max_p} planètes)...")
        planets_found = planet_detector(lc_clean, max_planets=max_p)

        # Étape D : Métriques physiques
        if planets_found:
            logger.info(f"Étape 4 : Calcul des rayons (Résolution={pts_transit})...")
            # On passe pts_transit pour que metrics utilise ton binning adaptatif
            final_results = analyze_planets_metrics(
                lc_clean, 
                planets_found, 
                star_radius=star_radius, 
                points_per_transit=pts_transit
            )
            
            # --- 4. AFFICHAGE DES RÉSULTATS ---
            print("\n" + "!"*60)
            print(f"   RÉSULTATS DE L'ANALYSE POUR {target_star.upper()}")
            print("!"*60)
            
            for i, p in enumerate(final_results):
                print(f"\n[CANDIDATE {i+1}]")
                print(f" > Période orbitale : {p['period']:.4f} jours")
                print(f" > Rayon            : {p['rayon_terrestre']:.2f} R_terrestre ({p['rayon_km']:.0f} km)")
                print(f" > Profondeur       : {p['depth_ppm']:.0f} ppm")
                print(f" > Score (SNR)      : {p['snr']:.2f}")
                
                # Interprétation
                if p['rayon_terrestre'] < 1.5:
                    print(" > Nature probable  : Rocheuse (Tellurique)")
                elif p['rayon_terrestre'] < 4.0:
                    print(" > Nature probable  : Neptune-like / Super-Terre")
                else:
                    print(" > Nature probable  : Géante Gazeuse")
        else:
            print(f"\nAucune planète détectée pour {target_star} avec un SNR > 7.")

    except ValueError as ve:
        logger.error(f"Erreur de saisie : {ve}")
    except Exception as e:
        logger.error(f"Erreur système : {e}")

    print("\n" + "="*60)
    print("                ANALYSE TERMINÉE")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_pipeline()