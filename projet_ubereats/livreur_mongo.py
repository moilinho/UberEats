import sys, os, random, time
from datetime import datetime
from pymongo import MongoClient, GEOSPHERE
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from threading import Thread

if len(sys.argv) < 2:
    print("Usage: python livreur_mongo.py <courier_id>")
    sys.exit(1)

courier_id = sys.argv[1]

load_dotenv()
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, server_api=ServerApi('1'))
db = client.UberEats
jobs = db.jobs
bids = db.bids
# NOUVEAU : Collection pour la position des livreurs
couriers_coll = db.couriers

# NOUVEAU: Fonction pour simuler le déplacement
def simuler_deplacement():
    """Met à jour la position du livreur toutes les 10s."""
    print(f"[Livreur {courier_id}] Simulation de déplacement activée.")
    # Position de départ aléatoire (autour de Paris)
    my_location = {
        "type": "Point",
        "coordinates": [
            round(random.uniform(2.25, 2.45), 6), # lon
            round(random.uniform(48.80, 48.90), 6)  # lat
        ]
    }
    
    while True:
        # Mettre à jour (ou insérer si non existant)
        couriers_coll.update_one(
            {"_id": courier_id},
            {
                "$set": {
                    "location": my_location,
                    "status": "available", # Le manager ne contactera que les 'available'
                    "updatedAt": datetime.utcnow()
                },
                "$setOnInsert": {"_id": courier_id} # Au cas où il n'existe pas
            },
            upsert=True
        )
        
        # Simuler un petit déplacement
        my_location["coordinates"][0] += random.uniform(-0.001, 0.001)
        my_location["coordinates"][1] += random.uniform(-0.001, 0.001)
        
        time.sleep(10) # Met à jour la position toutes les 10 secondes


# MODIFIÉ: Le livreur écoute les 'bids' (offres) qui lui sont envoyées
def ecouter_offres():
    """Écoute les offres de course (bids) où ce livreur est 'targetCourier'."""
    
    # Le manager va insérer un document dans 'bids' avec status: "OFFERED"
    pipeline = [{
        "$match": {
            "operationType": "insert",
            "fullDocument.status": "OFFERED",
            "fullDocument.targetCourier": courier_id
        }
    }]
    
    with bids.watch(pipeline) as stream:
        print(f"[Livreur {courier_id}] 📍 En attente d'offres géolocalisées...")
        for change in stream:
            offre = change["fullDocument"]
            job = jobs.find_one({"_id": offre["job_id"]}) # Récupère les détails du job
            
            if not job:
                continue

            print(f"[Livreur {courier_id}] 📩 Offre reçue pour {job['pickup']} (à {offre['distance_m']}m)")
            
            # Simule une réflexion (1-3s)
            time.sleep(random.uniform(1, 3))

            # Accepter l'offre en changeant le statut du bid
            bids.update_one(
                {"_id": offre["_id"]},
                {"$set": {"status": "ACCEPTED", "ts": datetime.utcnow()}}
            )
            print(f"[Livreur {courier_id}] ✅ J'accepte la course {job['_id']}")

# --- NOUVELLE FONCTION: Pour écouter les résultats (perdu/expiré) ---
def ecouter_resultats_offres():
    """Écoute si les offres qu'on a acceptées sont perdues ou ont expiré."""
    pipeline = [{
        "$match": {
            "operationType": "update",
            "fullDocument.targetCourier": courier_id,
            "fullDocument.status": {"$in": ["LOST", "EXPIRED"]}
        }
    }]
    
    # On a besoin du document complet pour lire le statut
    with bids.watch(pipeline, full_document='updateLookup') as stream:
        for change in stream:
            offre_perdue = change["fullDocument"]
            job_id = offre_perdue["job_id"]
            status = offre_perdue["status"]
            
            if status == "LOST":
                print(f"[Livreur {courier_id}] ❌ Dommage : Course {job_id} attribuée à un autre livreur.")
            elif status == "EXPIRED":
                print(f"[Livreur {courier_id}] ⏳ Course {job_id} a expiré (personne n'a accepté à temps).")
# --- FIN DE LA NOUVELLE FONCTION ---

# --- MODIFICATION PRINCIPALE ICI ---
def ecouter_assignations():
    """Écoute les assignations (pour le GAGNANT)."""
    pipeline = [{"$match": {
        "operationType": "update",
        "fullDocument.status": "ASSIGNED",
        "fullDocument.selectedCourier": courier_id
    }}]
    
    with jobs.watch(pipeline, full_document='updateLookup') as stream:
        for change in stream:
            job_updated = change["fullDocument"]
            print(f"\n[Livreur {courier_id}] 🚀🎉 Course {job_updated['_id']} confirmée et assignée !")
            print(f"    -> De: {job_updated['pickup']}")
            print(f"    -> À : {job_updated['dropoff']}\n")
            
            # 1. Le livreur n'est plus disponible
            couriers_coll.update_one({"_id": courier_id}, {"$set": {"status": "on_delivery"}})

            # 2. Fonction interne pour simuler la livraison dans un thread
            def simuler_livraison(job_id_livraison):
                duree_livraison_sec = random.randint(8, 15) # Simule 8-15 sec de livraison
                print(f"[Livreur {courier_id}] 🚚 Début de la livraison {job_id_livraison} (durée: {duree_livraison_sec}s)...")
                time.sleep(duree_livraison_sec)
                print(f"[Livreur {courier_id}] ✅ Livraison {job_id_livraison} terminée ! De nouveau disponible.")
                # 3. Le livreur redevient disponible
                couriers_coll.update_one({"_id": courier_id}, {"$set": {"status": "available"}})

            # 4. Lancer la simulation de livraison dans un thread pour ne pas bloquer
            Thread(target=simuler_livraison, args=(job_updated['_id'],), daemon=True).start()
# --- FIN DE LA MODIFICATION ---


if __name__ == "__main__":
    # NOUVEAU: Créer l'index 2dsphere au démarrage si besoin
    try:
        couriers_coll.create_index([("location", GEOSPHERE)])
    except Exception as e:
        print(f"Erreur index: {e}")

    # NOUVEAU: Lancer le thread de simulation de déplacement
    Thread(target=simuler_deplacement, daemon=True).start()
    
    # Thread pour écouter les NOUVELLES offres
    Thread(target=ecouter_offres, daemon=True).start()
    
    # --- AJOUT: Thread pour écouter les RÉSULTATS (perdu/expiré) ---
    Thread(target=ecouter_resultats_offres, daemon=True).start()
    
    # Boucle principale pour écouter les VICTOIRES (assignations)
    ecouter_assignations()
