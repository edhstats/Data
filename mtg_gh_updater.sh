#!/bin/bash

# Definisci il percorso della directory del repository
REPO_DIR=$(pwd)
DATA_DIR="${REPO_DIR}/Data"
GIT_BRANCH="gh-pages"  # Branch corrente (dove stai lavorando)
MAIN_BRANCH="main"     # Branch di destinazione per commanders.json
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# 1. Upload in bulk
echo "Eseguo bulk_upload con mtg12.py..."
python3 mtg12.py bulk_upload partite_log.txt

if [ $? -ne 0 ]; then
    echo "Errore durante il bulk upload."
    exit 1
fi
echo "Bulk upload completato con successo."

# 2. Generazione report
echo "Eseguo generate_report con mtg12.py..."
python3 mtg12.py generate_report

if [ $? -ne 0 ]; then
    echo "Errore durante la generazione del report."
    exit 1
fi
echo "Report generato con successo."

# 3. Aggiornamento JSON
echo "Eseguo json_creator_v3.py..."
python3 json_creator_v3.py

if [ $? -ne 0 ]; then
    echo "Errore durante l'esecuzione di json_creator_v3.py"
    exit 1
fi
echo "JSON aggiornato con successo."

# Salva lo stato attuale del branch gh-pages
echo "Salvataggio modifiche sul branch corrente: ${GIT_BRANCH}"
git add "${DATA_DIR}"
git commit -m "Aggiornamento dati EDH in Data/: ${TIMESTAMP}"

# 4. Salva il file commanders.json nel branch main
echo "Spostamento di commanders.json nel branch ${MAIN_BRANCH}..."

# Salva percorso del file JSON
JSON_FILE="${DATA_DIR}/commanders.json"
if [ ! -f "$JSON_FILE" ]; then
    echo "File commanders.json non trovato in ${DATA_DIR}"
    exit 1
fi

# Salva una copia temporanea del file JSON
TEMP_JSON="/tmp/commanders_temp.json"
cp "$JSON_FILE" "$TEMP_JSON"

# Cambia al branch main
git checkout $MAIN_BRANCH
git pull origin $MAIN_BRANCH --rebase

# Copia il file nella root del branch main
cp "$TEMP_JSON" "${REPO_DIR}/commanders.json"

# Commit e push delle modifiche nel branch main
git add "${REPO_DIR}/commanders.json"
git commit -m "Aggiornamento commanders.json: ${TIMESTAMP}"
git push origin $MAIN_BRANCH

echo "✅ File commanders.json aggiornato nel branch ${MAIN_BRANCH}"

# Torna al branch gh-pages originale
git checkout $GIT_BRANCH

# 5. Push delle modifiche nel branch gh-pages
git push origin $GIT_BRANCH

echo "✅ Modifiche salvate in entrambi i branch: ${GIT_BRANCH} e ${MAIN_BRANCH}"