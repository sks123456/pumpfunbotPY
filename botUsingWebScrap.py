import asyncio
import websockets
import json
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import os

# Solana WebSocket endpoint
SOCKET_URL = "wss://api.mainnet-beta.solana.com"

# Mint Authority Public Key (this is the address of the mint authority you provided)
MINT_AUTHORITY_PUBKEY = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"

# Solana RPC endpoint for fetching transaction details
RPC_URL = "https://api.mainnet-beta.solana.com"

# Path for storing the minted token addresses
JSON_LOG_FILE = "minted_tokens_log.json"

# Initialize the JSON log file if it does not exist
def init_json_log_file():
    try:
        with open(JSON_LOG_FILE, 'r') as f:
            # Load existing logs if the file exists
            logs = json.load(f)
    except FileNotFoundError:
        # If file does not exist, initialize it with an empty list
        logs = []
        with open(JSON_LOG_FILE, 'w') as f:
            json.dump(logs, f)
    return logs

# Function to save minted token data to a JSON log file
def save_minted_token_log(data, file_path):
    # Load existing data from the log file
    logs = init_json_log_file()

    # Append new data
    logs.append(data)

    # Save the updated logs back to the file
    with open(file_path, 'w') as f:
        json.dump(logs, f, indent=4)

# Setup the Selenium WebDriver
def setup_driver():
    # Chrome options for running headlessly
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# Function to scrape Solana Explorer for mint details using Selenium
def scrape_mint_address(transaction_signature):
    """
    Scrapes the Solana Explorer for the mint address related to a specific transaction signature.
    """
    # Solana Explorer URL for the transaction
    transaction_url = f"https://explorer.solana.com/tx/{transaction_signature}?cluster=mainnet"
    
    # Setup Selenium WebDriver
    driver = setup_driver()
    driver.get(transaction_url)

    try:
        # Wait for the page to load dynamically (increase timeout if needed)
        driver.implicitly_wait(3)

        # Look for the mint address in the page content
        # Selenium will now render the dynamic JavaScript content
        instruction_data_section = driver.find_element(By.CSS_SELECTOR, "pre.json-wrap")
        instruction_data = instruction_data_section.text

        # Parse the JSON data to extract the mint address
        try:
            instruction_json = json.loads(instruction_data)
            if 'info' in instruction_json and 'mint' in instruction_json['info']:
                mint_address = instruction_json['info']['mint']
                return mint_address
        except json.JSONDecodeError:
            print(f"Error parsing JSON for transaction {transaction_signature}")
    except Exception as e:
        print(f"Error scraping mint address for {transaction_signature}: {e}")
    finally:
        # Always close the driver after scraping
        driver.quit()

    return None

# Subscribe to logs related to mint authority
async def subscribe_to_mint_authority(ws):
    """
    Subscribes to logs for the mint authority and looks for mint instructions.
    """
    subscribe_message = json.dumps({
        "jsonrpc": "2.0",
        "method": "logsSubscribe",
        "params": [
            {
                "mentions": [MINT_AUTHORITY_PUBKEY],  # We are interested in logs mentioning the mint authority
            },
            {
                "commitment": "processed"  # You can change this to "confirmed" or "finalized"
            }
        ],
        "id": 1
    })
    
    await ws.send(subscribe_message)
    print(f"Subscribed to logs for mint authority: {MINT_AUTHORITY_PUBKEY}")

# Listen for mint transactions and handle them
async def listen_for_mints():
    """
    Listens for mint transactions from the specified mint authority and extracts the minted token's public key.
    """
    async with websockets.connect(SOCKET_URL) as ws:
        await subscribe_to_mint_authority(ws)
        
        while True:
            try:
                # Listen for incoming messages (transaction logs)
                message = await ws.recv()
                data = json.loads(message)

                # Process the logs if they contain the required information
                if 'params' in data and 'result' in data['params']:
                    result = data['params']['result']
                    if 'value' in result:
                        logs = result['value'].get('logs', [])
                        signature = result['value'].get('signature', None)
                        err = result['value'].get('err', None)  # Get the 'err' field to check for errors

                        if err is None and signature:
                            for log in logs:
                                if "Program log: Create" in log:
                                    print(f"Signature: {signature}")
                                    
                                    # Scrape the transaction page for the mint address
                                    mint_address = scrape_mint_address(signature)
                                    if mint_address:
                                        print(f"Mint Address: {mint_address}")

                                        # Save the mint address and associated details to the JSON log
                                        minted_token_data = {
                                            "transaction_url": f"https://explorer.solana.com/tx/{signature}?cluster=mainnet",
                                            "mint_address": mint_address,
                                            "timestamp": time.time()  # Timestamp when the data was recorded
                                        }
                                        save_minted_token_log(minted_token_data, JSON_LOG_FILE)
                                    else:
                                        print(f"No mint address found for transaction {signature}")

            except Exception as e:
                print(f"Error receiving or processing message: {e}")
                await asyncio.sleep(1)  # Handle error and retry

# Main function to initialize the log file and start listening
async def main():
    # Initialize the JSON log file if needed
    init_json_log_file()
    
    # Start listening for mints from the mint authority
    await listen_for_mints()

# Run the script
if __name__ == "__main__":
    asyncio.run(main())
