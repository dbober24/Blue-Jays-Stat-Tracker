import requests
import time
import threading
from datetime import date, datetime, timezone
import tkinter as tk

def get_game_info(team_id):
    today = date.today()

    # First, try today’s games
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={today}&endDate={today}"
    try:
        games = requests.get(sched_url).json().get("dates", [])[0].get("games", [])
        for game in games:
            if game["teams"]["home"]["team"]["id"] == team_id or game["teams"]["away"]["team"]["id"] == team_id:
                return game["gamePk"], game["gameDate"], None
    except (IndexError, KeyError):
        pass  # No game today

    # If no game today, search up to 30 days ahead for the next game
    future_sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={today}&endDate={date(today.year, 12, 31)}"
    try:
        future_dates = requests.get(future_sched_url).json().get("dates", [])
        for day in future_dates:
            for game in day.get("games", []):
                return None, None, game["gameDate"]  # This is the next game
    except Exception as e:
        print(f"Error fetching future games: {e}")

    return None, None, None  # No future games found



def get_current_players_and_live_data(game_pk):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        data = requests.get(url).json()
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
    except KeyError:
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

def update_game_display(team_id, label, view_mode, toggle_btn, force_refresh):
    game_pk, game_time_utc, next_game_time = get_game_info(team_id)
    if not game_pk:
        if next_game_time:
            try:
                dt = datetime.fromisoformat(next_game_time.replace("Z", "+00:00")).astimezone()
                formatted_time = dt.strftime("%A, %B %d @ %I:%M %p")
                label.config(text=f"No Game Today\n\nNext Game: {formatted_time}")
            except Exception:
              label.config(text="No Game Today\n\nNext Game: Date/time unavailable")
        else:             
            label.config(text="No Game Today")
        toggle_btn.pack_forget()
        return

    try:
        game_start = datetime.fromisoformat(game_time_utc.replace('Z', '+00:00'))
    except ValueError:
        print(f"Warning: Could not parse game_time_utc: {game_time_utc}")
        label.config(text="Error parsing game time.")
        toggle_btn.pack_forget()
        return


    def refresh():
        last_batter = ""
        last_pitcher = ""
        last_view_mode = view_mode.get()
        current_game_pk = game_pk
        current_game_start = game_start
        game_ended = False
        game_final_displayed_at = None
        previous_date = datetime.now(timezone.utc).date()


        # Initialize last_pitch_info with all possible keys
        last_pitch_info = {
            "type": "N/A", "speed": "N/A", "outcome": "N/A",
            "break_angle": "N/A", "vertical_break": "N/A",
            "horizontal_break": "N/A", "spin_rate": "N/A"
        }
        last_play_id = None

        while True:
            now = datetime.now(timezone.utc)

            batter_name, batter_id, pitcher_name, pitcher_id, live_data = get_current_players_and_live_data(current_game_pk)

            game_status = live_data.get("gameData", {}).get("status", {}).get("detailedState", "Unknown")

            # --- Game State Logic ---
            if now < current_game_start:
                countdown = current_game_start - now
                hours, remainder = divmod(int(countdown.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                label.config(text=f"Game Starts In: {hours:02}:{minutes:02}:{seconds:02}")
                toggle_btn.pack_forget()
                time.sleep(1)
                continue

            if game_status == "Final":
                if not game_ended:
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
                    game_ended = True
                    toggle_btn.pack_forget()
                new_pk,new_time,_ = get_game_info(team_id)

                if new_pk and new_pk != current_game_pk:
                    # ...then reset the state for the new game.
                    current_game_pk = new_pk
                    current_game_start = datetime.fromisoformat(new_time.replace('Z', '+00:00'))
                    last_batter = ""
                    last_pitcher = ""
                    game_ended = False
                    label.config(text="Loading next game...")
                    time.sleep(2) # Show message briefly
                    continue      # Restart the loop for the new game

                time.sleep(60)
                continue

            # If game is not final and has started, show toggle button
            if not toggle_btn.winfo_ismapped():
                toggle_btn.pack(pady=10)

            # --- Data Display Logic ---
            current_play_obj = live_data.get("liveData", {}).get("plays", {}).get("currentPlay", {})
            current_play_id = current_play_obj.get("playEvents", [{}])[-1].get("playId") if current_play_obj.get("playEvents") else None

            # Check if current batter/pitcher changed, view mode changed, or a new play started
            if (
                batter_name != last_batter or
                pitcher_name != last_pitcher or
                view_mode.get() != last_view_mode or
                force_refresh.get() or
                current_play_id != last_play_id
            ):
                if view_mode.get() == "stats":
                    batter_stats = get_batter_stats(batter_id)
                    pitcher_stats = get_pitcher_stats(pitcher_id)
                    label.config(
                        text=f"Current Batter: {batter_name}\n{batter_stats}\n\nCurrent Pitcher: {pitcher_name}\n{pitcher_stats}"
                    )
                else: # view_mode == "pitch"
                    pitch_found = False
                    all_plays = live_data.get("liveData", {}).get("plays", {}).get("allPlays", [])
                    for play in reversed(all_plays):
                        for event in reversed(play.get("playEvents", [])):
                            if event.get("isPitch", False) and event.get("pitchData"):
                                pitch_type = event.get("details", {}).get("type", {}).get("description", "Unknown")
                                speed = event.get("pitchData", {}).get("startSpeed", "N/A")
                                outcome = event.get("details", {}).get("description", "N/A")
                                
                                # Accessing break and spin data more safely
                                pitch_data = event.get("pitchData", {})
                                break_vert = pitch_data.get("breaks", {}).get("breakVertical", "N/A")
                                break_hori = pitch_data.get("breaks", {}).get("breakHorizontal", "N/A")
                                

                                last_pitch_info = {
                                    "type": pitch_type,
                                    "speed": speed,
                                    "outcome": outcome,
                                    "vertical_break": break_vert,  # Changed key for consistency
                                    "horizontal_break": break_hori, # Changed key for consistency
                                            # Changed key for consistency
                                }
                                pitch_found = True
                                break # Found the most recent pitch, stop inner loop
                        if pitch_found:
                            break # Found the most recent pitch, stop outer loop

                    if pitch_found:
                        label.config(
                            text=f"Last Pitch:\n"
                                 f"{last_pitch_info['type']}\n"
                                 f"{last_pitch_info['speed']} mph\n"
                                 f"{last_pitch_info['outcome']}\n"
                                 f"Vertical Break: {last_pitch_info['vertical_break']} in\n" # Added units
                                 f"Horizontal Break: {last_pitch_info['horizontal_break']} in\n" # Added unit
                        )
                    else:
                        label.config(text="No recent pitch data available. Waiting for next pitch or game action...")

                last_batter = batter_name
                last_pitcher = pitcher_name
                last_view_mode = view_mode.get()
                last_play_id = current_play_id
                force_refresh.set(False)

            # --- Sleep Logic ---
            sleep_time = 1 if view_mode.get() == "pitch" else 5
            for _ in range(int(sleep_time * 10)):
                if force_refresh.get():
                    break
                time.sleep(0.1)

    threading.Thread(target=refresh, daemon=True).start()

def launch_gui(team_id):
    root = tk.Tk()
    root.title("MLB Live Game Tracker")
    root.geometry("1024x600")

    view_mode = tk.StringVar(value="stats")
    force_refresh = tk.BooleanVar(value=False)

    label = tk.Label(root, text="Loading...", font=("Helvetica", 32), justify="center", anchor="center", wraplength=1000)
    label.pack(expand=True, fill="both", pady=20)

    def toggle_view():
        view_mode.set("pitch" if view_mode.get() == "stats" else "stats")
        force_refresh.set(True)

    toggle_btn = tk.Button(root, text="Toggle View", command=toggle_view, font=("Helvetica", 20))

    update_game_display(team_id, label, view_mode, toggle_btn, force_refresh)
    root.mainloop()

# Blue Jays team ID = 141
launch_gui(141)

# LOGS 
# added next game time on no game today screen
