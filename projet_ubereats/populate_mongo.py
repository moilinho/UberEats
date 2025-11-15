# populate_mongo.py
import os, csv, uuid, re
import random # --- AJOUT ---
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

CSV_FILE = "data/ubereats.csv"  # Assurez-vous que le chemin est correct

def _clean_price(raw):
    """Transforme '15.99 USD' -> 15.99"""
    if not raw:
        return 0.0
    s = str(raw)
    match = re.findall(r"[0-9]+(?:[.,][0-9]+)?", s)
    if not match:
        return 0.0
    return float(match[0].replace(",", "."))

def populate(csv_file=CSV_FILE, limit=None):
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"{csv_file} introuvable. Assurez-vous que le chemin est correct.")

    # --- Connexion MongoDB ---
    load_dotenv()
    uri = os.getenv("MONGODB_URI")
    client = MongoClient(uri, server_api=ServerApi('1'))
    db = client.UberEats # IMPORTANT: Utilisez la bonne casse (UberEats ou ubereats)
    
    restaurants = db.restaurants
    menus = db.menus
    
    print("Connexion à MongoDB... Nettoyage des anciennes collections...")
    # On vide les collections pour éviter les doublons à chaque exécution
    restaurants.delete_many({})
    menus.delete_many({})
    
    # --- AJOUT : Création de l'index géospatial ---
    print("Création de l'index 2dsphere pour 'restaurants'...")
    restaurants.create_index([("location", "2dsphere")])
    # --- FIN AJOUT ---
    
    print(f"Début du chargement depuis {csv_file}...")

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        count_rest = 0
        count_menu = 0
        restaurants_cache = set() # Pour éviter d'insérer le même restaurant 100x

        for row in reader:
            if limit and count_menu >= limit:
                break
                
            rid = row.get("restaurant_id")
            if not rid:
                continue

            # --- 1. Insérer le restaurant (s'il est nouveau) ---
            if rid not in restaurants_cache:
                
                # --- AJOUT: Générer des coordonnées aléatoires (autour de Paris) ---
                lat = round(random.uniform(48.80, 48.90), 6)
                lon = round(random.uniform(2.25, 2.45), 6)
                # --- FIN AJOUT ---
                
                rest_doc = {
                    "_id": rid, # On utilise l'ID du restaurant comme _id
                    "name": f"Restaurant {rid}", # Le CSV ne fournit pas de vrai nom
                    "city": "Unknown", # Le CSV ne fournit pas de ville
                    "cuisine": row.get("category", "General"),
                    # --- AJOUT: Champ location au format GeoJSON ---
                    "location": {
                        "type": "Point",
                        "coordinates": [lon, lat] # IMPORTANT: [Longitude, Latitude]
                    }
                    # --- FIN AJOUT ---
                }
                try:
                    restaurants.insert_one(rest_doc)
                    restaurants_cache.add(rid)
                    count_rest += 1
                except Exception as e:
                    print(f"Erreur d'insertion restaurant: {e}")

            # --- 2. Insérer le menu ---
            menu_doc = {
                "_id": str(uuid.uuid4()),
                "restaurant_id": rid, # Lien vers le restaurant
                "item": row.get("name", "Unknown"),
                "category": row.get("category", "General"),
                "description": row.get("description", ""),
                "price": _clean_price(row.get("price")),
                "currency": "USD"
            }
            menus.insert_one(menu_doc)
            count_menu += 1
            
            if count_menu % 100 == 0:
                print(f"... {count_menu} menus insérés.")

    print(f"✅ Terminé. {count_rest} restaurants et {count_menu} menus insérés dans MongoDB.")

if __name__ == "__main__":
    populate(limit=500) # Limite à 500 menus pour un test rapide
