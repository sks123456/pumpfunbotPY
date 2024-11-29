import asyncio
import websockets
import json
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
from solana.rpc.api import Client
from solana.transaction import Signature

# Solana WebSocket and RPC endpoints
SOCKET_URL = "wss://api.mainnet-beta.solana.com"
RPC_URL = "https://api.mainnet-beta.solana.com"
MINT_AUTHORITY_PUBKEY = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"
JSON_LOG_FILE = "minted_tokens_log.json"

# Solana RPC Client
solana_client = Client(RPC_URL)

# Initialize JSON log file if it doesn't exist
def init_json_log_file():
    try:
        with open(JSON_LOG_FILE, 'r') as f:
            logs = json.load(f)
    except FileNotFoundError:
        logs = []
        with open(JSON_LOG_FILE, 'w') as f:
            json.dump(logs, f)
    return logs

def save_minted_token_log(data, file_path):
    logs = init_json_log_file()
    logs.append(data)
    with open(file_path, 'w') as f:
        json.dump(logs, f, indent=4)

# Get transaction details via RPC instead of Selenium
def get_mint_address_from_tx(signature):
    try:
        # Convert the string signature to a Solana Signature object
        signature_obj = Signature.from_string(signature)

        # Fetch the transaction using the correct signature format, with maxSupportedTransactionVersion
        response = solana_client.get_transaction(signature_obj).value.block_time
        print(f"response: {response.value}")
        # Check if response is in expected format and contains 'result'
        if response.result:
            transaction = response.result
            # Look for mint-related instructions in the transaction logs
            for log in transaction['meta']['logMessages']:
                if "Program log: Create" in log:
                    print(f"Transaction {signature} minted a token")
                    return transaction['transaction']['message']['instructions'][0]['data']
    except Exception as e:
        print(f"Error fetching transaction {signature}: {e}")
    return None

# WebSocket subscription to listen for mint logs
async def subscribe_to_mint_authority(ws):
    subscribe_message = json.dumps({
        "jsonrpc": "2.0",
        "method": "logsSubscribe",
        "params": [
            {"mentions": [MINT_AUTHORITY_PUBKEY]},
            {"commitment": "processed"}
        ],
        "id": 1
    })
    await ws.send(subscribe_message)
    print(f"Subscribed to logs for mint authority: {MINT_AUTHORITY_PUBKEY}")

# Listen for mint transactions and handle them
async def listen_for_mints():
    async with websockets.connect(SOCKET_URL) as ws:
        await subscribe_to_mint_authority(ws)

        while True:
            try:
                message = await ws.recv()
                data = json.loads(message)

                if 'params' in data and 'result' in data['params']:
                    result = data['params']['result']
                    if 'value' in result:
                        logs = result['value'].get('logs', [])
                        signature = result['value'].get('signature', None)
                        err = result['value'].get('err', None)

                        if err is None and signature:
                            for log in logs:
                                if "Program log: Create" in log:
                                    mint_address = await asyncio.to_thread(get_mint_address_from_tx, signature)
                                    if mint_address:
                                        minted_token_data = {
                                            "transaction_url": f"https://explorer.solana.com/tx/{signature}?cluster=mainnet",
                                            "mint_address": mint_address,
                                            "timestamp": time.time()
                                        }
                                        save_minted_token_log(minted_token_data, JSON_LOG_FILE)
                                    else:
                                        print(f"No mint address found for transaction {signature}")

            except Exception as e:
                print(f"Error receiving or processing message: {e}")
                await asyncio.sleep(1)

# Main function to initialize and start the listener
async def main():
    init_json_log_file()
    await listen_for_mints()

# Run the script
if __name__ == "__main__":
    asyncio.run(main())
