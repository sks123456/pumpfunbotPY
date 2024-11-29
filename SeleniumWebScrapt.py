from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager  # Automatic chromedriver management
from bs4 import BeautifulSoup
import time
import json
import os

# Setup WebDriver using webdriver-manager to automatically handle chromedriver version
service = Service(ChromeDriverManager().install())

# Initialize the Chrome WebDriver
driver = webdriver.Chrome(service=service)

# Open the Solana Explorer transaction page
transaction_url = "https://explorer.solana.com/tx/4JzAhA3VPiwfhPWeEyogxRi6vEd39VyvUKampQQ16XX7XMGZSfsYK1fiHMdnqHuAdPWdmLr9vCnhg9xzgyWQ1yA9#ix-4"
driver.get(transaction_url)

# Wait for the page to load and JavaScript to render (adjust the time as needed)
time.sleep(3)  # Make sure the page content is fully loaded

# Get the page content
soup = BeautifulSoup(driver.page_source, 'html.parser')

# Find the 'Instruction Data' section containing the mint address
instruction_data_section = soup.find('pre', class_='d-inline-block text-start json-wrap')

# If the instruction data section exists, try to parse the mint address
mint_address = None
if instruction_data_section:
    # Extract the text (JSON) from the <pre> tag
    instruction_data = instruction_data_section.get_text()

    try:
        # Parse the JSON data
        instruction_json = json.loads(instruction_data)

        # Extract the mint address from the JSON structure
        if 'info' in instruction_json and 'mint' in instruction_json['info']:
            mint_address = instruction_json['info']['mint']
    except json.JSONDecodeError:
        print("Failed to parse JSON.")

# Print the extracted mint address
if mint_address:
    print("Mint Address:", mint_address)
else:
    print("Mint address not found.")

# Quit the browser after scraping
driver.quit()

# Define the path for the log file
log_file_path = "minted_tokens_log.json"

# Prepare the data to be stored
minted_token_data = {
    "transaction_url": transaction_url,
    "mint_address": mint_address,
    "timestamp": time.time()  # Timestamp when the data was recorded
}

# Function to save the minted token log
def save_minted_token_log(data, file_path):
    # Check if the file exists
    if os.path.exists(file_path):
        # Open the existing file and load its contents
        with open(file_path, 'r') as file:
            existing_data = json.load(file)
    else:
        # If file doesn't exist, initialize an empty list
        existing_data = []

    # Append the new minted token data to the list
    existing_data.append(data)

    # Save the updated data back to the file
    with open(file_path, 'w') as file:
        json.dump(existing_data, file, indent=4)

# Save the minted token data to the log file
save_minted_token_log(minted_token_data, log_file_path)
