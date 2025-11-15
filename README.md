# Simulation de Plateforme UberEats (Redis vs. MongoDB)

Ce projet simule une plateforme de dispatch de courses (type UberEats) pour le cours de Bases de Données Avancées.
L'objectif est de comparer deux approches de communication temps réel entre un **Manager** (qui publie les offres) et des **Livreurs** (qui y répondent) :

1. **Approche Redis :** Utilise les commandes **GEO** pour trouver les livreurs proches et le **Pub/Sub** pour les notifier sur des canaux privés.
2. **Approche MongoDB :** Utilise les requêtes d’agrégation **`$geoNear`** (index 2dsphere) pour trouver les livreurs et les **Change Streams** pour les notifier des changements d’état.

---

## 🚀 Fonctionnalités Principales

* **Dispatch géolocalisé :** Le manager ne notifie que les 5 livreurs les plus proches du restaurant.
* **Simulation concurrente :** Utilise `threading` pour simuler le déplacement des livreurs (mise à jour GPS).
* **Logique d’état (Mongo) :** Les livreurs ont un statut (`available`, `on_delivery`).
* **Logique “Push” (Redis) :** Communication ultra-rapide via Pub/Sub.
* **Logique “Pull” (Mongo) :** Architecture événementielle avec Change Streams.

---

## 🛠️ Technologies Utilisées

* Python 3.10+
* Redis (serveur local)
* MongoDB Atlas (cluster cloud)
* Bibliothèques Python : `pymongo`, `redis`, `python-dotenv`

---

## ⚙️ Installation et Configuration

### 1. Cloner le Dépôt

```bash
git clone <url_du_repo>
cd <nom_du_dossier>
```

---

### 2. Installer les Dépendances

```bash
pip install pymongo redis python-dotenv
```

---

### 3. Configurer MongoDB Atlas

Créez un fichier **`.env`** à la racine du projet :

```ini
# .env
MONGODB_URI=mongodb+srv://user:password@cluster....mongodb.net/
```

Assurez-vous d’avoir autorisé votre IP dans **Network Access** de MongoDB Atlas.

---

### 4. Démarrer Redis

Assurez-vous d’avoir un serveur Redis local, puis lancez :

```bash
redis-server
```

---

### 5. ⚠️ IMPORTANT : Télécharger les Données (CSV)

Les scripts `populate_*.py` nécessitent un fichier CSV contenant restaurants et menus.

1. Téléchargez le dataset :
   [https://www.kaggle.com/datasets/melanieroberts/foodmenus](https://www.kaggle.com/datasets/melanieroberts/foodmenus)

2. Placez le fichier à la racine du projet.

3. Renommez-le **ubereats.csv**, ou adaptez le nom dans les scripts :

* `populate_redis.py`
* `populate_mongo.py`

---

## ⚡ Utilisation de la Simulation

La simulation nécessite plusieurs terminaux.

---

### Étape 1 : Peupler les Bases de Données

À exécuter **une seule fois** :

```bash
# Peupler Redis
python3 populate_redis.py

# Peupler MongoDB (peut prendre quelques secondes)
python3 populate_mongo.py
```

---

### Étape 2 : Lancer la Simulation (Scénario au choix)

---

## 🔴 Scénario 1 : Redis

Ouvrez **3 terminaux**.

### Terminal 1 — Livreur c1

```bash
python3 livreur_redis.py c1
```

### Terminal 2 — Livreur c2

```bash
python3 livreur_redis.py c2
```

### Terminal 3 — Manager

```bash
python3 manager_redis.py
```

---

## 🟢 Scénario 2 : MongoDB

Ouvrez **3 terminaux**.

### Terminal 1 — Livreur c1

```bash
python3 livreur_mongo.py c1
```

### Terminal 2 — Livreur c2

```bash
python3 livreur_mongo.py c2
```

### Terminal 3 — Manager

```bash
python3 manager_mongo.py
```

Le manager lancera 5 courses et les livreurs y répondront en temps réel.

---

## 📄 License

Ce projet est sous licence **MIT**.
