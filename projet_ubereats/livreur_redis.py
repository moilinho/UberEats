import redis, json, sys, time, random
from threading import Thread

if len(sys.argv) < 2:
    print("Usage: python livreur_redis.py <courier_id>")
    sys.exit(1)

courier_id = sys.argv[1]
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# NOUVEAU: Fonction pour simuler le déplacement
def simuler_deplacement():
    """Met à jour la position du livreur toutes les 10s."""
    print(f"[Livreur {courier_id}] Simulation de déplacement activée.")
    # Position de départ aléatoire
    lon = round(random.uniform(2.25, 2.45), 6)
    lat = round(random.uniform(48.80, 48.90), 6)
    
    while True:
        try:
            # --- CORRECTION ---
            # On passe les valeurs (lon, lat, member) comme UN SEUL TUPLE
            # pour éviter l'ambiguïté avec les arguments nx/xx
            r.geoadd("couriers:locations", (lon, lat, courier_id))
            # --- FIN CORRECTION ---
            
            # Simuler un petit déplacement
            lon += random.uniform(-0.001, 0.001)
            lat += random.uniform(-0.001, 0.001)
            
            time.sleep(10)
        except Exception as e:
            print(f"[Livreur {courier_id}] Erreur dans le thread de déplacement: {e}")
            time.sleep(10)

# MODIFIÉ: Le livreur n'écoute plus 'jobs:new'
def ecouter():
    pubsub = r.pubsub()
    # Il écoute SEULEMENT son canal personnel
    pubsub.subscribe(f"courier:{courier_id}:notify")
    print(f"[Livreur {courier_id}] 📍 en attente d'offres géolocalisées...")

    for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
            
        canal = msg["channel"]
        data = json.loads(msg["data"])

        # Si on reçoit une nouvelle offre de job
        if data.get("type") == "NEW_JOB_OFFER":
            annonce = data["annonce"]
            distance = data["distance"]
            
            print(
                f"[Livreur {courier_id}] 📩 Offre reçue (à {distance}m): {annonce['restaurant']} / {annonce['menu_item']} "
                f"({annonce['reward']}€) [Durée estimée: {annonce['estimated_time']}]"
            )

            # Simule une réflexion aléatoire
            time.sleep(random.uniform(0.5, 2.0))

            # Envoie l'acceptation
            r.publish(f"jobs:{annonce['job_id']}:accepts",
                        json.dumps({"courier_id": courier_id, "job_id": annonce["job_id"], "distance": distance}))
            print(f"[Livreur {courier_id}] ✅ a accepté la course {annonce['job_id']}")

        # Si on reçoit la confirmation d'assignation
        elif data.get("type") == "ASSIGNED":
            print(f"[Livreur {courier_id}] 🎉 Confirmation : Course {data['job_id']} attribuée !")
            
        # --- AJOUT : Gérer le cas où on a perdu l'offre ---
        elif data.get("type") == "JOB_LOST":
            print(f"[Livreur {courier_id}] ❌ Dommage : Course {data.get('job_id', 'unknown')} attribuée à un autre livreur ou expirée.")
        # --- FIN AJOUT ---

if __name__ == "__main__":
    try:
        # NOUVEAU: Lancer le thread de simulation
        Thread(target=simuler_deplacement, daemon=True).start()
        ecouter()
    except KeyboardInterrupt:
        print(f"\n[Livreur {courier_id}] Arrêt manuel.")
