import redis, json, time, uuid, random

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# ... (fonction choisir_restaurant_et_menu reste identique) ...
def choisir_restaurant_et_menu():
    rest_key = r.srandmember("restaurants:index")
    if not rest_key:
        raise Exception("⚠️ Aucun restaurant trouvé. Exécute d'abord populate_redis.py")
    restaurant = r.hgetall(rest_key)
    menus_key = f"{rest_key}:menus"
    menu_key = r.srandmember(menus_key)
    menu = r.hgetall(menu_key)
    return restaurant, menu

# MODIFIÉ: Ne publie plus globalement, mais cible les livreurs
def publier_annonce_geo():
    job_id = str(uuid.uuid4())
    restaurant, menu = choisir_restaurant_et_menu()
    
    # 1. Récupérer la localisation du restaurant
    try:
        lon = float(restaurant["lon"])
        lat = float(restaurant["lat"])
    except (KeyError, ValueError):
        print(f"Erreur: Coordonnées manquantes/invalides pour {restaurant.get('name')}")
        return None, [] # Annule cette course

    annonce = {
        # ... (le dictionnaire 'annonce' reste identique) ...
        "job_id": job_id,
        "restaurant": restaurant.get("name", f"Restaurant {restaurant.get('id')}"),
        "menu_item": menu.get("item", "Unknown"),
        "price": float(menu.get("price", 0.0)),
        "reward": round(5 + random.random()*10, 2),
        "estimated_time": f"{random.randint(10,40)} min"
    }
    r.hset(f"job:{job_id}", mapping=annonce)
    print(f"[Manager] 📢 Annonce créée: {annonce['restaurant']} - {annonce['menu_item']}")

    # 2. --- MODIFICATION PRINCIPALE ICI ---
    # Au lieu de chercher dans un rayon de 5km, on cherche
    # les 5 livreurs les plus proches dans un rayon GÉANT de 1000km.
    try:
        livreurs_proches = r.georadius(
            "couriers:locations", 
            lon, lat, 
            1000, unit="km",  # 1. Rayon de recherche immense (1000 km)
            withdist=True,    # 2. On veut la distance
            sort="ASC",       # 3. On trie par distance (le plus proche en premier)
            count=5           # 4. On ne prend que les 5 meilleurs
        )
    except redis.exceptions.ResponseError:
        print("[Manager] ❌ Aucun livreur n'a encore transmis sa position (key 'couriers:locations' vide).")
        return job_id, []
    # --- FIN DE LA MODIFICATION ---
        
    if not livreurs_proches:
        # Cette erreur ne devrait (presque) plus jamais arriver, 
        # sauf si aucun livreur n'est lancé.
        print("[Manager] ❌ Aucun livreur trouvé (la base 'couriers:locations' est vide ?).")
        return job_id, []

    # 3. Publier l'offre en privé à chaque livreur
    print(f"[Manager] 📡 Envoi d'offres à {len(livreurs_proches)} livreur(s) proche(s)...")
    candidats_potentiels = {} # stocke {courier_id: distance}
    
    for item in livreurs_proches:
        courier_id = item[0]
        distance_km = item[1]
        distance_m = round(distance_km * 1000, 2)
        candidats_potentiels[courier_id] = distance_m
        
        # Le paquet de données envoyé au canal privé du livreur
        payload = {
            "type": "NEW_JOB_OFFER",
            "distance": distance_m,
            "annonce": annonce
        }
        
        r.publish(f"courier:{courier_id}:notify", json.dumps(payload))
        print(f"    -> Offre envoyée à {courier_id} (à {distance_m}m)")
        
    return job_id, candidats_potentiels

# MODIFIÉ: Attend les acceptations et choisit le plus proche
def attendre_acceptation(job_id, candidats_potentiels, duree=10):
    pubsub = r.pubsub()
    pubsub.subscribe(f"jobs:{job_id}:accepts")
    print(f"[Manager] En attente d'acceptations pour {job_id}...")

    livreurs_acceptes = [] # Liste des {courier_id, distance}
    start = time.time()

    while time.time() - start < duree:
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if msg is None:
            continue
            
        data = json.loads(msg["data"])
        courier_id = data["courier_id"]
        
        # Vérifier si ce livreur était bien sur notre liste
        if courier_id in candidats_potentiels:
            distance = candidats_potentiels[courier_id] # On récupère la distance qu'on avait calculée
            print(f"[Manager] 👍 Le livreur {courier_id} (à {distance}m) a accepté.")
            livreurs_acceptes.append({"courier_id": courier_id, "distance": distance})
        else:
             print(f"[Manager] ⚠️ {courier_id} a accepté, mais n'était pas ciblé. Ignoré.")
    
    pubsub.close()

    if not livreurs_acceptes:
        return None # Personne n'a accepté

    # Tri des livreurs qui ont accepté par distance
    livreurs_acceptes.sort(key=lambda x: x['distance'])
    gagnant = livreurs_acceptes[0] # Le gagnant est le plus proche
    
    print(f"[Manager] Le plus proche des acceptants est {gagnant['courier_id']}.")
    return gagnant["courier_id"]


# --- MODIFICATION: notifier_selection gère les gagnants et les perdants ---
# On ajoute 'all_candidates_ids' (une liste des IDs de tous ceux qui ont reçu l'offre)
def notifier_selection(job_id, courier_id, all_candidates_ids):
    losers_notified = 0
    
    # S'il y a un gagnant (courier_id n'est pas None)
    if courier_id:
        # 1. Notifier le GAGNANT
        r.hset(f"job:{job_id}", mapping={"status":"ASSIGNED", "selected_courier": courier_id})
        r.publish(f"courier:{courier_id}:notify", json.dumps({"type":"ASSIGNED", "job_id": job_id}))
        print(f"[Manager] ✅ Course {job_id} attribuée à {courier_id}")

    # 2. Notifier les PERDANTS
    for candidate_id in all_candidates_ids:
        # Si ce n'est pas le gagnant (ou s'il n'y a pas de gagnant, on notifie tout le monde)
        if candidate_id != courier_id: 
            r.publish(
                f"courier:{candidate_id}:notify", 
                json.dumps({"type": "JOB_LOST", "job_id": job_id})
            )
            losers_notified += 1
            
    if losers_notified > 0:
        print(f"[Manager] 🔔 Notifié les {losers_notified} autres livreurs.")
# --- FIN MODIFICATION ---


# --- MAIN MODIFIÉ ---
if __name__ == "__main__":
    MAX_COURSES = 5
    try:
        for i in range(MAX_COURSES):
            print(f"\n=== [Manager] 🚀 Course {i+1}/{MAX_COURSES} ===")
            
            # 'candidats_potentiels' est un dict {id: distance}
            job_id, candidats_potentiels = publier_annonce_geo()
            
            if not candidats_potentiels:
                print("[Manager] ❌ Échec de la création de course (pas de livreurs).")
                time.sleep(2)
                continue

            # 'courier' est l'ID du gagnant (ou None)
            courier = attendre_acceptation(job_id, candidats_potentiels, duree=10)
            
            # --- MODIFICATION: On appelle notifier_selection dans tous les cas ---
            if courier:
                # Cas 1: Il y a un gagnant
                # On passe le gagnant et la liste de tous les IDs contactés
                notifier_selection(job_id, courier, candidats_potentiels.keys())
            else:
                # Cas 2: Personne n'a accepté
                print("[Manager] ❌ Aucun livreur n'a accepté cette course.")
                r.hset(f"job:{job_id}", "status", "EXPIRED")
                # On passe None comme gagnant, et la liste de tous les IDs contactés
                notifier_selection(job_id, None, candidats_potentiels.keys())
            # --- FIN MODIFICATION ---
                
            time.sleep(2) 
        print("\n[Manager] ✅ Fin du cycle de courses.")
    except KeyboardInterrupt:
        print("\n[Manager] Arrêt manuel.")
