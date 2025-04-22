#!/bin/bash

# 1. Upload in bulk
echo "Eseguo bulk_upload con mtg12.py..."
python3 mtg12.py bulk_upload partite_log.txt

if [ $? -eq 0 ]; then
    echo "Bulk upload completato con successo."

    # 2. Generazione report
    echo "Eseguo generate_report con mtg12.py..."
    python3 mtg12.py generate_report

    if [ $? -eq 0 ]; then
        echo "Report generato con successo."

        # 3. Aggiornamento JSON
        echo "Eseguo json_creator.py..."
        python3 json_creatorv_3.py

        if [ $? -eq 0 ]; then
            echo "JSON aggiornato con successo."
        else
            echo "Errore durante l'esecuzione di json_creator.py"
        fi

    else
        echo "Errore durante la generazione del report."
    fi

else
    echo "Errore durante il bulk upload."
fi
