import schedule
import time
from datetime import datetime
from utils import make_driver, scrape_games

def run_script():
    # Clear the countdown line
    print("\nRunning script...".ljust(50))
    driver = make_driver(True)
    scrape_games(driver, month=9, day=20, year=2024)
    driver.quit()
    print("Script completed.".ljust(50))

# Schedule the task to run every hour
schedule.every(1).hours.do(run_script)

# Keep the script running
while True:
    # Get the current time and the next run time
    now = datetime.now()
    next_run = schedule.next_run()
    
    # Calculate time remaining only if next_run is in the future
    time_remaining = (next_run - now).total_seconds()
    if time_remaining > 0:
        hours, remainder = divmod(time_remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"Time until next run: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds".ljust(50), end="\r")
    else:
        print("Waiting for the next interval...".ljust(50), end="\r")

    # Run any pending scheduled tasks
    schedule.run_pending()
    
    # Small delay to prevent excessive CPU usage
    time.sleep(1)
