import uuid, time, os, random
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, server_api=ServerApi('1'))
db = client.UberEats 
jobs = db.jobs
bids = db.bids
restaurants_coll = db.restaurants
menus_coll = db.menus
couriers_coll = db.couriers # NOUVEAU

# ... (fonction choisir_restaurant_et_menu reste identique) ...
def choisir_restaurant_et_menu():
    # ... (code identique) ...
    random_restaurant_cursor = restaurants_coll.aggregate([{"$sample": {"size": 1}}])
    try:
        restaurant = next(random_restaurant_cursor)
    except StopIteration:
        raise Exception("⚠️ Aucun restaurant trouvé. Exécutez d'abord populate_mongo.py")
    random_menu_cursor = menus_coll.aggregate([
        {"$match": {"restaurant_id": restaurant["_id"]}},
        {"$sample": {"size": 1}}
    ])
    try:
        menu = next(random_menu_cursor)
    except StopIteration:
        print(f"Avertissement: Restaurant {restaurant['_id']} n'a pas de menu, ré-essai...")
        return choisir_restaurant_et_menu() 
    return restaurant, menu


# MODIFIÉ: Ne publie plus, mais "offre" la course aux livreurs proches
def offrir_course_aux_livreurs_proches(restaurant, menu):
    
    # 1. Récupérer la localisation du restaurant
    restaurant_loc = restaurant["location"] # [lon, lat]
    
    # 2. Trouver les 5 livreurs 'available' les plus proches
    # --- MODIFICATION: Suppression de maxDistance ---
    # On cherche les 5 plus proches, quelle que soit leur distance.
    pipeline = [
        {
            "$geoNear": {
                "near": restaurant_loc,
                "distanceField": "distance_m", # Nom du champ qui contiendra la distance
                "query": {"status": "available"}, # Ne chercher que les livreurs dispo
                "spherical": True
                # "maxDistance" a été supprimé
            }
        },
        {
            "$limit": 5 # On prend les 5 plus proches
        }
    ]
    # --- FIN DE LA MODIFICATION ---
    
    livreurs_proches = list(couriers_coll.aggregate(pipeline))
    
    if not livreurs_proches:
        print("[Manager] ❌ Aucun livreur disponible (la collection 'couriers' est vide ou aucun n'est 'available').")
        return None, [], [] # Retourne None (pas de job) et listes vides

    # 3. Créer le Job
    job_id = str(uuid.uuid4())
    pickup = restaurant.get("name", "Restaurant Inconnu")
    dropoff = f"Client au {random.randint(1, 100)} Rue de la Paix"
    reward = round(5 + random.random()*10, 2)
    
    job = {
        "_id": job_id, "pickup": pickup, "dropoff": dropoff, "reward": reward,
        "restaurant_id": restaurant["_id"], "menu_item": menu.get("item", "Menu Inconnu"),
        "status": "PENDING", # Le job n'est pas "OPEN", il est "en attente d'acceptation"
        "selectedCourier": None, "createdAt": datetime.utcnow()
    }
    jobs.insert_one(job)
    print(f"[Manager] Annonce {job_id} ({pickup}) créée.")

    # 4. Envoyer les offres (via la collection 'bids')
    offres_envoyees_ids = []
    targeted_courier_ids = [] # --- AJOUT ---
    print(f"[Manager] 📡 Envoi d'offres à {len(livreurs_proches)} livreur(s) proche(s)...")
    
    for livreur in livreurs_proches:
        offre = {
            "_id": str(uuid.uuid4()),
            "job_id": job_id,
            "targetCourier": livreur["_id"],
            "status": "OFFERED", # Le livreur écoute ce statut
            "distance_m": round(livreur["distance_m"], 2),
            "ts_offer": datetime.utcnow()
        }
        bids.insert_one(offre)
        offres_envoyees_ids.append(offre["_id"])
        targeted_courier_ids.append(livreur["_id"]) # --- AJOUT ---
        print(f"    -> Offre envoyée à {livreur['_id']} (à {offre['distance_m']}m)")
        
    return job_id, offres_envoyees_ids, targeted_courier_ids # --- MODIFIÉ ---

# MODIFIÉ: N'attend plus les 'insert', mais les 'update' sur les offres envoyées
def attendre_acceptations(job_id, offres_ids, duree=10):
    
    pipeline = [{
        "$match": {
            "operationType": "update",
            "fullDocument.status": "ACCEPTED",
            "fullDocument.job_id": job_id,
            "fullDocument._id": {"$in": offres_ids} # N'écoute que les offres qu'on a envoyées
        }
    }]
    
    candidats = []
    with bids.watch(pipeline, full_document='updateLookup') as stream:
        print(f"[Manager] En attente d'acceptations pour {job_id} (pendant {duree}s)...")
        start = time.time()
        
        while time.time() - start < duree:
            change = stream.try_next() 
            if change is None:
                time.sleep(0.1) 
                continue 

            offre_acceptee = change["fullDocument"]
            candidat = {
                "courier_id": offre_acceptee["targetCourier"],
                "distance": offre_acceptee["distance_m"],
                "bid_id": offre_acceptee["_id"]
            }
            print(f"[Manager] 👍 Acceptation de {candidat['courier_id']} (distance {candidat['distance']})")
            candidats.append(candidat)
            
            # On continue de collecter pour laisser les autres accepter
        
        print("[Manager] Temps d'attente écoulé.")
        
        if candidats:
             candidats_tries = sorted(candidats, key=lambda x: x['distance'])
             print(f"[Manager] Le plus proche des acceptants est {candidats_tries[0]['courier_id']}.")
             return candidats_tries[0] # On retourne le meilleur
        return None

# --- MODIFICATION: Ajout de 'all_targeted_ids' ---
def notifier_selection(job_id, courier_id_gagnant, all_targeted_ids, status_echec="LOST"):
    
    # S'il y a un gagnant
    if courier_id_gagnant:
        # On met le job à ASSIGNED
        jobs.update_one(
            {"_id": job_id}, 
            {"$set":{"status":"ASSIGNED","selectedCourier": courier_id_gagnant}}
        )
        # On met le bid gagnant à "WON"
        bids.update_many(
            {"job_id": job_id, "targetCourier": courier_id_gagnant},
            {"$set": {"status": "WON"}}
        )
        print(f"[Manager] ✅ Course {job_id} attribuée au plus proche: {courier_id_gagnant}")
    
    # On met les autres bids (ceux qui ne sont pas le gagnant) à "LOST" ou "EXPIRED"
    # Le livreur écoutera ce changement
    query_perdants = {
        "job_id": job_id, 
        "targetCourier": {"$in": all_targeted_ids, "$ne": courier_id_gagnant}
    }
    update_perdants = {"$set": {"status": status_echec}}
    
    result = bids.update_many(query_perdants, update_perdants)
    
    if result.modified_count > 0:
        print(f"[Manager] 🔔 Notifié les {result.modified_count} autres livreurs (statut {status_echec}).")

# --- MAIN MODIFIÉ ---
if __name__ == "__main__":
    MAX_COURSES = 5
    print("[Manager] Lancement du cycle de 5 courses GÉO...")
    
    try:
        for i in range(MAX_COURSES):
            print(f"\n=== [Manager] 🚀 Course {i+1}/{MAX_COURSES} ===")
            
            restaurant, menu = choisir_restaurant_et_menu()
            # --- MODIFIÉ: On récupère les 3 valeurs ---
            job_id, offres_envoyees_ids, targeted_courier_ids = offrir_course_aux_livreurs_proches(restaurant, menu)
            
            if not job_id:
                time.sleep(2)
                continue # Passe à la course suivante si aucun livreur trouvé

            candidat_gagnant = attendre_acceptations(job_id, offres_envoyees_ids, duree=10)
            
            if candidat_gagnant:
                # --- MODIFIÉ: On passe la liste des livreurs contactés ---
                notifier_selection(job_id, candidat_gagnant["courier_id"], targeted_courier_ids)
            else:
                print("[Manager] ❌ Aucun livreur n'a accepté cette course à temps.")
                jobs.update_one({"_id": job_id}, {"$set":{"status":"EXPIRED"}})
                # --- MODIFIÉ: On notifie tout le monde de l'échec ---
                notifier_selection(job_id, None, targeted_courier_ids, status_echec="EXPIRED")

            time.sleep(2)
            
        print("\n[Manager] ✅ Fin du cycle de courses.")
    except KeyboardInterrupt:
        print("\n[Manager] Arrêt manuel.")
