# populate_redis.py
import os, csv, uuid, re
import redis
import random # --- AJOUT ---

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

CSV_FILE = "data/ubereats.csv"   # ton fichier Kaggle

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
        raise FileNotFoundError(f"{csv_file} introuvable")

    # --- AJOUT: Nettoyage de la base Redis ---
    print("Nettoyage de la base Redis (FLUSHDB)...")
    r.flushdb()
    # --- FIN AJOUT ---

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count_rest = 0
        count_menu = 0
        
        print(f"Début du chargement depuis {csv_file}...")
        
        for row in reader:
            if limit and count_menu >= limit:
                break
            rid = row.get("restaurant_id")
            if not rid:
                continue
                
            rest_key = f"restaurant:{rid}"

            # --- AJOUT: Insérer le restaurant (si nouveau) ---
            if not r.exists(rest_key):
                # --- AJOUT: Coordonnées Géo ---
                lat = round(random.uniform(48.80, 48.90), 6)
                lon = round(random.uniform(2.25, 2.45), 6)
                # --- FIN AJOUT ---
                
                # Stocker restaurant minimal
                r.hset(rest_key, mapping={
                    "id": rid,
                    "name": f"Restaurant {rid}",   # pas de vrai nom dispo
                    "city": "Unknown",
                    "cuisine": row.get("category", "General"),
                    "lon": lon, # --- AJOUT ---
                    "lat": lat  # --- AJOUT ---
                })
                r.sadd("restaurants:index", rest_key)
                count_rest += 1
            # --- FIN AJOUT ---

            # Créer un menu
            menu_id = str(uuid.uuid4())
            menu_key = f"menu:{menu_id}"
            r.hset(menu_key, mapping={
                "restaurant_id": rid,
                "item": row.get("name", "Unknown"),
                "category": row.get("category", "General"),
                "description": row.get("description", ""),
                "price": _clean_price(row.get("price")),
                "currency": "USD"
            })

            # Lier menu au restaurant
            r.sadd(f"{rest_key}:menus", menu_key)
            count_menu += 1
            
            if count_menu % 100 == 0:
                print(f"... {count_menu} menus insérés.")

    print(f"✅ Terminé. {count_rest} restaurants et {count_menu} menus insérés dans Redis.")

if __name__ == "__main__":
    populate(limit=500)   # limite pour tester
