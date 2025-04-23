#!/bin/bash

# Definisci il percorso della directory del repository
REPO_DIR=$(pwd)
JSON_FILE="${REPO_DIR}/commanders.json"  # Percorso corretto del file JSON generato
HTML_REPORT="${REPO_DIR}/edh_report.html" # Percorso del report generato
GIT_BRANCH="gh-pages"  # Branch corrente (dove stai lavorando)
MAIN_BRANCH="main"     # Branch di destinazione per commanders.json
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# Directory temporanea per il clone del repository di destinazione
TEMP_DIR="/tmp/edhstats_gh_io"

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

# Verifica che il file commanders.json esista
if [ ! -f "$JSON_FILE" ]; then
    echo "File commanders.json non trovato in $JSON_FILE"
    exit 1
fi
echo "File commanders.json trovato in: $JSON_FILE"

# Verifica che il report HTML esista
if [ ! -f "$HTML_REPORT" ]; then
    echo "File edh_report.html non trovato in $HTML_REPORT"
    exit 1
fi
echo "File edh_report.html trovato in: $HTML_REPORT"

# Salva lo stato attuale del branch gh-pages - COMMIT TUTTE LE MODIFICHE
echo "Salvataggio modifiche sul branch corrente: ${GIT_BRANCH}"
git add -A  # Aggiunge tutte le modifiche, incluso .DS_Store e mtg_gh_updater.sh
git commit -m "Aggiornamento dati EDH e script: ${TIMESTAMP}"

# 4. Salva il file commanders.json nel branch main
echo "Spostamento di commanders.json nel branch ${MAIN_BRANCH}..."

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

# 6. Trasferimento del report HTML al repository edhstats.github.io
echo "Preparazione del trasferimento di edh_report.html a edhstats.github.io/index.html..."

# Crea/pulisci la directory temporanea
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Clona il repository di destinazione
git clone git@github.com:edhstats/edhstats.github.io.git "$TEMP_DIR"
if [ $? -ne 0 ]; then
    # Prova con HTTPS se SSH fallisce
    git clone https://github.com/edhstats/edhstats.github.io.git "$TEMP_DIR"
    if [ $? -ne 0 ]; then
        echo "Errore durante il clone del repository edhstats.github.io"
        exit 1
    fi
fi

# Copia il file edh_report.html come index.html nel repository di destinazione
cp "$HTML_REPORT" "$TEMP_DIR/index.html"

# Commit e push dei cambiamenti
cd "$TEMP_DIR"
git add index.html
git commit -m "Aggiornamento automatico index.html dal report EDH: ${TIMESTAMP}"
git push

if [ $? -ne 0 ]; then
    echo "Errore durante il push a edhstats.github.io"
    exit 1
fi

echo "✅ File edh_report.html trasferito con successo a edhstats.github.io/index.html"

# Torna alla directory originale
cd "$REPO_DIR"

echo "✅ Processo di aggiornamento completato con successo!"