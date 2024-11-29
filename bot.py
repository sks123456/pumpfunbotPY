import asyncio
import json
import base64
import websockets
import time
import struct

# Store decoded data to a file
def store_decoded_data(decoded_data, filename='decoded_data.json'):
    """Store decoded data into a JSON file."""
    try:
        # Ensure the file exists or initialize it with an empty list if it's missing or empty
        try:
            with open(filename, 'r') as f:
                all_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is empty/corrupt, initialize with an empty list
            all_data = []

        # Base64 encode the raw binary data to store it in JSON format
        base64_encoded_data = base64.b64encode(decoded_data).decode('utf-8')

        # Append the base64-encoded data to the list
        all_data.append(base64_encoded_data)

        # Save the updated data back to the file
        with open(filename, 'w') as f:
            json.dump(all_data, f, indent=4)

    except Exception as e:
        print(f"Error storing decoded data: {e}")

# Decode base64-encoded data into raw bytes
def decode_base64_data(base64_data):
    """Decode the base64 data into raw bytes (do not attempt UTF-8 decoding)."""
    try:
        # Decode base64 into raw binary data
        decoded_data = base64.b64decode(base64_data)

        # Print the first 50 bytes of the binary data for inspection
        print(f"Decoded binary data (not UTF-8): {decoded_data[:50]}...")  # Print a part of the binary data
        return decoded_data  # Return raw binary data for further inspection

    except Exception as e:
        print(f"Error decoding base64 data: {e}")
        return None

# Decode the 'create' instruction from the transaction data
def decode_create_instruction(ix_data, ix_def, accounts):
    """Decode the 'create' instruction from the transaction data."""
    args = {}
    offset = 8  # Skip 8-byte discriminator

    for arg in ix_def['args']:
        if arg['type'] == 'string':
            length = struct.unpack_from('<I', ix_data, offset)[0]
            offset += 4
            value = ix_data[offset:offset+length].decode('utf-8')
            offset += length
        elif arg['type'] == 'publicKey':
            value = base64.b64encode(ix_data[offset:offset+32]).decode('utf-8')
            offset += 32
        else:
            raise ValueError(f"Unsupported type: {arg['type']}")

        args[arg['name']] = value

    # Add account keys to args
    args['mint'] = str(accounts[0])
    args['bondingCurve'] = str(accounts[2])
    args['associatedBondingCurve'] = str(accounts[3])
    args['user'] = str(accounts[7])

    return args

# Listen for pump transactions and decode 'create' instructions
async def listen_for_pump_transactions():
    wss_endpoint = "wss://api.mainnet-beta.solana.com"
    subscription_message = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "programSubscribe",
        "params": [
            "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # pump.fun program address
            {"encoding": "jsonParsed"}  # Use jsonParsed for more readable data
        ]
    })

    try:
        async with websockets.connect(wss_endpoint, timeout=60) as websocket:
            await websocket.send(subscription_message)
            print("Subscribed to program updates for pump.fun address.")

            ping_interval = 20
            last_ping_time = time.time()

            while True:
                try:
                    current_time = time.time()
                    if current_time - last_ping_time > ping_interval:
                        await websocket.ping()
                        last_ping_time = current_time
                        print("Sending ping...")

                    response = await websocket.recv()
                    data = json.loads(response)
                    print(f"Raw response: {json.dumps(data, indent=2)}")

                    if 'method' in data and data['method'] == 'programNotification':
                        program_data = data['params']['result']
                        if 'value' in program_data:
                            account_data = program_data['value']['account']['data']
                            decoded_data = decode_base64_data(account_data[0])  # Only taking the first item in the list
                            
                            if decoded_data:
                                # Process the decoded data further (Solana instruction data parsing)
                                print(f"Decoded binary data: {decoded_data}")

                                # You can optionally process the decoded data further based on its structure.
                                # For example, decode specific Solana instructions if necessary.

                                # Store the decoded data
                                store_decoded_data(decoded_data)
                            else:
                                print("Failed to decode the base64 data.")

                    else:
                        print("No relevant update in response.")

                except websockets.exceptions.ConnectionClosed as e:
                    print(f"WebSocket connection closed: {e}. Reconnecting...")
                    break
                except Exception as e:
                    print(f"Error receiving message: {e}")

    except asyncio.TimeoutError as e:
        print(f"Connection timed out: {e}")

# Run the listener
asyncio.run(listen_for_pump_transactions())
