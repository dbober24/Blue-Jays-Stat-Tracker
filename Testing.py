import requests
import time
import threading
from datetime import date
from datetime import datetime, timezone
import tkinter as tk

# Get game information for a specific team
def get_game_info(team_id):
    today = date.today()
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        games = requests.get(sched_url).json()["dates"][0]["games"]
    except (KeyError, IndexError):
        return None, None
    for game in games:
        if game["teams"]["home"]["team"]["id"] == team_id or game["teams"]["away"]["team"]["id"] == team_id:
            game_pk = game["gamePk"]
            game_time = game["gameDate"]  # UTC ISO format
            return game_pk, game_time
    return None, None

# Get current batter and pitcher information for a specific game
def get_current_players(game_pk):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        data = requests.get(url).json()
        batter = data["liveData"]["plays"]["currentPlay"]["matchup"]["batter"]
        pitcher = data["liveData"]["plays"]["currentPlay"]["matchup"]["pitcher"]
        return batter["fullName"], batter["id"], pitcher["fullName"], pitcher["id"]
    except KeyError:
        return "Waiting for play...", None, "Waiting for play...", None

# Fetch batter stats for the season
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
        return f"AVG: {avg} | HR: {hr} | RBI: {rbi} | OPS: {ops}"
    except (KeyError, IndexError):
        return "Stats unavailable"

# Fetch pitcher stats for the season
def get_pitcher_stats(pitcher_id):
    if not pitcher_id:
        return "Stats unavailable"
    stats_url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats?stats=statsSingleSeason&season={date.today().year}&group=pitching"
    try:
        stats_data = requests.get(stats_url).json()
        stats = stats_data["stats"][0]["splits"][0]["stat"]
        era = stats.get("era", "N/A")
        strikeouts = stats.get("strikeOuts", "N/A")
        wins = stats.get("wins", "N/A")
        innings = stats.get("inningsPitched", "N/A")
        return f"ERA: {era} | K: {strikeouts} | Wins: {wins} | IP: {innings}"
    except (KeyError, IndexError):
        return "Stats unavailable"


# Update display to show current batter, pitcher stats, and post-game score
def update_game_display(team_id, label):
    game_pk, game_time_utc = get_game_info(team_id)
    if not game_pk:
        label.config(text="Team not playing today.")
        return

    game_start = datetime.fromisoformat(game_time_utc.replace('Z', '+00:00'))

    def refresh():
        last_batter = ""
        last_pitcher = ""
        while True:
            now = datetime.now(timezone.utc)
            if now < game_start:
                countdown = game_start - now
                hours, remainder = divmod(int(countdown.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                label.config(text=f"Game starts in: {hours:02}:{minutes:02}:{seconds:02}")
            else:
                # Check if the game is completed
                game_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
                data = requests.get(game_url).json()
                game_status = data["gameData"]["status"]["detailedState"]
                
                if game_status == "Final":
                    home_team_name = data["gameData"]["teams"]["home"]["teamName"]
                    away_team_name = data["gameData"]["teams"]["away"]["teamName"]
                    home_score = data["liveData"]["linescore"]["teams"]["home"]["runs"]
                    away_score = data["liveData"]["linescore"]["teams"]["away"]["runs"]
                    label.config(text=f"Game Over!\n{away_team_name} {away_score} - {home_team_name} {home_score}")
                else:
                    batter_name, batter_id, pitcher_name, pitcher_id = get_current_players(game_pk)
                    if batter_name != last_batter or pitcher_name != last_pitcher:
                        batter_stats = get_batter_stats(batter_id)
                        pitcher_stats = get_pitcher_stats(pitcher_id)
                        label.config(text=f"Current Batter: {batter_name}\n{batter_stats}\n\nCurrent Pitcher: {pitcher_name}\n{pitcher_stats}")
                        last_batter = batter_name
                        last_pitcher = pitcher_name
            time.sleep(1 if now < game_start else 5)

    threading.Thread(target=refresh, daemon=True).start()



# GUI setup
def launch_gui(team_id):
    root = tk.Tk()
    root.title("MLB Live Game Tracker")
    root.geometry("1024x600")              
    label = tk.Label(root, text="Loading...", font=("Helvetica", 40), justify="center", anchor="center", wraplength=1000)
    label.pack(expand=True, fill="both", pady=20)
    update_game_display(team_id, label)
    root.mainloop()

# Example: Launch GUI for (Blue Jays teamID=141) Link to all team codes https://github.com/jasonlttl/gameday-api-docs/blob/master/team-information.md
launch_gui(141)
