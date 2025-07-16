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
from datetime import datetime, timedelta


color_names = {
    'W': 'Mono White',
    'U': 'Mono Blue',
    'B': 'Mono Black',
    'R': 'Mono Red',
    'G': 'Mono Green',
    'WU': 'Azorius',
    'UW': 'Azorius',
    'WB': 'Orzhov',
    'BW': 'Orzhov',
    'UB': 'Dimir',
    'BU': 'Dimir',
    'UR': 'Izzet',
    'RU': 'Izzet',
    'BR': 'Rakdos',
    'RB': 'Rakdos',
    'BG': 'Golgari',
    'GB': 'Golgari',
    'RG': 'Gruul',
    'GR': 'Gruul',
    'WG': 'Selesnya',
    'GW': 'Selesnya',
    'WR': 'Boros',
    'RW': 'Boros',
    'UG': 'Simic',
    'GU': 'Simic',
    'WUB': 'Esper',
    'WBU': 'Esper',
    'UWB': 'Esper',
    'UBW': 'Esper',
    'BWU': 'Esper',
    'BUW': 'Esper',
    'UBR': 'Grixis',
    'URB': 'Grixis',
    'BUR': 'Grixis',
    'BRU': 'Grixis',
    'RUB': 'Grixis',
    'RBU': 'Grixis',
    'BRG': 'Jund',
    'BGR': 'Jund',
    'RBG': 'Jund',
    'RGB': 'Jund',
    'GBR': 'Jund',
    'GRB': 'Jund',
    'RGW': 'Naya',
    'RWG': 'Naya',
    'GRW': 'Naya',
    'GWR': 'Naya',
    'WRG': 'Naya',
    'WGR': 'Naya',
    'GWU': 'Bant',
    'GUW': 'Bant',
    'WUG': 'Bant',
    'WGU': 'Bant',
    'UWG': 'Bant',
    'UGW': 'Bant',
    'WUR': 'Jeskai',
    'WRU': 'Jeskai',
    'UWR': 'Jeskai',
    'URW': 'Jeskai',
    'RWU': 'Jeskai',
    'RUW': 'Jeskai',
    'URG': 'Temur',
    'UGR': 'Temur',
    'GRU': 'Temur',
    'GUR': 'Temur',
    'RUG': 'Temur',
    'RGU': 'Temur',
    'WBG': 'Abzan',
    'WGB': 'Abzan',
    'BWG': 'Abzan',
    'BGW': 'Abzan',
    'GWB': 'Abzan',
    'GBW': 'Abzan',
    'UBG': 'Sultai',
    'UGB': 'Sultai',
    'BUG': 'Sultai',
    'BGU': 'Sultai',
    'GUB': 'Sultai',
    'GBU': 'Sultai',
    'WBR': 'Mardu',
    'WRB': 'Mardu',
    'BWR': 'Mardu',
    'BRW': 'Mardu',
    'RWB': 'Mardu',
    'RBW': 'Mardu',
    'WUBRG': '5-Color',
    'WUBGR': '5-Color',
    'WU BRG': '5-Color',
    'WUGBR': '5-Color',
    'WUGRB': '5-Color',
    'WURBG': '5-Color',
    'WURGB': '5-Color',
    'WUBRG': '5-Color',
    'WUBGR': '5-Color',
    'WUBRG': '5-Color',
    'WRUBG': '5-Color',
    'WRGBU': '5-Color',
  
}

def get_current_season(today=None, anchor_date=datetime(2025, 7, 16).date(), season_length_days=90):
    if today is None:
        today = datetime.today().date()

    days_since_anchor = (today - anchor_date).days
    season_number = days_since_anchor // season_length_days
    season_start = anchor_date + timedelta(days=season_number * season_length_days)
    season_end = season_start + timedelta(days=season_length_days - 1)
    
    return season_start, season_end

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
css_style = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

  body {
    font-family: 'Inter', 'Roboto', 'Helvetica Neue', sans-serif;
    margin: 20px;
    background-color: #f5f7fa;
    color: #2e2e2e;
    line-height: 1.6;
    transition: background-color 0.3s, color 0.3s;
  }

  h1, h2, h3 {
    color: #1a1a1a;
    font-weight: 600;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 24px;
    background-color: #fff;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0,0,0,0.06);
  }

  th, td {
    padding: 14px;
    border: 1px solid #e0e0e0;
    text-align: center;
    font-size: 0.95rem;
  }

  th {
    background-color: #5865f2;
    color: #fff;
    text-transform: uppercase;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
  }

  tr:nth-child(even) {
    background-color: #f1f3f5;
  }

  tr:hover {
    background-color: #e4e8ee;
  }

  .player-section {
    margin-bottom: 30px;
    border: 1px solid #d8dee9;
    padding: 20px;
    border-radius: 12px;
    background-color: #ffffff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
  }

  .player-section h3 {
    margin-top: 0;
    background-color: #f0f2f5;
    padding: 12px;
    border-radius: 6px;
    font-weight: 600;
    color: #3b5bdb;
  }

  .hidden {
    display: none;
  }

  /* 🌙 Modalità Scura */
  @media (prefers-color-scheme: dark) {
    body {
      background-color: #121212;
      color: #e4e4e4;
    }

    h1, h2, h3 {
      color: #f1f1f1;
    }

    table {
      background-color: #1e1e1e;
      box-shadow: 0 2px 4px rgba(0,0,0,0.4);
    }

    th {
      background-color: #3b5bdb;
      color: #ffffff;
    }

    td, th {
      border-color: #2a2a2a;
    }

    tr:nth-child(even) {
      background-color: #222;
    }

    tr:hover {
      background-color: #2c2c2c;
    }

    .player-section {
      background-color: #1c1c1c;
      border-color: #2a2a2a;
    }

    .player-section h3 {
      background-color: #2a2a2a;
      color: #8faaff;
    }
  }
</style>
"""

# === HTML Report Generator ===
def generate_html_report(
    player_winrate_over_time,
    player_commander_stats,
    color_stats_most_played,
    color_stats_best_winrate,
    player_stats,
    victory_streak,
    commander_stats,
    player_vs_others,
    player_list,
    cmc_medio_totale,
    num_players,
    num_commanders,
    top_commanders_played,
    top_commanders_winrate,
    total_games,
    # Aggiunta:
    player_stats_season,
    top_commanders_played_season,
    top_commanders_winrate_season
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
{css_style}
</head>
<body>
<h1>Magic EDH Stats Report</h1>
<!-- Iniettata da Python -->
<p id="lastUpdated" data-ts="{timestamp}">Ultimo aggiornamento: --</p>

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
<p>Dati dal 31.10.2024</p>
<p><strong>CMC Medio Totale:</strong> {cmc_medio_totale}</p>
<p><strong>Numero Totale Giocatori:</strong> {num_players}</p>
<p><strong>Numero Totale Comandanti Giocati:</strong> {num_commanders}</p>
<p><strong>Numero Totale Partite Registrate:</strong> {total_games}</p>
<h2>Dettaglio Comandanti per Giocatore</h2>
<label for="commanderPlayerSelect">Seleziona Giocatore:</label>
<select id="commanderPlayerSelect">
<option value="">Seleziona un giocatore</option>
{"".join(f'<option value="{p}">{p}</option>' for p in player_list)}
</select>
""")
        for player, df in player_commander_stats.items():
            pid = player.replace(" ", "-")
            report_file.write(f"""
<div id="player-{pid}" class="player-section hidden player-commander-section">
<h3>Comandanti di {player}</h3>
{dataframe_to_table(df, f"commanderStatsTable-{pid}")}
</div>
""")
        report_file.write(f"""
<div style="display: flex; gap: 2em;">
  <div style="flex: 1;">
    <h2>Colori Più Utilizzati</h2>
    {dataframe_to_table(color_stats_most_played[["color_visual", "color_name", "total_games", "total_wins", "win_rate"]], "colorStatsMostPlayed")}
  </div>
  <div style="flex: 1;">
    <h2>Colori Più Vincenti</h2>
    {dataframe_to_table(color_stats_best_winrate[["color_visual", "color_name", "total_games", "total_wins", ]], "colorStatsBestWinrate")}
  </div>


</div>
<h2>Statistiche dei Giocatori</h2>
{dataframe_to_table(player_stats, "playerStatsTable")}
<h2>Top 5 Comandanti più Giocati</h2>
{dataframe_to_table(top_commanders_played, "topCommandersPlayedTable")}

<h2>Victory Streak</h2>
<p>Serie di vittorie più lunghe</p>
{dataframe_to_table(victory_streak, "winStreakTable")}

<h2>Top 5 Comandanti con Maggior Winrate (min. 5 partite)</h2>
{dataframe_to_table(top_commanders_winrate, "topCommandersWinrateTable")}
report_file.write(f"""
<h2>Statistiche della Stagione Corrente</h2>
report_file.write(f"<p>Periodo: {season_start} → {season_end}</p>")

<h3>Giocatori (min. 5 partite)</h3>
{dataframe_to_table(player_stats_season, "playerStatsSeasonTable")}

<h3>Top 5 Comandanti più Giocati (Stagione)</h3>
{dataframe_to_table(top_commanders_played_season, "topCommandersPlayedSeasonTable")}

<h3>Top 5 Comandanti con Maggior Winrate (Stagione, min. 5 partite)</h3>
{dataframe_to_table(top_commanders_winrate_season, "topCommandersWinrateSeasonTable")}
""")

<h2>Statistiche dei Comandanti</h2>
{dataframe_to_table(commander_stats, "commanderStatsTable")}
<h2>Statistiche Giocatore vs Avversario</h2>
<label for="playerSelect">Seleziona Giocatore:</label>
<select id="playerSelect">
<option value="Tutti">Tutti</option>
{"".join(f'<option value="{p}">{p}</option>' for p in player_list)}
</select>
{dataframe_to_table(player_vs_others, "playerVsOthersTable")}
<h2>Andamento Win Rate nel Tempo</h2>
<label for="winratePlayerSelect">Seleziona Giocatore:</label>
<select id="winratePlayerSelect">
<option value="">Seleziona un giocatore</option>
{"".join(f'<option value="{p}">{p}</option>' for p in player_list)}
</select>
<canvas id="winrateChart" width="800" height="400"></canvas>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const chartData = {json.dumps(chart_data_js)};
$(document).ready(function() {{
    $('#colorStatsTable, #playerStatsTable, #commanderStatsTable, #playerVsOthersTable, #topCommandersPlayedTable, #topCommandersWinrateTable').DataTable();
    $('.player-commander-section table.display').each(function() {{
        $(this).DataTable({{ paging: false, info: false }});
    }});
    $('#playerSelect').on('change', function() {{
        var val = $(this).val();
        var table = $('#playerVsOthersTable').DataTable();
        table.column(0).search(val === "Tutti" ? "" : "^" + val + "$", true, false).draw();
    }});
    $('#commanderPlayerSelect').on('change', function() {{
        var val = $(this).val();
        $('.player-commander-section').addClass('hidden');
        if (val) $('#player-' + val.replace(' ', '-')).removeClass('hidden');
    }});
    const ctx = document.getElementById('winrateChart').getContext('2d');
    const winrateChart = new Chart(ctx, {{
        type: 'line',
        data: {{ labels: [], datasets: [{{ label: 'Win Rate (%)', data: [], borderColor: 'rgb(75,192,192)', tension: 0.1 }}] }},
        options: {{ scales: {{ y: {{ beginAtZero: true, max: 100 }} }} }}
    }});
    document.getElementById("winratePlayerSelect").addEventListener("change", function() {{
        const player = this.value;
        if (!player || !chartData[player]) return;
        const data = chartData[player];
        winrateChart.data.labels = data.map(p => p.data);
        winrateChart.data.datasets[0].data = data.map(p => p.winrate);
        winrateChart.update();
    }});
}});
</script>

</body>
</html>
""")
    print("✅ Report HTML generato con successo: edh_report.html")

# === Statistiche dal DB ===
def generate_report():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    season_start, season_end = get_current_season()

    total_games = pd.read_sql_query("SELECT COUNT(DISTINCT game_id) AS total FROM matches;", conn).iloc[0]["total"]

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
            HAVING COUNT(m.id) >= 20
            ORDER BY "Winrate (%)" DESC, Vittorie DESC
        """, conn)

        # === Top 5 color identity più giocate ===
    color_stats_most_played = pd.read_sql_query("""
        SELECT
          c.color_identity,
          COUNT(*) AS total_games,
          SUM(m.win) AS total_wins,
          ROUND(SUM(m.win) * 1.0 / COUNT(*) * 100, 2) AS win_rate
        FROM matches m
        JOIN commanders c ON m.commander_id = c.id
        GROUP BY c.color_identity
        HAVING COUNT(*) >= 5
        ORDER BY total_games DESC
        LIMIT 5;
    """, conn)

    # === Top 5 color identity più vincenti ===
    color_stats_best_winrate = pd.read_sql_query("""
        SELECT
          c.color_identity,
          COUNT(*) AS total_games,
          SUM(m.win) AS total_wins
          
        FROM matches m
        JOIN commanders c ON m.commander_id = c.id
        GROUP BY c.color_identity
        
        ORDER BY total_wins DESC
        LIMIT 5;
    """, conn)

    # === Mappa da simboli a emoji ===
    mana_symbols = {
        'W': '⚪️',  # White
        'U': '🔵',  # Blue
        'B': '⚫️',  # Black
        'R': '🔴',  # Red
        'G': '🟢',  # Green
    }

    mana_order = ['W', 'U', 'B', 'R', 'G']

    def convert_identity_to_icons(identity):
        if not identity:
            return ''
        ordered = [c for c in mana_order if c in identity]
        return ''.join(mana_symbols.get(c, c) for c in ordered)
    def convert_identity_to_name(identity):
        if not identity:
            return 'Colorless'
        key = ''.join([c for c in mana_order if c in identity])
        return color_names.get(key, key)

    # Aggiungi colonne
    for df in [color_stats_most_played, color_stats_best_winrate]:
        df["color_identity"] = df["color_identity"].apply(lambda cid: ''.join([c for c in mana_order if c in cid]))
        df["color_visual"] = df["color_identity"].apply(convert_identity_to_icons)
        df["color_name"] = df["color_identity"].apply(convert_identity_to_name)

        # === SEASON: ultimi 3 mesi ===
    player_stats_season = pd.read_sql_query("""
    SELECT p.name AS Giocatore,
           COUNT(m.id) AS Partite,
           SUM(m.win) AS Vittorie,
           ROUND(SUM(m.win) * 100.0 / COUNT(m.id), 2) AS "Winrate (%)"
    FROM players p
    LEFT JOIN matches m ON m.player_id = p.id
    WHERE date(m.date) BETWEEN ? AND ?
    GROUP BY p.name
    HAVING COUNT(m.id) >= 5
    ORDER BY "Winrate (%)" DESC, Vittorie DESC
""", conn, params=(season_start, season_end))

    top_commanders_played_season = pd.read_sql_query("""
    SELECT c.name AS Comandante,
           COUNT(m.id) AS Partite
    FROM commanders c
    JOIN matches m ON c.id = m.commander_id
    WHERE date(m.date) BETWEEN ? AND ?
    GROUP BY c.name
    ORDER BY Partite DESC
    LIMIT 5
""", conn, params=(season_start, season_end))

top_commanders_winrate_season = pd.read_sql_query("""
    SELECT c.name AS Comandante,
           COUNT(m.id) AS Partite,
           SUM(m.win) AS Vittorie,
           ROUND(SUM(m.win)*100.0 / COUNT(m.id), 2) AS "Winrate (%)"
    FROM commanders c
    JOIN matches m ON c.id = m.commander_id
    WHERE date(m.date) BETWEEN ? AND ?
    GROUP BY c.name
    HAVING COUNT(m.id) >= 5
    ORDER BY "Winrate (%)" DESC
    LIMIT 5
""", conn, params=(season_start, season_end))




    victory_streak= pd.read_sql_query("""
            WITH sorted_matches AS (
      SELECT
        m.id,
        m.player_id,
        m.date,
        m.commander_id,
        m.win,
        ROW_NUMBER() OVER (PARTITION BY m.player_id ORDER BY m.date) AS rn_all,
        ROW_NUMBER() OVER (PARTITION BY m.player_id, m.win ORDER BY m.date) AS rn_by_win
      FROM matches m
    ),

    win_streaks_raw AS (
      SELECT
        *,
        rn_all - rn_by_win AS grp
      FROM sorted_matches
      WHERE win = 1
    ),

    win_streaks_base AS (
      SELECT
        player_id,
        grp,
        COUNT(*) AS streak_length,
        MIN(date) AS streak_start,
        MAX(date) AS streak_end
      FROM win_streaks_raw
      GROUP BY player_id, grp
      HAVING COUNT(*) >= 2
    ),

    commander_wins_per_streak AS (
      SELECT
        w.player_id,
        w.grp,
        c.name AS commander_name,
        COUNT(*) AS wins_with_commander
      FROM win_streaks_raw w
      JOIN commanders c ON w.commander_id = c.id
      GROUP BY w.player_id, w.grp, w.commander_id
    ),

    commander_summary AS (
      SELECT
        player_id,
        grp,
        GROUP_CONCAT(commander_name || ' (' || wins_with_commander || ')') AS commanders_used
      FROM commander_wins_per_streak
      GROUP BY player_id, grp
    )

    SELECT
      p.name AS player,
      ws.streak_length,
      ws.streak_start,
      ws.streak_end,
      cs.commanders_used
    FROM win_streaks_base ws
    JOIN commander_summary cs ON ws.player_id = cs.player_id AND ws.grp = cs.grp
    JOIN players p ON ws.player_id = p.id
    ORDER BY streak_length DESC, streak_start ASC
    LIMIT 5;

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
    LIMIT 10
""", conn)


    generate_html_report(
    player_winrate_over_time,
    player_commander_stats,
    color_stats_most_played,
    color_stats_best_winrate,
    player_stats,
    victory_streak,
    commander_stats,
    player_vs_others,
    player_list,
    cmc_medio_totale,
    num_players,
    num_commanders,
    top_commanders_played,
    top_commanders_winrate,
    total_games,
    player_stats_season,
    top_commanders_played_season,
    top_commanders_winrate_season
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