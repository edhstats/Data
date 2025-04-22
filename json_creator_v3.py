import sqlite3
import json
import os
import datetime
from collections import defaultdict

# Connessione al database
conn = sqlite3.connect('edh_stats.db')  # Cambia se il tuo DB ha un altro nome
cursor = conn.cursor()

# Query per aggregare vittorie e partite per ogni commander
query = """
    SELECT 
        c.id, 
        c.name, 
        c.mana_cost, 
        c.cmc, 
        c.color_identity,
        COUNT(m.id) AS partite,
        SUM(m.win) AS vittorie
    FROM commanders c
    LEFT JOIN matches m ON m.commander_id = c.id
    GROUP BY c.id, c.name, c.mana_cost, c.cmc, c.color_identity
    ORDER BY partite DESC
"""
cursor.execute(query)
rows = cursor.fetchall()

# Prepara struttura base dei commander
commanders = []
commander_index_by_name = {}

for row in rows:
    cmd_id, name, mana_cost, cmc, color_identity, partite, vittorie = row
    commander = {
        "id": cmd_id,
        "name": name,
        "mana_cost": mana_cost or "",
        "cmc": cmc,
        "color_identity": [color.strip() for color in (color_identity or "").split(',') if color.strip()],
        "partite": partite or 0,
        "vittorie": vittorie or 0,
        "storico": []  # campo da popolare dopo
    }
    commanders.append(commander)
    commander_index_by_name[name] = commander

# Query per ottenere i dati storici (ultimi 6 mesi)
historical_query = """
    SELECT 
        c.name,
        strftime('%Y-%m', m.date) AS month,
        COUNT(m.id) AS partite_mensili,
        SUM(m.win) AS vittorie_mensili
    FROM commanders c
    JOIN matches m ON m.commander_id = c.id
    WHERE m.date >= date('now', '-6 months')
    GROUP BY c.name, month
    ORDER BY c.name, month
"""

try:
    cursor.execute(historical_query)
    historical_rows = cursor.fetchall()

    if historical_rows:
        for row in historical_rows:
            name, month, partite_mensili, vittorie_mensili = row
            if name in commander_index_by_name and partite_mensili > 0:
                month_date = datetime.datetime.strptime(month, "%Y-%m")
                month_data = {
                    "periodo": month_date.strftime("%b %Y"),
                    "mese": month,
                    "partite": partite_mensili,
                    "winrate": round((vittorie_mensili / partite_mensili) * 100, 1)
                }
                commander_index_by_name[name]["storico"].append(month_data)
        print("📊 Storico aggiornato nei dati dei commander.")
    else:
        print("ℹ️ Nessun dato storico disponibile negli ultimi 6 mesi. Nessuna sezione 'storico' verrà popolata.")

except sqlite3.OperationalError as e:
    print(f"⚠️ Errore nella query storica: {e}")
    print("Assicurati che la tabella 'matches' abbia una colonna 'date' in formato YYYY-MM-DD.")

# Salvataggio del file JSON completo
output_dir = os.path.join(os.getcwd(), "Data_JSON")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "commanders.json")

with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"commanders": commanders}, f, indent=4, ensure_ascii=False)

conn.close()

print(f"✅ File 'commanders.json' creato con successo in: {output_path}")
