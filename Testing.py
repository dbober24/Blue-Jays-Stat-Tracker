# what to add next: team has no schedualed game screen
# make random stat year,leauge,team totals 
# git hub 
# game gets postponed / double header
# Stat Card 

import statsapi
from PIL import Image, ImageDraw
import datetime
import time  
import pytz
import matplotlib.pyplot as plt
import numpy as np
import random
from matplotlib.widgets import Button


TEAM_ID = 141
WIDTH = 320
HEIGHT = 240
TORONTO_TZ = pytz.timezone('America/Toronto')

# Toggle state (True = show batter, False = show pitcher)
show_batter = True


# Set up font
from PIL import ImageFont
try:
    font_large = ImageFont.truetype("arial.ttf", 24)  # Was default; now larger
    font_small = ImageFont.truetype("arial.ttf", 18)
except:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

def render_image(image):
    global ax, fig, toggle_ax, toggle_button

    img_array = np.asarray(image)

    if 'fig' not in globals():
        fig, ax = plt.subplots()
        plt.subplots_adjust(bottom=0.2)
        ax.axis('off')
        img_obj = ax.imshow(img_array)

        # Add button
        toggle_ax = plt.axes([0.7, 0.05, 0.2, 0.075])
        toggle_button = Button(toggle_ax, 'Toggle View')
        toggle_button.on_clicked(toggle_stats)

        plt.show(block=False)
    else:
        ax.imshow(img_array)
        fig.canvas.draw_idle()
        plt.pause(0.01)
        ax.clear()
        ax.axis('off')

def toggle_stats(event):
    global show_batter
    show_batter = not show_batter

def fade_transition(image, alpha_start=0, alpha_end=1, steps=10):
    for i in range(steps):
        alpha = alpha_start + (alpha_end - alpha_start) * (i / steps)
        faded = image.copy()
        faded.putalpha(int(alpha * 255))
        render_image(faded)
        time.sleep(0.05)

def get_todays_game(team_id):
    today = datetime.date.today().strftime('%Y-%m-%d')
    games = statsapi.schedule(team=team_id, date=today)
    return games[0] if games else None

def get_next_game(team_id):
    today = datetime.date.today()
    for offset in range(1, 30):
        future_date = (today + datetime.timedelta(days=offset)).strftime('%Y-%m-%d')
        games = statsapi.schedule(team=team_id, date=future_date)
        if games:
            return games[0]
    return None

def game_has_started(game_id):
    live_data = statsapi.get('game', {'gamePk': game_id})
    status = live_data.get('gameData', {}).get('status', {}).get('detailedState', '')
    return status == 'In Progress'

def get_game_status(game_id):
    live_data = statsapi.get('game', {'gamePk': game_id})
    return live_data.get('gameData', {}).get('status', {}).get('detailedState', '')

def get_current_batter(game_id): #find current batter
    live_data = statsapi.get('game_playByPlay', {'gamePk': game_id})
    all_plays = live_data.get('allPlays', [])
    if all_plays:
        current_play = all_plays[-1]
        batter = current_play.get('matchup', {}).get('batter', {})
        if batter:
            return {"name": batter['fullName'], "id": batter['id']}
    return None

def get_current_pitcher(game_id): # find current pitcher
    live_data = statsapi.get('game', {'gamePk': game_id})
    try:
        pitcher_data = live_data['liveData']['plays']['currentPlay']['matchup']['pitcher']
        pitcher_name = pitcher_data['fullName']
        pitcher_id = pitcher_data['id']
        return {'name': pitcher_name, 'id': pitcher_id}
    except (KeyError, TypeError):
        return None

def get_batter_stats(player_id): # find batter stats
    stats = statsapi.player_stat_data(player_id, group='hitting', type='season')
    statline = stats['stats']
    if isinstance(statline, list):
        statline = statline[0].get('stats', {})

    all_stats = statline.copy()
    displayed_stats = {
        'avg': statline.get('avg', 'N/A'),
        'hr': statline.get('homeRuns', 'N/A'),
        'ops': statline.get('ops', 'N/A'),
        'rbi': statline.get('rbi', 'N/A'),
        'hits': statline.get('hits', 'N/A'),
        'obp': statline.get('obp', 'N/A'),
    }

    excluded_keys = set(displayed_stats.keys())
    available_extra = [k for k in all_stats.keys() if k not in excluded_keys]
    random_stat_key = random.choice(available_extra) if available_extra else None
    if random_stat_key:
        displayed_stats['random_stat'] = (random_stat_key, all_stats[random_stat_key])
    else:
        displayed_stats['random_stat'] = ("", "N/A")

    return displayed_stats

def get_pitcher_stats(pitcher_id):
    try:
        player_stats = statsapi.player_stat_data(pitcher_id, group="pitching", type="season")
        stats_list = player_stats['stats']
        
        for stat_entry in stats_list:
            if stat_entry.get('type') == 'season':  # Fixed here
                stats = stat_entry.get('stats', {})

                return {
                    'ERA': stats.get('era', 'N/A'),
                    'W-L': f"{stats.get('wins', 0)}-{stats.get('losses', 0)}",
                    'IP': stats.get('inningsPitched', 'N/A'),
                    'SO': stats.get('strikeOuts', 'N/A'),
                    'WHIP': stats.get('whip', 'N/A')
                }

        return {}
    except Exception as e:
        print("Pitcher stats error:", e)
        return {}

def countdown_to_game(start_time):
    # Create static background once
    background = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 128))
    draw_bg = ImageDraw.Draw(background)

    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_time = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = ImageFont.load_default()
        font_time = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw_centered_text(draw_bg, "Game Countdown", 50, font_title)

    # Add game time below countdown
    game_time_str = start_time.strftime("%I:%M %p").lstrip("0")
    draw_centered_text(draw_bg, f"Game Time: {game_time_str}", 150, font_small)

    # Add Blue Jays logo to the bottom right corner
    try:
        logo = Image.open("bluejays_logo.png").convert("RGBA")
        try:
            resample_method = Image.Resampling.LANCZOS
        except AttributeError:
            resample_method = Image.ANTIALIAS  # Pillow < 10 fallback

        logo.thumbnail((48, 48), resample_method)
        background.paste(logo, (WIDTH - logo.width - 10, HEIGHT - logo.height - 10), logo)
    except Exception as e:
        print(f"Error loading logo: {e}")

    while True:
        now = datetime.datetime.now(start_time.tzinfo)
        time_diff = start_time - now
        if time_diff.total_seconds() <= 0:
            break

        hrs, remainder = divmod(int(time_diff.total_seconds()), 3600)
        mins, secs = divmod(remainder, 60)

        # Create overlay for countdown time
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        time_str = f"{hrs:02}:{mins:02}:{secs:02}"
        draw_centered_text(draw_overlay, time_str, 100, font_time)

        # Composite overlay on background
        frame = Image.alpha_composite(background, overlay)
        render_image(frame)

        time.sleep(1)


def render_countdown(hours, minutes, seconds):
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 128))
    draw = ImageDraw.Draw(image)

    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_time = ImageFont.truetype("arial.ttf", 36)
    except:
        font_title = ImageFont.load_default()
        font_time = ImageFont.load_default()

    draw_centered_text(draw, "Game Countdown", 50, font_title)

    time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
    draw_centered_text(draw, time_str, 100, font_time)

    fade_transition(image, alpha_start=0, alpha_end=1, steps=10)


def render_display(name, stats, team_id, pms_code):
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 128))  # Default background color
    draw = ImageDraw.Draw(image)

    # Convert PMS code to RGB
    def pms_to_rgb(pms_code):
        pms_colors = {
        # AL East
        "Baltimore Orioles": (252, 88, 0),      # Orange
        "Boston Red Sox": (186, 0, 33),         # Red
        "New York Yankees": (0, 32, 91),        # Navy Blue
        "Toronto Blue Jays": (19, 74, 142),     # UNIQUE Blue
        "Tampa Bay Rays": (9, 44, 92),          # Dark Blue


        # AL Central
        "Chicago White Sox": (39, 37, 31),      # Black
        "Cleveland Guardians": (0, 56, 93),     # Navy 
        "Detroit Tigers": (12, 35, 64),         # Navy
        "Kansas City Royals": (0, 121, 184),    # Royal Blue
        "Minnesota Twins": (179, 25, 66),       # Red


        # AL West
        "Houston Astros": (235, 110, 31 ),      # Orange 
        "Los Angeles Angels": (186, 0, 33),     # Red
        "Oakland Athletics": (0, 53, 36),       # Green
        "Seattle Mariners": (0, 92, 92),        # Teal
        "Texas Rangers": (0, 50, 120),          # Blue


        # NL East
        "Atlanta Braves": (206, 17, 65),        # Red
        "Miami Marlins": (0, 163, 224),         # Blue
        "New York Mets": (252, 88, 0),          # Orange
        "Philadelphia Phillies": (232, 24, 40), # Red
        "Washington Nationals": (171, 0, 3),    # Red


        # NL Central
        "Chicago Cubs": (14, 51, 134),          # Blue
        "Cincinnati Reds": (198, 1, 31),        # Red
        "Milwaukee Brewers": (18, 40, 75),      # Navy
        "Pittsburgh Pirates": (255, 184, 28),   # Gold
        "St. Louis Cardinals": (196, 30, 58),   #  Red


        # NL West
        "Arizona Diamondbacks": (167, 25, 48),  # Red
        "Colorado Rockies": (51, 51, 102),      # Purple
        "Los Angeles Dodgers": (0, 90, 156),    # Blue
        "San Diego Padres": (47, 36, 29),       # Brown
        "San Francisco Giants": (253, 90, 30),  # Orange
    }
        return pms_colors.get(pms_code, (0, 56, 168))  # Default to Blue Jays Blue

    # Assuming pms_code is for the opponent
    opponent_rgb = pms_to_rgb(pms_code)
    image = Image.new("RGBA", (WIDTH, HEIGHT), opponent_rgb)
    draw = ImageDraw.Draw(image)

    draw.text((10, 10), name.upper(), font=font_large, fill="LightGrey")
    draw.line((0,40, WIDTH, 40),fill="WHITE",width=2)

    draw.text((10, 50), f"AVG%: {stats['avg']}", font=font_small, fill="LightGrey")
    draw.line((0,70, WIDTH,70), fill="White", width=2)

    draw.text((10, 75), f"OPS%: {stats['ops']}", font=font_small, fill="LightGrey")
    draw.line((0,95, WIDTH,95), fill="White", width=2)

    draw.text((10, 100), f"OBP%: {stats['obp']}", font=font_small, fill="LightGrey")
    draw.line((0,120, WIDTH,120), fill="White", width=2)

    draw.text((10, 125), f"HR:  {stats['hr']}", font=font_small, fill="LightGrey")
    draw.line((0,145, WIDTH,145), fill="White", width=2)

    draw.text((10, 150), f"RBI: {stats['rbi']}", font=font_small, fill="LightGrey")
    draw.line((0,170, WIDTH,170), fill="White", width=2)

    draw.text((10, 175), f"Hits: {stats['hits']}", font=font_small, fill="LightGrey")
    draw.line((0,195, WIDTH,195), fill="White", width=2)

    key, value = stats['random_stat']
    if key:
        draw.text((10, 200), f"{key}: {value}", font=font_small, fill="LightGrey")
        draw.line((0,225, WIDTH,225), fill="White", width=2)

    fade_transition(image, alpha_start=0, alpha_end=1, steps=20)

def render_pitcher_display(pitcher_name, pitcher_stats, opponent_name,):
    # Convert PMS code to RGB
    def pms_to_rgb(pms_code):
        pms_colors = {
            "Baltimore Orioles": (252, 88, 0),      # Orange
            "Boston Red Sox": (186, 0, 33),         # Red
            "New York Yankees": (0, 32, 91),        # Navy Blue
            "Toronto Blue Jays": (19, 74, 142),     # UNIQUE Blue
            "Tampa Bay Rays": (9, 44, 92),          # Dark Blue
            "Chicago White Sox": (39, 37, 31),      # Black
            "Cleveland Guardians": (0, 56, 93),     # Navy 
            "Detroit Tigers": (12, 35, 64),         # Navy
            "Kansas City Royals": (0, 121, 184),    # Royal Blue
            "Minnesota Twins": (179, 25, 66),       # Red
            "Houston Astros": (235, 110, 31),       # Orange 
            "Los Angeles Angels": (186, 0, 33),     # Red
            "Oakland Athletics": (0, 53, 36),       # Green
            "Seattle Mariners": (0, 92, 92),        # Teal
            "Texas Rangers": (0, 50, 120),          # Blue
            "Atlanta Braves": (206, 17, 65),        # Red
            "Miami Marlins": (0, 163, 224),         # Blue
            "New York Mets": (252, 88, 0),          # Orange
            "Philadelphia Phillies": (232, 24, 40), # Red
            "Washington Nationals": (171, 0, 3),    # Red
            "Chicago Cubs": (14, 51, 134),          # Blue
            "Cincinnati Reds": (198, 1, 31),        # Red
            "Milwaukee Brewers": (18, 40, 75),      # Navy
            "Pittsburgh Pirates": (255, 184, 28),   # Gold
            "St. Louis Cardinals": (196, 30, 58),   # Red
            "Arizona Diamondbacks": (167, 25, 48),  # Red
            "Colorado Rockies": (51, 51, 102),      # Purple
            "Los Angeles Dodgers": (0, 90, 156),    # Blue
            "San Diego Padres": (47, 36, 29),       # Brown
            "San Francisco Giants": (253, 90, 30),  # Orange
        }
        return pms_colors.get(pms_code, (0, 56, 168))  # Default to Blue Jays Blue

    opponent_rgb = pms_to_rgb(opponent_name)
    image = Image.new("RGBA", (WIDTH, HEIGHT), opponent_rgb)
    draw = ImageDraw.Draw(image)

    draw.text((10, 10), pitcher_name.upper(), font=font_large, fill="LightGrey")
    draw.line((0, 40, WIDTH, 40), fill="WHITE", width=2)

    y = 50
    for stat_name in ['ERA', 'W-L', 'IP', 'SO', 'WHIP']:
        stat_value = pitcher_stats.get(stat_name, 'N/A')
        draw.text((10, y), f"{stat_name}: {stat_value}", font=font_small, fill="LightGrey")
        y += 25
        draw.line((0, y, WIDTH, y), fill="White", width=2)
        y += 5

    fade_transition(image, alpha_start=0, alpha_end=1, steps=20)

def check_toggle_button():
    global show_batter
    import msvcrt
    if msvcrt.kbhit():
        key = msvcrt.getwch().lower()
        if key == 'b':
            show_batter = True
            print("Toggled view to: Batter")
        elif key == 'p':
            show_batter = False
            print("Toggled view to: Pitcher")

def draw_centered_text(draw, text, y, font, fill="white"):
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    draw.text(((WIDTH - text_width) // 2, y), text, font=font, fill=fill)

def render_game_over_screen(score_text, next_game_info):
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 128))
    draw = ImageDraw.Draw(image)

    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_main = ImageFont.truetype("arial.ttf", 18)
    except:
        font_title = ImageFont.load_default()
        font_main = ImageFont.load_default()

    date_obj = datetime.datetime.strptime(next_game_info['date'], "%Y-%m-%d")
    pretty_date = date_obj.strftime("%B %d, %Y")

    draw_centered_text(draw, "GAME OVER", 30, font_title)
    draw_centered_text(draw, "Final Score:", 70, font_main)
    draw_centered_text(draw, score_text, 90, font_main)
    draw_centered_text(draw, "Next Game:", 125, font_main)
    draw_centered_text(draw, f"On {pretty_date}", 145, font_main)
    draw_centered_text(draw, f"@ {next_game_info['time']}", 165, font_main)
    draw_centered_text(draw, f"Against: {next_game_info['opponent']}", 185, font_main)

    fade_transition(image, alpha_start=0, alpha_end=1, steps=20)

# No game today screen 
def render_no_game_today(next_game):
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 128))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    game_time = datetime.datetime.fromisoformat(next_game['game_datetime'].replace("Z", "+00:00"))
    toronto_time = game_time.astimezone(TORONTO_TZ)
    opponent = next_game['away_name'] if next_game['home_id'] == TEAM_ID else next_game['home_name']
    date_str = toronto_time.strftime('%b %d, %Y')
    time_str = toronto_time.strftime('%I:%M %p')

    draw.text((10, 70),f"No game today", font=font, fill="LightGrey")
    draw.text((10, 100),f"Next game: {date_str}", font=font, fill="LightGrey")
    draw.text((10, 130),f"@ {time_str}", font=font, fill="LightGrey")
    draw.text((10, 160),f"Against: {opponent}", font=font, fill="LightGrey")

    fade_transition(image, alpha_start=0, alpha_end=1, steps=20)


def get_final_score(game):
    linescore = statsapi.boxscore_data(game['game_id'])
    teams = linescore['teamInfo']
    away_name = teams['away']['teamName']
    home_name = teams['home']['teamName']
    away_score = linescore['away']['teamStats']['batting']['runs']
    home_score = linescore['home']['teamStats']['batting']['runs']
    return f"{away_name} {away_score} - {home_name} {home_score}"

def update_stats_periodically():
    game = get_todays_game(TEAM_ID)
    if not game:
        print("No Blue Jays game today.")
        next_game = get_next_game(TEAM_ID)
        if next_game:
            while datetime.datetime.now().hour < 23:
                render_no_game_today(next_game)
                time.sleep(60)
        return

    game_id = game['game_id']
    game_time = datetime.datetime.fromisoformat(game['game_datetime'].replace("Z", "+00:00")).astimezone(TORONTO_TZ)

    print("Countdown to game starting...")
    countdown_to_game(game_time)

    print("\nGame started. Tracking batters...")
    current_batter_id = None
    batter_info = None  # Store the most recent batter info

    while True:
        status = get_game_status(game_id)

        if status == "Final":
            print("Game ended with status: Final")
            final_score = get_final_score(game)
            next_game = get_next_game(TEAM_ID)
            if next_game:
                next_game_time = datetime.datetime.fromisoformat(next_game['game_datetime'].replace("Z", "+00:00")).astimezone(TORONTO_TZ)
                next_game_info = {
                    'date': next_game['game_date'],
                    'time': next_game_time.strftime('%I:%M %p'),
                    'opponent': next_game['away_name'] if next_game['home_id'] == TEAM_ID else next_game['home_name']
                }
                render_game_over_screen(final_score, next_game_info)
            break

        if status != "In Progress":
            print("Waiting for the game to go into 'In Progress' status...")
            time.sleep(15)
            continue

        # Always fetch the current batter info
        new_batter = get_current_batter(game_id)
        if new_batter:
            if new_batter['id'] != current_batter_id:
                current_batter_id = new_batter['id']
            batter_info = new_batter

        opponent_name = game['away_name'] if game['home_id'] == TEAM_ID else game['home_name']

        if batter_info:
            if show_batter:
                batter_stats = get_batter_stats(current_batter_id)
                render_display(batter_info['name'], batter_stats, TEAM_ID, opponent_name)
            else:
                pitcher_info = get_current_pitcher(game_id)
                if pitcher_info:
                    pitcher_stats = get_pitcher_stats(pitcher_info['id'])
                    render_pitcher_display(pitcher_info['name'], pitcher_stats, TEAM_ID,)

        check_toggle_button()
        time.sleep(10)

if __name__ == "__main__":
    update_stats_periodically()