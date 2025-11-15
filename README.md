# Simulation de Plateforme UberEats (Redis vs. MongoDB)

Ce projet simule une plateforme de dispatch de courses (type UberEats) pour le cours de Bases de Données Avancées. L'objectif est de comparer deux approches de communication temps réel entre un "Manager" (qui publie les offres) et des "Livreurs" (qui y répondent) :

1.  **Approche Redis :** Utilise les commandes **GEO** pour trouver les livreurs proches et le **Pub/Sub** pour les notifier sur des canaux privés.
2.  **Approche MongoDB :** Utilise les requêtes d'agrégation **$geoNear** (index 2dsphere) pour trouver les livreurs et les **Change Streams** pour les notifier des changements d'état.

## 🚀 Fonctionnalités Principales

* **Dispatch Géolocalisé :** Le manager ne notifie que les 5 livreurs les plus proches du restaurant.
* **Simulation Concurrente :** Utilise le `threading` pour simuler le déplacement des livreurs (mise à jour de leur position GPS) en tâche de fond.
* **Logique d'État (Mongo) :** Les livreurs ont un statut (`available`, `on_delivery`) pour une simulation plus réaliste.
* **Logique "Push" (Redis) :** Communication "fire-and-forget" ultra-rapide via des canaux de notification privés.
* **Logique "Pull" (Mongo) :** Les livreurs observent les changements dans la base de données (architecture événementielle basée sur la BDD).

## 🛠️ Technologies Utilisées

* Python 3.10+
* Redis (serveur local)
* MongoDB Atlas (Cluster Cloud)
* Bibliothèques Python : `pymongo`, `redis`, `python-dotenv`

## ⚙️ Installation et Configuration

Suivez ces étapes pour lancer le projet.

### 1. Cloner le Dépôt

2. Installer les Dépendances
Bash

pip install pymongo redis python-dotenv
3. Configurer MongoDB Atlas
Le projet se connecte à un cluster MongoDB Atlas.

Créez un fichier .env à la racine du projet.

Copiez-y votre URI de connexion (obtenue depuis MongoDB Atlas) :

Ini, TOML

# .env
MONGODB_URI=mongodb+srv://user:password@cluster....mongodb.net/
Assurez-vous d'avoir autorisé votre adresse IP actuelle dans les "Network Access" de MongoDB Atlas.

4. Démarrer Redis
Vous devez avoir un serveur Redis lancé localement. Si vous l'avez installé sur votre machine, ouvrez un terminal et lancez :

Bash

redis-server
5. ⚠️ IMPORTANT : Télécharger les Données (CSV)
Les scripts de peuplement (populate_*.py) ont besoin d'un fichier CSV pour remplir les bases de données avec des restaurants et des menus.

Téléchargez le jeu de données à l'adresse suivante : https://www.kaggle.com/datasets/melanieroberts/foodmenus

Placez le fichier CSV à la racine du projet.

Renommez-le ubereats.csv (ou modifiez le nom du fichier directement dans les scripts populate_redis.py et populate_mongo.py).

⚡ Utilisation de la Simulation
La simulation se lance dans plusieurs terminaux.

Étape 1 : Peupler les bases de données
Exécutez ces deux scripts une seule fois pour remplir Redis et MongoDB avec les données du CSV.

Bash

# Peupler Redis
python3 populate_redis.py

# Peupler MongoDB (cela peut prendre quelques secondes)
python3 populate_mongo.py
Étape 2 : Lancer la Simulation (Scénario au choix)
Scénario 1 : REDIS
Ouvrez 3 terminaux :

Terminal 1 (Livreur c1) :

Bash

python3 livreur_redis.py c1
Terminal 2 (Livreur c2) :

Bash

python3 livreur_redis.py c2
Terminal 3 (Manager) :

Bash

python3 manager_redis.py
Scénario 2 : MONGODB
Ouvrez 3 terminaux :

Terminal 1 (Livreur c1) :

Bash

python3 livreur_mongo.py c1
Terminal 2 (Livreur c2) :

Bash

python3 livreur_mongo.py c2
Terminal 3 (Manager) :

Bash

python3 manager_mongo.py
Le manager lancera 5 courses et les livreurs y répondront en temps réel. Vous verrez les logs s'afficher dans chaque terminal.

📄 License
Ce projet est sous licence MIT.
