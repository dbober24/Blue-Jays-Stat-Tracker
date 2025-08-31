import requests
import time
import threading
from datetime import date, datetime, timezone
import tkinter as tk

# This global event is crucial for cleanly stopping the background thread when changing teams.
stop_event = threading.Event()

# --- DATA FETCHING FUNCTIONS (Largely Unchanged) ---
def get_game_info(team_id):
    """Fetches the game ID for today or the date of the next upcoming game."""
    today = date.today()
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={today}&endDate={today}"
    try:
        # First, check for a game today
        dates = requests.get(sched_url, timeout=5).json().get("dates", [])
        if dates:
            games = dates[0].get("games", [])
            for game in games:
                if game["teams"]["home"]["team"]["id"] == team_id or game["teams"]["away"]["team"]["id"] == team_id:
                    return game["gamePk"], game["gameDate"], None
    except (IndexError, KeyError, requests.exceptions.RequestException) as e:
        print(f"Could not fetch today's game info: {e}")

    # If no game today, find the next one
    future_sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={today}&endDate={date(today.year, 12, 31)}"
    try:
        future_dates = requests.get(future_sched_url, timeout=5).json().get("dates", [])
        if future_dates and future_dates[0].get("games"):
            return None, None, future_dates[0]["games"][0]["gameDate"]
    except (IndexError, KeyError, requests.exceptions.RequestException) as e:
        print(f"Error fetching future games: {e}")

    return None, None, None

def get_current_players_and_live_data(game_pk):
    """Gets live game data, including the current batter and pitcher."""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        data = requests.get(url, timeout=5).json()
        batter_name, batter_id = "Waiting for play...", None
        pitcher_name, pitcher_id = "Waiting for play...", None
        current_play_matchup = data.get("liveData", {}).get("plays", {}).get("currentPlay", {}).get("matchup")
        if current_play_matchup:
            batter = current_play_matchup.get("batter")
            pitcher = current_play_matchup.get("pitcher")
            if batter:
                batter_name = batter.get("fullName", "Unknown Batter")
                batter_id = batter.get("id")
            if pitcher:
                pitcher_name = pitcher.get("fullName", "Unknown Pitcher")
                pitcher_id = pitcher.get("id")
        return batter_name, batter_id, pitcher_name, pitcher_id, data
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching live data: {e}")
        return "Error...", None, "Error...", None, {}
    except (KeyError, ValueError): # Handles potential JSON parsing errors
        return "Waiting for play...", None, "Waiting for play...", None, {}

def get_batter_stats(batter_id):
    if not batter_id:
        return "Stats unavailable"
    stats_url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=statsSingleSeason&season={date.today().year}&group=hitting"
    try:
        stats_data = requests.get(stats_url).json()
        stats = stats_data["stats"][0]["splits"][0]["stat"]
        avg = stats.get("avg", "N/A")
        hr = stats.get("homeRuns", "N/A")
        rbi = stats.get("rbi", "N/A")
        ops = stats.get("ops", "N/A")
        obp = stats.get("obp", "N/A")
        return f"AVG: {avg} | HR: {hr} | RBI: {rbi} | OPS: {ops} | OBP: {obp}"
    except (KeyError, IndexError):
        return "Stats unavailable"
    except requests.exceptions.RequestException:
        return "Stats unavailable (network error)"

def get_pitcher_stats(pitcher_id):
    if not pitcher_id:
        return "Stats unavailable"
    stats_url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats?stats=statsSingleSeason&season={date.today().year}&group=pitching"
    try:
        stats_data = requests.get(stats_url).json()
        stats = stats_data["stats"][0]["splits"][0]["stat"]
        era = stats.get("era", "N/A")
        strikeoutWalkRatio = stats.get("strikeoutWalkRatio", "N/A")
        pitchesPerInning = stats.get("pitchesPerInning", "N/A")
        strikePercentage = stats.get("strikePercentage", "N/A")
        return f"ERA: {era} | K-BB: {strikeoutWalkRatio} | PPI: {pitchesPerInning}| Strike%: {strikePercentage}"
    except (KeyError, IndexError):
        return "Stats unavailable"
    except requests.exceptions.RequestException:
        return "Stats unavailable (network error)"

# --- REFACTORED THREADING AND GUI LOGIC ---
def update_game_display(team_id, label, view_mode, toggle_btn, force_refresh, stop_event_ref):
    """The main worker function that runs in a background thread."""
    game_pk, game_time_utc, next_game_time = get_game_info(team_id)

    if stop_event_ref.is_set(): return # Exit if a new team was selected quickly

    if not game_pk:
        if next_game_time:
            try:
                dt = datetime.fromisoformat(next_game_time.replace("Z", "+00:00")).astimezone()
                formatted_time = dt.strftime("%A, %B %d @ %I:%M %p")
                label.config(text=f"No Game Today\n\nNext Game: {formatted_time}")
            except Exception:
                label.config(text="No Game Today\n\nNext Game: Date/time unavailable")
        else:
            label.config(text="No game scheduled for the remainder of the season.")
        toggle_btn.pack_forget()
        return

    try:
        game_start = datetime.fromisoformat(game_time_utc.replace('Z', '+00:00'))
    except ValueError:
        label.config(text="Error parsing game time.")
        toggle_btn.pack_forget()
        return

    def refresh():
        last_batter, last_pitcher, last_play_id = "", "", None
        last_view_mode = view_mode.get()

        while not stop_event_ref.is_set():
            now_utc = datetime.now(timezone.utc)

            # --- Game State Logic ---
            if now_utc < game_start:
                countdown = game_start - now_utc
                hours, remainder = divmod(int(countdown.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                label.config(text=f"Game Starts In: {hours:02}:{minutes:02}:{seconds:02}")
                toggle_btn.pack_forget()
                time.sleep(1)
                continue

            batter_name, batter_id, pitcher_name, pitcher_id, live_data = get_current_players_and_live_data(game_pk)
            game_status = live_data.get("gameData", {}).get("status", {}).get("detailedState", "Unknown")

            if game_status == "Final":
                home = live_data.get("gameData", {}).get("teams", {}).get("home", {})
                away = live_data.get("gameData", {}).get("teams", {}).get("away", {})
                home_score = live_data.get("liveData", {}).get("linescore", {}).get("teams", {}).get("home", {}).get("runs", "N/A")
                away_score = live_data.get("liveData", {}).get("linescore", {}).get("teams", {}).get("away", {}).get("runs", "N/A")
                
                away_record = away.get('record', {}).get('leagueRecord', {})
                home_record = home.get('record', {}).get('leagueRecord', {})
                
                label.config(
                        text=f"Game Over!\n"
                             f"{away.get('teamName', 'Away')} {away_score} - {home.get('teamName', 'Home')} {home_score}\n"
                             f"({away_record.get('wins', 'N/A')}-{away_record.get('losses', 'N/A')})   "
                             f"({home_record.get('wins', 'N/A')}-{home_record.get('losses', 'N/A')})"
                    )
                toggle_btn.pack_forget()
                break # Exit loop and end thread

            if not toggle_btn.winfo_ismapped():
                toggle_btn.pack(pady=10)

            # --- Data Display Logic ---
            current_play_obj = live_data.get("liveData", {}).get("plays", {}).get("currentPlay", {})
            current_play_id = current_play_obj.get("playEvents", [{}])[-1].get("playId") if current_play_obj.get("playEvents") else None

            if (batter_name != last_batter or pitcher_name != last_pitcher or view_mode.get() != last_view_mode or force_refresh.get() or current_play_id != last_play_id):
                if view_mode.get() == "stats":
                    batter_stats = get_batter_stats(batter_id)
                    pitcher_stats = get_pitcher_stats(pitcher_id)
                    label.config(text=f"Batter: {batter_name}\n{batter_stats}\n\nPitcher: {pitcher_name}\n{pitcher_stats}")
                else: # "pitch" view
                    all_plays = live_data.get("liveData", {}).get("plays", {}).get("allPlays", [])
                    pitch_found = False
                    for play in reversed(all_plays):
                        for event in reversed(play.get("playEvents", [])):
                            if event.get("isPitch") and event.get("pitchData"):
                                pitch_type = event.get("details", {}).get("type", {}).get("description", "N/A")
                                speed = event.get("pitchData", {}).get("startSpeed", "N/A")
                                outcome = event.get("details", {}).get("description", "N/A")
                                pitch_data = event.get("pitchData", {})
                                break_vert = pitch_data.get("breaks", {}).get("breakVertical", "N/A")
                                break_hori = pitch_data.get("breaks", {}).get("breakHorizontal", "N/A")
                                label.config(text=f"Last Pitch to {batter_name}:\n{pitch_type} ({speed} mph)\nResult: {outcome}:\n  Vertical Break: {break_vert}:\nHorizontal Break:{break_hori}")
                                pitch_found = True
                                break
                        if pitch_found: break
                    if not pitch_found:
                        label.config(text="Waiting for first pitch of at-bat...")
                last_batter, last_pitcher, last_view_mode, last_play_id = batter_name, pitcher_name, view_mode.get(), current_play_id
                force_refresh.set(False)

            # --- Interruptible Sleep Logic ---
            sleep_time = 1 if view_mode.get() == "pitch" else 5
            for _ in range(int(sleep_time * 10)):
                if force_refresh.get() or stop_event_ref.is_set():
                    break
                time.sleep(0.1)

    threading.Thread(target=refresh, daemon=True).start()

def launch_gui(initial_team_id=141):
    root = tk.Tk()
    root.title("MLB Live Game Tracker")
    root.geometry("1024x600")

    global stop_event

    view_mode = tk.StringVar(value="stats")
    force_refresh = tk.BooleanVar(value=False)
    current_font_size = tk.IntVar(value=32)
    current_theme = tk.StringVar(value="light")
    root.configure(bg="white")

    label = tk.Label(
        root, text="Loading...", font=("Helvetica", current_font_size.get()),
        justify="center", anchor="center", wraplength=1000, bg="white", fg="black"
    )
    label.pack(expand=True, fill="both", pady=20)

    # --- Settings Functions ---
    def apply_theme():
        bg, fg = ("black", "white") if current_theme.get() == "dark" else ("white", "black")
        root.configure(bg=bg)
        label.configure(bg=bg, fg=fg)

    def change_font(size):
        current_font_size.set(size)
        label.config(font=("Helvetica", size))

    def change_team(new_team_id):
        global stop_event
        stop_event.set() # Signal the old thread to stop
        time.sleep(0.2)  # Give the thread a moment to exit
        stop_event = threading.Event() # Create a new, clear event for the new thread
        label.config(text=f"Loading data for new team...")
        update_game_display(new_team_id, label, view_mode, toggle_btn, force_refresh, stop_event)

    def toggle_view():
        view_mode.set("pitch" if view_mode.get() == "stats" else "stats")
        force_refresh.set(True)

    toggle_btn = tk.Button(root, text="Toggle View", command=toggle_view, font=("Helvetica", 20))

        # --- MENU BAR SETUP ---
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    # Main Settings Menu
    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Settings", menu=settings_menu)

    # 1. Team Selection Submenu
    team_menu = tk.Menu(settings_menu, tearoff=0)
    settings_menu.add_cascade(label="Select Team", menu=team_menu)
    ALL_TEAMS = {
        "American League": {
            "East": [
                {"name": "Baltimore Orioles", "id": 110},
                {"name": "Boston Red Sox", "id": 111},
                {"name": "New York Yankees", "id": 147},
                {"name": "Tampa Bay Rays", "id": 139},
                {"name": "Toronto Blue Jays", "id": 141},
            ],
            "Central": [
                {"name": "Chicago White Sox", "id": 145},
                {"name": "Cleveland Guardians", "id": 114},
                {"name": "Detroit Tigers", "id": 116},
                {"name": "Kansas City Royals", "id": 118},
                {"name": "Minnesota Twins", "id": 142},
            ],
            "West": [
                {"name": "Houston Astros", "id": 117},
                {"name": "Los Angeles Angels", "id": 108},
                {"name": "Oakland Athletics", "id": 133},
                {"name": "Seattle Mariners", "id": 136},
                {"name": "Texas Rangers", "id": 140},
            ],
        },
        "National League": {
            "East": [
                {"name": "Atlanta Braves", "id": 144},
                {"name": "Miami Marlins", "id": 146},
                {"name": "New York Mets", "id": 121},
                {"name": "Philadelphia Phillies", "id": 143},
                {"name": "Washington Nationals", "id": 120},
            ],
            "Central": [
                {"name": "Chicago Cubs", "id": 112},
                {"name": "Cincinnati Reds", "id": 113},
                {"name": "Milwaukee Brewers", "id": 158},
                {"name": "Pittsburgh Pirates", "id": 134},
                {"name": "St. Louis Cardinals", "id": 138},
            ],
            "West": [
                {"name": "Arizona Diamondbacks", "id": 109},
                {"name": "Colorado Rockies", "id": 115},
                {"name": "Los Angeles Dodgers", "id": 119},
                {"name": "San Diego Padres", "id": 135},
                {"name": "San Francisco Giants", "id": 137},
            ],
        },
    }
    for league_name, divisions in ALL_TEAMS.items():
        league_menu = tk.Menu(team_menu, tearoff=0)
        team_menu.add_cascade(label=league_name, menu=league_menu)
        for division_name, teams_in_division in divisions.items():
            division_menu = tk.Menu(league_menu, tearoff=0)
            league_menu.add_cascade(label=division_name, menu=division_menu)
            for team in teams_in_division:
                division_menu.add_command(
                    label=team["name"],
                    command=lambda id=team["id"]: change_team(id)
                )

    # 2. Font Size Submenu
    font_menu = tk.Menu(settings_menu, tearoff=0)
    settings_menu.add_cascade(label="Font Size", menu=font_menu)
    font_menu.add_command(label="Small", command=lambda: change_font(24))
    font_menu.add_command(label="Medium", command=lambda: change_font(32))
    font_menu.add_command(label="Large", command=lambda: change_font(48))

    # 3. Theme Submenu
    theme_menu = tk.Menu(settings_menu, tearoff=0)
    settings_menu.add_cascade(label="Theme", menu=theme_menu)
    theme_menu.add_command(label="Light", command=lambda: (current_theme.set("light"), apply_theme()))
    theme_menu.add_command(label="Dark", command=lambda: (current_theme.set("dark"), apply_theme()))
    # --- END OF MENU BAR ---


    # Initial start
    update_game_display(initial_team_id, label, view_mode, toggle_btn, force_refresh, stop_event)
    root.mainloop()

if __name__ == "__main__":
    # Blue Jays team ID = 141
    launch_gui(141)

# Increased Size of Settings Tabs
