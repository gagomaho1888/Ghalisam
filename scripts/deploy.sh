#!/usr/bin/env bash
# Script de déploiement pour Ghalisam Boutique
# Usage: bash scripts/deploy.sh
set -euo pipefail

APP_DIR="/path/to/ecommerce"
ENV_FILE="$APP_DIR/.env"

echo "=== Déploiement Ghalisam Boutique ==="

# 1. Charger les variables d'environnement
if [ -f "$ENV_FILE" ]; then
    set -a; source "$ENV_FILE"; set +a
fi

cd "$APP_DIR"

# 2. Activer l'environnement virtuel
source .venv/bin/activate

# 3. Installer / mettre à jour les dépendances
pip install -r requirements.txt --no-deps

# 4. Migrations
python manage.py migrate --noinput

# 5. Collecte des fichiers statiques
python manage.py collectstatic --noinput --clear

# 6. Redémarrer le service
# Avec systemd :
# sudo systemctl restart ecommerce

# Avec supervisor :
# supervisorctl restart ecommerce

echo "=== Déploiement terminé ==="
