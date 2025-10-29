# Author: Parth Patel
# Project: UFC Fight Predictor
# Description: Scrapes live fighter stats from ufcstats.com to predict fight outcomes.
#
# ----- WARNING: This script relies on web scraping and may break
# ----- if ufcstats.com changes its HTML structure.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import re # For cleaning text
import sys # For exiting on error

# --- 1. Web Scraping Functions ---

def get_fighter_profile_url(fighter_name):
    """
    Finds the ufcstats.com profile URL for a given fighter.
    
    --- MODIFIED: This function now correctly searches the fighter table
    --- by combining first and last name columns.
    """
    print(f"Searching for '{fighter_name}'...")
    
    # .strip() and .lower() to clean input for comparison
    search_name = fighter_name.strip().lower()
    
    # Get the first letter of the *last* name
    try:
        last_name_letter = fighter_name.split(' ')[-1][0].lower()
    except IndexError:
        print(f"Error: Invalid name '{fighter_name}'")
        return None

    # This is the URL for the A-Z list. We use page=all to get everyone on one page.
    search_url = f"http://ufcstats.com/statistics/fighters?char={last_name_letter}&page=all"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(search_url, headers=headers)
        response.raise_for_status() # Check for errors (like 404)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching fighter list: {e}")
        return None

    # Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # --- NEW LOGIC ---
    # Find the table body that contains all the fighter rows
    table_body = soup.find('tbody')
    
    if not table_body:
        print(f"Error: Could not find fighter table on page for letter '{last_name_letter}'.")
        return None
        
    rows = table_body.find_all('tr')
    
    for row in rows:
        # Find all columns in this row
        cols = row.find_all('td')
        
        # Ensure the row has enough columns (at least 2 for names)
        if len(cols) > 1:
            first_name_link = cols[0].find('a')
            last_name_link = cols[1].find('a')
            
            # Check if both name links exist
            if first_name_link and last_name_link:
                first_name = first_name_link.get_text(strip=True).lower()
                last_name = last_name_link.get_text(strip=True).lower()
                full_name = f"{first_name} {last_name}"
                
                # Compare the constructed full name with our search name
                if full_name == search_name:
                    # Found it! Return the link's URL (href)
                    # Both links point to the same profile.
                    return first_name_link.get('href')
            
    # If the loop finishes without finding a match
    print(f"Warning: Could not find profile for '{fighter_name}'.")
    return None

def get_stats_from_profile(profile_url, fighter_name):
    """
    Scrapes the individual stats from a fighter's profile page.
    """
    if profile_url is None:
        return {'Name': fighter_name, 'Wins': 0, 'Losses': 0, 'Draws': 0, 'SLpM': 0.0, 'Str_Def': 0}

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(profile_url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching profile: {e}")
        return {'Name': fighter_name, 'Wins': 0, 'Losses': 0, 'Draws': 0, 'SLpM': 0.0, 'Str_Def': 0}

    soup = BeautifulSoup(response.text, 'html.parser')

    try:
        # --- Get Record (Wins, Losses, Draws) ---
        # This is the class for the record (e.g., "Record: 27-1-0")
        record_span = soup.find('span', class_='b-content__title-record')
        record_text = record_span.get_text(strip=True).replace('Record: ', '')
        # Split the record "27-1-0" or "11-3-0 (1 NC)" into parts
        parts = record_text.split('-')
        wins = int(parts[0])
        losses = int(parts[1])
        
        # --- MODIFIED: Handle "No Contests" in record, e.g., "0 (1 NC)" ---
        # We split the 'draws' part by a space and take the first element
        draws_string = parts[2].split(' ')[0]
        draws = int(draws_string)
        # --- END MODIFICATION ---

        # --- Get Striking Stats ---
        # All stats are in <li> tags with this class
        stat_items = soup.find_all('li', class_='b-list__box-list-item')
        
        slpm = 0.0
        str_def = 0
        
        for item in stat_items:
            text = item.get_text(strip=True)
            if text.startswith('SLpM:'):
                # Get the number, e.g., "SLpM: 2.63" -> "2.63"
                slpm_text = text.split(':')[-1].strip()
                # --- MODIFIED: Check for empty stats "--" ---
                if slpm_text != '--':
                    slpm = float(slpm_text)
                # else, slpm remains 0.0
                
            elif text.startswith('Str. Def:'):
                # Get the percentage, e.g., "Str. Def: 61%" -> "61"
                str_def_text = text.split(':')[-1].strip().replace('%', '')
                # --- MODIFIED: Check for empty stats "--" ---
                if str_def_text != '--':
                    str_def = int(str_def_text)
                # else, str_def remains 0
        
        if slpm == 0.0:
            print(f"Warning: Could not parse SLpM for {fighter_name}.")
        if str_def == 0:
            print(f"Warning: Could not parse Str. Def for {fighter_name}.")

        return {
            'Name': fighter_name,
            'Wins': wins,
            'Losses': losses,
            'Draws': draws,
            'SLpM': slpm,
            'Str_Def': str_def
        }

    except Exception as e:
        print(f"Error parsing stats for {fighter_name}: {e}. Using default stats.")
        return {'Name': fighter_name, 'Wins': 0, 'Losses': 0, 'Draws': 0, 'SLpM': 0.0, 'Str_Def': 0}


# --- 2. Main Program Logic ---
def main():
    """
    Main function to run the prediction program.
    """
    print("===== Welcome to the Live UFC Fight Predictor =====")
    print("--- (Data scraped from ufcstats.com) ---\n")
    
    # --- Get user input ---
    fighter1_name = input("Enter the full name for Fighter 1: ")
    fighter2_name = input("Enter the full name for Fighter 2: ")
    print("\n--- Scraping Data (This may take a moment) ---")

    # --- Get data from the web ---
    f1_url = get_fighter_profile_url(fighter1_name)
    # Pass the original, user-typed name (cleaned up) to get_stats_from_profile
    fighter1_data = get_stats_from_profile(f1_url, fighter1_name.strip().title())
    
    f2_url = get_fighter_profile_url(fighter2_name)
    # Pass the original, user-typed name (cleaned up) to get_stats_from_profile
    fighter2_data = get_stats_from_profile(f2_url, fighter2_name.strip().title())
    print("--- Scraping Complete ---\n")

    # Use the 'Name' from the data we received
    fighter1_name = fighter1_data['Name']
    fighter2_name = fighter2_data['Name']

    # Create DataFrame for easy manipulation
    df = pd.DataFrame([fighter1_data, fighter2_data])

    # --- 3. Simple Analytics / Model ---

    # Win Rate (%)
    df['Total_Fights'] = df['Wins'] + df['Losses'] + df['Draws']
    df['Win_Rate'] = np.where(df['Total_Fights'] > 0,
                              (df['Wins'] / df['Total_Fights']) * 100,
                              0)

    # Striking Differential
    f1_slpm = df.loc[0, 'SLpM']
    f2_slpm = df.loc[1, 'SLpM']
    f1_def = df.loc[0, 'Str_Def'] / 100
    f2_def = df.loc[1, 'Str_Def'] / 100

    f1_effective_strikes = f1_slpm * (1 - f2_def)
    f2_effective_strikes = f2_slpm * (1 - f1_def)

    # Weighted Prediction Score
    f1_win_rate = df.loc[0, 'Win_Rate']
    f2_win_rate = df.loc[1, 'Win_Rate']

    total_effective_strikes = f1_effective_strikes + f2_effective_strikes
    if total_effective_strikes == 0:
        f1_strike_ratio = 0.5
        f2_strike_ratio = 0.5
    else:
        f1_strike_ratio = f1_effective_strikes / total_effective_strikes
        f2_strike_ratio = f2_effective_strikes / total_effective_strikes

    weight_win_rate = 0.6
    weight_striking = 0.4

    f1_prediction_score = (f1_win_rate * weight_win_rate) + (f1_strike_ratio * 100 * weight_striking)
    f2_prediction_score = (f2_win_rate * weight_win_rate) + (f2_strike_ratio * 100 * weight_striking)

    total_score = f1_prediction_score + f2_prediction_score
    if total_score == 0:
        f1_likelihood = 50.0
        f2_likelihood = 50.0
        predicted_winner = "It's a perfect tie!"
    else:
        f1_likelihood = round((f1_prediction_score / total_score) * 100, 2)
        f2_likelihood = round((f2_prediction_score / total_score) * 100, 2)
        predicted_winner = fighter1_name if f1_likelihood > f2_likelihood else fighter2_name


    # --- 4. Data Visualization ---
    names = [fighter1_name, fighter2_name]
    likelihoods = [f1_likelihood, f2_likelihood]
    colors = ['#FF4500', '#1E90FF']

    plt.figure(figsize=(8, 6))
    bars = plt.bar(names, likelihoods, color=colors)

    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 1, f'{yval}%', 
                 ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.ylim(0, 100)
    plt.title('UFC Fight Prediction Likelihood', fontsize=14, fontweight='bold')
    plt.ylabel('Prediction Likelihood (%)', fontsize=12)
    plt.xlabel('Fighter', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    plot_filename = "fight_prediction.png"
    plt.savefig(plot_filename)
    

    # --- 5. Summary Report ---
    print("\n================ UFC FIGHT PREDICTION REPORT ================\n")
    print_columns = ['Name', 'Wins', 'Losses', 'Draws', 'Win_Rate', 'SLpM', 'Str_Def']
    print(df[print_columns].to_string(index=False))
    print("\n-------------------------------------------------------------")
    print(f"Effective Strikes: {fighter1_name} = {f1_effective_strikes:.2f}, {fighter2_name} = {f2_effective_strikes:.2f}")
    print(f"Prediction Likelihood: {fighter1_name} = {f1_likelihood}%, {fighter2_name} = {f2_likelihood}%")
    print("-------------------------------------------------------------")
    print(f"✅ Predicted Winner: {predicted_winner}")
    print("=============================================================\n")
    print(f"Code Execution Complete. Chart saved as '{plot_filename}'.")


# This line tells Python to run the `main` function
if __name__ == "__main__":
    # Check for dependencies
    try:
        import requests
        import bs4
    except ImportError:
        print("="*50)
        print("ERROR: Missing required libraries.")
        print("Please run this command in your terminal:")
        print("pip install requests beautifulsoup4")
        print("="*50)
        sys.exit(1) # Exit the script
        
    main()



