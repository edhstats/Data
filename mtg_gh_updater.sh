#!/bin/bash

# Definisci il percorso della directory del repository
REPO_DIR=$(pwd)
DATA_DIR="${REPO_DIR}/Data"
GIT_BRANCH="gh-pages"  # Branch per GitHub Pages
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

# 4. Git Operations - Pubblicazione su GitHub Pages
echo "Pubblicazione su GitHub Pages..."

# Controlla se ci sono modifiche nel repository
if git diff --quiet "${DATA_DIR}"; then
    echo "Nessuna modifica rilevata nei dati. Pubblicazione su GitHub Pages non necessaria."
    exit 0
fi

# A. Salva lo stato attuale del branch di lavoro
CURRENT_BRANCH=$(git branch --show-current)
echo "Salvataggio modifiche sul branch corrente: ${CURRENT_BRANCH}"
git add "${DATA_DIR}"
git commit -m "Aggiornamento dati EDH: ${TIMESTAMP}"

# B. Pubblica su GitHub Pages
echo "Pubblicazione sul branch ${GIT_BRANCH}..."

# Opzione 1: Se usi un branch separato per GitHub Pages
if [ "${CURRENT_BRANCH}" != "${GIT_BRANCH}" ]; then
    # Verifica se il branch gh-pages esiste
    if git show-ref --verify --quiet refs/heads/${GIT_BRANCH}; then
        # Branch esiste, lo aggiorna
        git checkout ${GIT_BRANCH}
        git pull origin ${GIT_BRANCH} --rebase
        # Aggiorna con le modifiche dal branch principale
        git merge ${CURRENT_BRANCH} -m "Merge aggiornamenti dal branch ${CURRENT_BRANCH}"
    else
        # Branch non esiste, lo crea
        git checkout -b ${GIT_BRANCH}
    fi
    
    # Push al repository
    git push origin ${GIT_BRANCH}
    
    # Torna al branch originale
    git checkout ${CURRENT_BRANCH}
else
    # Se sei già sul branch gh-pages, fai solo il push
    git push origin ${GIT_BRANCH}
fi

echo "✅ Pubblicazione su GitHub Pages completata!"