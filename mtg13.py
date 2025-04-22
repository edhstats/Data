import sqlite3
import pandas as pd
import argparse
from tabulate import tabulate
import os
from datetime import datetime
import requests
from rapidfuzz import process
import uuid
from jinja2 import Template
from functools import lru_cache
from rapidfuzz import process, fuzz
import json
from collections import defaultdict
import urllib.parse
from datetime import datetime


# Percorso del file database persistente
DB_PATH = 'edh_stats.db'

timestamp = datetime.now().isoformat(timespec='minutes')  # es. "2025-04-16T14:03"
# Creiamo o connettiamo a un database SQLite
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Cache for validated commander names
COMMANDER_CACHE = {}

def normalize_name(name):

    if not name:  # Controlla se name è None o una stringa vuota
        return None  
        
    """
    Normalizes a name by:
    - Converting to lowercase
    - Removing extra spaces
    - Removing special characters
    - Standardizing apostrophes and diacritics
    """
    # Convert to lowercase
    name = name.lower()
    
    # Remove extra spaces
    name = " ".join(name.split())
    
    # Remove special characters but keep apostrophes and spaces
    name = re.sub(r'[^a-z0-9\' ]', '', name)
    
    # Standardize apostrophes
    name = name.replace("'", "'")
    
    return name

@lru_cache(maxsize=1000)
def get_cached_commander_info(name):
    """
    Cached version of commander info fetch to avoid repeated API calls.
    Uses Python's built-in LRU cache decorator.

    """
    normalized_name = normalize_name(name)
    if not normalized_name:
        return None  # Evita di chiamare fetch_commander_info con None
    return fetch_commander_info(normalized_name)

def find_similar_commander(name, threshold=80):
    """
    Finds similar commander names in the database using fuzzy matching.
    Returns the closest match above the threshold, or None if no match is found.
    """

    cursor.execute("SELECT name FROM commanders")
    existing_commanders = [row[0] for row in cursor.fetchall()]
    
    if not existing_commanders:
        return None
        
    # Find the best match
    best_match, score = process.extractOne(
        name,
        existing_commanders,
        scorer=fuzz.ratio
    )
    
    if score >= threshold:
        return best_match
    return None

def validate_commander_name(name):
    """
    Validates a commander name and suggests corrections if needed.
    Returns (normalized_name, is_valid, suggestion)
    """
    normalized_name = normalize_name(name)
    
    # Check cache first
    if normalized_name in COMMANDER_CACHE:
        return COMMANDER_CACHE[normalized_name], True, None
    
    # Try to fetch from Scryfall
    commander_info = get_cached_commander_info(normalized_name)
    
    if commander_info:
        COMMANDER_CACHE[normalized_name] = commander_info["name"]
        return commander_info["name"], True, None
    
    # If not found, try fuzzy matching with existing commanders
    suggestion = find_similar_commander(normalized_name)
    return normalized_name, False, suggestion

def get_or_create_commander(name):
    # Verifica del nome del comandante

    conn = sqlite3.connect("database.db")  # Assicurati che il database esista
    cursor = conn.cursor()

    validated_name, is_valid, suggestion = validate_commander_name(name)
    
    if not is_valid:
        if suggestion:
            print(f"Il comandante '{name}' non è valido. Potrebbe essere '{suggestion}' invece.")
        else:
            print(f"Il comandante '{name}' non è valido e non è stato trovato un suggerimento.")
        return None

    normalized_name = validated_name
    
    cursor.execute("SELECT id FROM commanders WHERE name = ?", (normalized_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Se il comandante non esiste, lo inseriamo nel database
    color_identity = ""  # Qui possiamo aggiungere un'ulteriore logica per ottenere il colore
    cursor.execute("INSERT INTO commanders (name, color_identity) VALUES (?, ?)", (normalized_name, color_identity))
    conn.commit()
    return cursor.lastrowid

def create_tables():
    cursor.execute('''CREATE TABLE IF NOT EXISTS players (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL
                      )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS commanders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        color_identity TEXT
                      )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS matches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        player_id INTEGER NOT NULL,
                        commander_id INTEGER NOT NULL,
                        win INTEGER NOT NULL,
                        game_id TEXT NOT NULL,
                        FOREIGN KEY (player_id) REFERENCES players(id),
                        FOREIGN KEY (commander_id) REFERENCES commanders(id)
                      )''')
    conn.commit()

def fetch_commander_info(name):
    normalized_name = name.lower().replace(" ", "+")
    url = f"https://api.scryfall.com/cards/named?exact={normalized_name}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "name": data["name"],
            "mana_cost": data.get("mana_cost", ""),
            "cmc": data.get("cmc", 0),
            "color_identity": data.get("color_identity", []),
            "type_line": data.get("type_line", ""),
            "oracle_text": data.get("oracle_text", "")
        }
    else:
        print(f"Errore nel recupero per '{name}'. Codice: {response.status_code}")
        return None

def get_or_create_player(name):
    cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
    conn.commit()
    return cursor.lastrowid

def get_or_create_commander(name):
    commander_info = fetch_commander_info(name)
    if not commander_info:
        print(f"Errore: il comandante '{name}' non è valido.")
        return None
    
    normalized_name = commander_info["name"].lower()
    color_identity = ''.join(commander_info["color_identity"])
    mana_cost = commander_info["mana_cost"]
    cmc = commander_info["cmc"]
    
    # Verifica se il comandante esiste già
    cursor.execute("SELECT id FROM commanders WHERE name = ?", (normalized_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]  # Comandante già presente, ritorna l'id
    
    # Se il comandante non esiste, crealo nel database con tutti i dettagli
    cursor.execute("""
        INSERT INTO commanders (name, color_identity, mana_cost, cmc)
        VALUES (?, ?, ?, ?)
    """, (normalized_name, color_identity, mana_cost, cmc))
    
    conn.commit()
    return cursor.lastrowid  # Restituisce l'id del comandante appena creato


# Funzione per registrare una partita
def record_match(date, players):
    # Genera un identificativo univoco per la partita
    game_id = str(uuid.uuid4())
    
    for player in players:
        player_id = get_or_create_player(player['name'])
        commander_id = get_or_create_commander(player['commander'])
        win = 1 if player['win'] else 0
        cursor.execute(
            "INSERT INTO matches (date, player_id, commander_id, win, game_id) VALUES (?, ?, ?, ?, ?)",
            (date, player_id, commander_id, win, game_id)
        )
    conn.commit()
    print(f"Partita registrata con successo. ID partita: {game_id}")

# Funzione per caricare partite in blocco da file
def bulk_upload_matches(filename):
    try:
        with open(filename, 'r') as file:
            lines = file.readlines()
            i = 0
            while i < len(lines):
                # Ignoriamo eventuali righe vuote all'inizio
                if lines[i].strip() == "":
                    i += 1
                    continue

                # Leggiamo la data e la convertiamo nel formato appropriato
                date_str = lines[i].strip()
                date = datetime.strptime(date_str, "%d.%m.%y").date()
                i += 1
                
                players = []
                game_id = str(uuid.uuid4())  # Genera un nuovo game_id per questa partita
                
                # Leggiamo le righe dei giocatori fino alla riga del vincitore o una riga vuota
                while i < len(lines) and lines[i].strip() != "" and not lines[i].startswith("W:"):
                    line = lines[i].strip()
                    if line:
                        player_name, commander_name = map(str.strip, line.split(":"))
                        players.append({
                            'name': player_name,
                            'commander': commander_name,
                            'win': False  # Impostiamo win su False di default
                        })
                    i += 1
                
                # Leggiamo la riga del vincitore e otteniamo il comandante
                if i < len(lines) and lines[i].startswith("W:"):
                    winner_commander = lines[i].split(":")[1].strip()
                    # Impostiamo win = True per il giocatore con il comandante vincitore
                    for player in players:
                        if player['commander'] == winner_commander:
                            player['win'] = True
                            break
                    i += 1  # Passiamo alla prossima riga
                
                # Registriamo la partita con lo stesso game_id
                for player in players:
                    player_id = get_or_create_player(player['name'])
                    commander_id = get_or_create_commander(player['commander'])
                    win = 1 if player['win'] else 0
                    cursor.execute(
                        "INSERT INTO matches (date, player_id, commander_id, win, game_id) VALUES (?, ?, ?, ?, ?)",
                        (date, player_id, commander_id, win, game_id)
                    )
                conn.commit()

                # Saltiamo la riga vuota tra le partite, se presente
                while i < len(lines) and lines[i].strip() == "":
                    i += 1

            print("Upload in blocco completato con successo.")
    except FileNotFoundError:
        print(f"Errore: il file '{filename}' non è stato trovato.")
    except Exception as e:
        print(f"Errore durante il caricamento: {e}")


# Funzione per ottenere il link Scryfall per il comandante
def get_commander_scryfall_link(commander_name):

    if commander_name is None:
        print("ERROR: commander_name is None")
        return None
    normalized_name = commander_name.lower().replace(" ", "-")
    url = f"https://api.scryfall.com/cards/named?exact={normalized_name}"
    response = requests.get(url)
    
    # Verifica se la risposta è corretta
    if response.status_code == 200:
        data = response.json()
        # Controlla se 'url' è presente nella risposta
        if 'scryfall_uri' in data:
            return data['scryfall_uri']
        else:
            print(f"Errore: Nessun URL trovato per {commander_name}. Risposta API: {data}")
            return f"Link non disponibile per {commander_name}."
    else:
        print(f"Errore nella richiesta API per {commander_name}. Status code: {response.status_code}")
        return f"Errore nel trovare il link per {commander_name}."

def linkify_commander_names(df):
    df = df.copy()
    df['Comandante'] = df['Comandante'].apply(lambda name: f'<a href="https://scryfall.com/search?q={urllib.parse.quote(name)}" target="_blank">{name}</a>')
    return df

# === HTML Helper ===
def dataframe_to_table(df, table_id):
    return df.to_html(classes="display", table_id=table_id, index=False, border=0)

# === HTML Report Generator ===
def generate_html_report(
    player_winrate_over_time,
    player_commander_stats,
    color_stats,
    player_stats,
    commander_stats,
    player_vs_others,
    player_list,
    cmc_medio_totale,
    num_players,
    num_commanders,
    top_commanders_played,       
    top_commanders_winrate       
):

    chart_data_js = {player: df.to_dict(orient='records') for player, df in player_winrate_over_time.items()}
    with open("edh_report.html", "w", encoding="utf-8") as report_file:
        report_file.write(f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Magic EDH Stats Report</title>
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 20px;
    }
    h1, h2, h3 {
      color: #444;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 20px;
    }
    th, td {
      padding: 12px;
      border: 1px solid #ddd;
      text-align: center;
    }
    th {
      background-color: #4CAF50;
      color: white;
    }
    tr:nth-child(even) {
      background-color: #f2f2f2;
    }
    tr:hover {
      background-color: #ddd;
    }
    .player-section {
      margin-bottom: 30px;
      border: 1px solid #ccc;
      padding: 15px;
      border-radius: 8px;
    }
    .player-section h3 {
      margin-top: 0;
      background-color: #eee;
      padding: 10px;
      border-radius: 5px;
    }
    .hidden {
      display: none;
    }
  </style>
</head>
<body>
  <h1>Magic EDH Stats Report</h1>

  <!-- Iniettata da Python -->
  <p id="lastUpdated" data-ts="{{ timestamp }}">Ultimo aggiornamento: --</p>

  <!-- Includi day.js -->
  <script src="https://cdn.jsdelivr.net/npm/dayjs@1/dayjs.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dayjs@1/locale/it.js"></script>

  <script>
    dayjs.locale('it');  // Imposta la lingua italiana

    // Recupera il timestamp iniettato da Python (es. nel data attribute)
    const ts = document.getElementById("lastUpdated").dataset.ts;

    // Formattalo con day.js (solo al primo caricamento)
    const formatted = dayjs(ts).format('D MMMM YYYY [alle] HH:mm');

    document.getElementById("lastUpdated").textContent =
      "Ultimo aggiornamento: " + formatted;
  </script>

  <p><strong>CMC Medio Totale:</strong> {{ cmc_medio_totale }}</p>
  <p><strong>Numero Totale Giocatori:</strong> {{ num_players }}</p>
  <p><strong>Numero Totale Comandanti Giocati:</strong> {{ num_commanders }}</p>

  <h2>Dettaglio Comandanti per Giocatore</h2>
  <label for="commanderPlayerSelect">Seleziona Giocatore:</label>
  <select id="commanderPlayerSelect">
    <option value="">Seleziona un giocatore</option>
    {% for player in player_list %}
      <option value="{{ player }}">{{ player }}</option>
    {% endfor %}
</select>


  {% for player, df in player_commander_stats.items() %}
    <div id="player-{{ player.replace(' ', '-') }}" class="player-section hidden player-commander-section">
      <h3>Comandanti di {{ player }}</h3>
      {{ dataframe_to_table(df, "commanderStatsTable-" + player.replace(' ', '-')) }}
    </div>
  {% endfor %}

  <h2>Colori Più Utilizzati</h2>
  {{ dataframe_to_table(color_stats, "colorStatsTable") }}

  <h2>Statistiche dei Giocatori</h2>
  {{ dataframe_to_table(player_stats, "playerStatsTable") }}

  <h2>Top 5 Comandanti più Giocati</h2>
  {{ dataframe_to_table(top_commanders_played, "topCommandersPlayedTable") }}

  <h2>Top 5 Comandanti con Maggior Winrate (min. 5 partite)</h2>
  {{ dataframe_to_table(top_commanders_winrate, "topCommandersWinrateTable") }}

  <h2>Statistiche dei Comandanti</h2>
  {{ dataframe_to_table(commander_stats, "commanderStatsTable") }}

  <h2>Statistiche Giocatore vs Avversario</h2>
  <label for="playerSelect">Seleziona Giocatore:</label>
  <select id="playerSelect">
    <option value="Tutti">Tutti</option>
    {% for player in player_list %}
      <option value="{{ player }}">{{ player }}</option>
    {% endfor %}
  </select>

  {{ dataframe_to_table(player_vs_others, "playerVsOthersTable") }}

  <h2>Andamento Win Rate nel Tempo</h2>
  <label for="winratePlayerSelect">Seleziona Giocatore:</label>
  <select id="winratePlayerSelect">
    <option value="">Seleziona un giocatore</option>
    {% for player in player_list %}
      <option value="{{ player }}">{{ player }}</option>
    {% endfor %}
  </select>

  <canvas id="winrateChart" width="800" height="400"></canvas>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    const chartData = {{ chart_data_js|safe }};
    $(document).ready(function() {
      $('#colorStatsTable, #playerStatsTable, #commanderStatsTable, #playerVsOthersTable, #topCommandersPlayedTable, #topCommandersWinrateTable').DataTable();
      $('.player-commander-section table.display').each(function() {
        $(this).DataTable({ paging: false, info: false });
      });

      $('#playerSelect').on('change', function() {
        var val = $(this).val();
        var table = $('#playerVsOthersTable').DataTable();
        table.column(0).search(val === "Tutti" ? "" : "^" + val + "$", true, false).draw();
      });

      $('#commanderPlayerSelect').on('change', function() {
        var val = $(this).val();
        $('.player-commander-section').addClass('hidden');
        if (val) $('#player-' + val.replace(' ', '-')).removeClass('hidden');
      });

      const ctx = document.getElementById('winrateChart').getContext('2d');
      const winrateChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Win Rate (%)',
            data: [],
            borderColor: 'rgb(75,192,192)',
            tension: 0.1
          }]
        },
        options: {
          scales: {
            y: {
              beginAtZero: true,
              max: 100
            }
          }
        }
      });

      document.getElementById("winratePlayerSelect").addEventListener("change", function() {
        const player = this.value;
        if (!player || !chartData[player]) return;
        const data = chartData[player];
        winrateChart.data.labels = data.map(p => p.date);
        winrateChart.data.datasets[0].data = data.map(p => p.winrate);
        winrateChart.update();
      });
    });
  </script>
</body>
</html>

""")
    print("✅ Report HTML generato con successo: edh_report.html")

# === Statistiche dal DB ===
def generate_report():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    player_list = pd.read_sql("SELECT name FROM players ORDER BY name", conn)['name'].tolist()
    player_winrate_over_time = {}
    for player in player_list:
        df = pd.read_sql_query("""
            SELECT strftime('%Y-%m', m.date) AS data,
                   ROUND(SUM(m.win)*100.0 / COUNT(*), 2) AS winrate
            FROM matches m
            JOIN players p ON p.id = m.player_id
            WHERE p.name = ?
            GROUP BY data
            ORDER BY data
        """, conn, params=(player,))
        player_winrate_over_time[player] = df

    player_commander_stats = {}
    for player in player_list:
        df = pd.read_sql_query("""
            SELECT c.name AS Comandante,
                   c.color_identity AS Colori,
                   c.cmc AS CMC,
                   COUNT(m.id) AS Partite,
                   SUM(m.win) AS Vittorie,
                   ROUND(SUM(m.win)*100.0 / COUNT(m.id), 2) AS "Winrate (%)"
            FROM matches m
            JOIN players p ON p.id = m.player_id
            JOIN commanders c ON c.id = m.commander_id
            WHERE p.name = ?
            GROUP BY c.name
            ORDER BY Partite DESC
        """, conn, params=(player,))
        player_commander_stats[player] = df

    player_stats = pd.read_sql_query("""
        SELECT p.name AS Giocatore,
               COUNT(m.id) AS Partite,
               SUM(m.win) AS Vittorie,
               ROUND(SUM(m.win) * 100.0 / COUNT(m.id), 2) AS "Winrate (%)"
        FROM players p
        LEFT JOIN matches m ON m.player_id = p.id
        GROUP BY p.name
    """, conn)

    color_stats = pd.read_sql_query("""
        SELECT c.color_identity AS Colore, COUNT(*) AS Utilizzi
        FROM commanders c
        JOIN matches m ON m.commander_id = c.id
        GROUP BY c.color_identity
        ORDER BY Utilizzi DESC
    """, conn)

    commander_stats = pd.read_sql_query("""
        SELECT c.name AS Comandante,
               COUNT(m.id) AS Partite,
               SUM(m.win) AS Vittorie,
               ROUND(SUM(m.win)*100.0 / COUNT(m.id), 2) AS "Winrate (%)"
        FROM commanders c
        JOIN matches m ON m.commander_id = c.id
        GROUP BY c.name
        ORDER BY "Winrate (%)" DESC
    """, conn)

    player_vs_others = pd.read_sql_query("""
        WITH match_data AS (
            SELECT m1.player_id AS player_id,
                   p1.name AS Giocatore,
                   m2.player_id AS opponent_id,
                   p2.name AS Avversario,
                   m1.win AS Vittorie
            FROM matches m1
            JOIN matches m2 ON m1.game_id = m2.game_id AND m1.player_id != m2.player_id
            JOIN players p1 ON m1.player_id = p1.id
            JOIN players p2 ON m2.player_id = p2.id
        )
        SELECT Giocatore,
               Avversario,
               COUNT(*) AS Partite,
               SUM(Vittorie) AS Vittorie,
               ROUND(SUM(Vittorie)*100.0 / COUNT(*), 2) AS "Winrate (%)"
        FROM match_data
        GROUP BY Giocatore, Avversario
        ORDER BY Giocatore, "Winrate (%)" DESC
    """, conn)

    cmc_medio_totale = pd.read_sql_query("SELECT ROUND(AVG(cmc), 2) AS cmc_medio FROM commanders", conn).iloc[0]["cmc_medio"]
    num_players = len(player_list)
    num_commanders = pd.read_sql_query("SELECT COUNT(DISTINCT commander_id) AS n FROM matches", conn).iloc[0]["n"]

    top_commanders_played = pd.read_sql_query("""
    SELECT c.name AS Comandante,
           COUNT(m.id) AS Partite
    FROM commanders c
    JOIN matches m ON c.id = m.commander_id
    GROUP BY c.name
    ORDER BY Partite DESC
    LIMIT 5
""", conn)

    top_commanders_winrate = pd.read_sql_query("""
    SELECT c.name AS Comandante,
           COUNT(m.id) AS Partite,
           SUM(m.win) AS Vittorie,
           ROUND(SUM(m.win)*100.0 / COUNT(m.id), 2) AS "Winrate (%)"
    FROM commanders c
    JOIN matches m ON c.id = m.commander_id
    GROUP BY c.name
    HAVING COUNT(m.id) >= 5  -- evita outlier con 1-2 partite
    ORDER BY "Winrate (%)" DESC
    LIMIT 5
""", conn)


    generate_html_report(
    player_winrate_over_time,
    player_commander_stats,
    color_stats,
    player_stats,
    commander_stats,
    player_vs_others,
    player_list,
    cmc_medio_totale,
    num_players,
    num_commanders,
    top_commanders_played,       # <--- QUI
    top_commanders_winrate       # <--- QUI
)


    conn.close()



def main():

    create_tables()

    parser = argparse.ArgumentParser(description="Gestione Partite Magic EDH")
    subparsers = parser.add_subparsers(dest="command")

    # Comando per registrare una partita in modalità interattiva
    record_parser = subparsers.add_parser("record", help="Registra una partita in modalità interattiva")

    # Comando per visualizzare la dashboard delle statistiche
    dashboard_parser = subparsers.add_parser("dashboard", help="Mostra la dashboard delle statistiche")

    # Comando per il caricamento in blocco di partite da un file
    bulk_upload_parser = subparsers.add_parser("bulk_upload", help="Carica partite da file")
    bulk_upload_parser.add_argument("filename", type=str, help="Nome del file per il caricamento in blocco")

    # Comando per generare il report delle statistiche in formato HTML
    report_parser = subparsers.add_parser("generate_report", help="Genera un report delle statistiche in formato HTML")

    # Parsing degli argomenti
    args = parser.parse_args()

    # Eseguiamo il comando selezionato
    if args.command == "record":
        interactive_record()
    elif args.command == "dashboard":
        show_dashboard()
    elif args.command == "bulk_upload":
        bulk_upload_matches(args.filename)
    elif args.command == "generate_report":
        generate_report()
    else:
        parser.print_help()



if __name__ == "__main__":
    main()