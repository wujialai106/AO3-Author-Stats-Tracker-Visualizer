import json
import os
import csv
from datetime import datetime
from curl_cffi import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import platform

# ==========================================
# Configuration
# ==========================================
TARGET_USERNAME = "XXX"  # Replace with your AO3 username

# Dual-engine approach: JSON for terminal increment display (+N), CSV for Pandas line charts
JSON_FILE = "ao3_history.json"
CSV_FILE = "ao3_data_log.csv"

def load_json_history():
    """Load the legacy JSON data to ensure the terminal continues displaying (+N) increments."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_json_history(data):
    """Save the current stats state back to JSON."""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def append_to_csv(data_list):
    """Append data to the CSV file. If the file is locked by Excel, print a gentle warning."""
    file_exists = os.path.exists(CSV_FILE)
    try:
        with open(CSV_FILE, "a", encoding="utf-8-sig", newline='') as f:
            fieldnames = ['Timestamp', 'Title', 'Hits', 'Kudos', 'Bookmarks', 'Comments']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
                
            for data in data_list:
                writer.writerow(data)
        return True
    except PermissionError:
        print("\n⚠️ WARNING: Cannot write to CSV! Is the file open in Excel? Please close Excel and run again.")
        return False

def parse_int(text):
    """Helper function to parse integers from text, handling commas."""
    if not text:
        return 0
    return int(text.replace(',', ''))

def get_ao3_stats(username):
    """Fetch and parse AO3 stats for the given username."""
    url = f"https://archiveofourown.org/users/{username}/works"
    # Cookies to bypass adult content warnings
    cookies = {'view_adult': 'true', 'tos_agree': 'true'}
    
    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"========== AO3 Stats Dashboard ==========")
    print(f"Generated at: {current_time_str}")
    print(f"=========================================\n")
    
    try:
        # Use impersonate="chrome110" to bypass Cloudflare protection
        response = requests.get(url, impersonate="chrome110", cookies=cookies)
    except Exception as e:
        print(f"Network connection error: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    works = soup.select('li.work.blurb')
    
    if not works:
        print("No works found. Please check your network. If AO3 servers are acting up, try again in two minutes.")
        return

    # Load history data
    history_stats = load_json_history()
    
    current_json_stats = {}
    current_csv_batch = []
    
    for work in works:
        title_tag = work.select_one('h4.heading a')
        title = title_tag.text.strip() if title_tag else "Unknown Title"
        
        hits_tag = work.select_one('dd.hits')
        kudos_tag = work.select_one('dd.kudos')
        bookmarks_tag = work.select_one('dd.bookmarks')
        comments_tag = work.select_one('dd.comments')
        
        hits = parse_int(hits_tag.text) if hits_tag else 0
        kudos = parse_int(kudos_tag.text) if kudos_tag else 0
        bookmarks = parse_int(bookmarks_tag.text) if bookmarks_tag else 0
        comments = parse_int(comments_tag.text) if comments_tag else 0
        
        # Store in dictionary (for JSON updates)
        current_json_stats[title] = {
            "hits": hits, "kudos": kudos, "bookmarks": bookmarks, "comments": comments
        }
        
        # Store in list (for appending to CSV)
        current_csv_batch.append({
            'Timestamp': current_time_str, 'Title': title,
            'Hits': hits, 'Kudos': kudos, 'Bookmarks': bookmarks, 'Comments': comments
        })
        
        # Calculate terminal increments (+N)
        hit_diff = hits - history_stats.get(title, {}).get("hits", 0)
        kudo_diff = kudos - history_stats.get(title, {}).get("kudos", 0)
        bkmk_diff = bookmarks - history_stats.get(title, {}).get("bookmarks", 0)
        
        hit_str = f"{hits} (+{hit_diff})" if hit_diff > 0 else f"{hits}"
        kudo_str = f"{kudos} (+{kudo_diff})" if kudo_diff > 0 else f"{kudos}"
        bkmk_str = f"{bookmarks} (+{bkmk_diff})" if bkmk_diff > 0 else f"{bookmarks}"
        
        print(f"《{title}》")
        print(f"  ▶ Hits: {hit_str} | Kudos: {kudo_str} | Bookmarks: {bkmk_str}")
        print("-" * 45)

    # 1. Save to JSON so the next run shows increments properly
    save_json_history(current_json_stats)
    
    # 2. Save to CSV, silently accumulating time-series data
    success = append_to_csv(current_csv_batch)
    
    print("\n✅ Live status successfully updated to JSON.")
    if success:
        print("📈 Time-series data saved to CSV! (+1 Pandas visualization material)")


# ==========================================
# Data Visualization Module
# ==========================================

# Automatically adapt to the OS to prevent Chinese label encoding issues in plots
system = platform.system()
if system == 'Windows':
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
elif system == 'Darwin': 
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC']
else:
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False 

def generate_trend_chart():
    """Generate a line chart showing the hits trend over time."""
    try:
        df = pd.read_csv("ao3_data_log.csv")
    except FileNotFoundError:
        print("Cannot find ao3_data_log.csv. Please run the scraping script first.")
        return

    # Convert text-format timestamps into actual datetime objects
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Set canvas size
    plt.figure(figsize=(12, 7))
    
    # Core magic: group by title and plot lines. If a new work appears, it draws a new line starting from its debut day!
    for title, group in df.groupby('Title'):
        plt.plot(group['Timestamp'], group['Hits'], marker='o', label=title, linewidth=2, markersize=6)
        
    plt.title('AO3 Works Traffic Trend Tracking (Total Hits)', fontsize=16, fontweight='bold')
    plt.xlabel('Timeline', fontsize=12)
    plt.ylabel('Total Hits', fontsize=12)
    
    # Place legend outside on the right to avoid blocking the beautiful trend lines
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    
    # Generate image
    plt.savefig('AO3_Hits_Trend_LineChart.png', dpi=300)
    print("✅ Long-term trend line chart generated successfully: AO3_Hits_Trend_LineChart.png")
    plt.close()

if __name__ == "__main__":
    get_ao3_stats(TARGET_USERNAME)
    generate_trend_chart()