from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from eth_utils import keccak
import threading
import websocket
import json

app = Flask(__name__)
socketio = SocketIO(app)

price_data = {}

def encode_6_1_25_price_standard(price, timestamp):
    value = int(timestamp) * (2 ** (8 * 26))
    value += 18 * (2 ** (8 * 25))
    value += round(float(price) * (10 ** 18))
    return value

def on_message(ws, message):
    global price_data
    data = json.loads(message)
    data_key = keccak(('BINANCE:' + data['s']).encode('utf-8'))
    data_value = encode_6_1_25_price_standard(data['p'], data['T'])
    price_data[data_key] = data_value

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connection opened")

def start_ws():
    ws_url = "wss://stream.binance.com:9443/ws/ethusdt@trade"
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

@app.route('/fetch', methods=['GET'])
def get_price():
    symbol = request.args.get('key', type=str)
    if symbol is None:
        return jsonify({ "error": "Missing key argument!" })
    symbol_bytes = None
    try:
        symbol_bytes = bytes.fromhex(symbol[2:]) if symbol[0:2] == '0x' else bytes.fromhex(symbol)
    except Exception as e:
        return jsonify({ "error": str(e) })
    value = price_data.get(symbol_bytes)
    if value:
        return jsonify({ "data": "0x" + hex(value)[2:].zfill(64) })
    else:
        return jsonify({ "error": "Symbol not found" })

if __name__ == '__main__':
    ws_thread = threading.Thread(target=start_ws)
    ws_thread.daemon = True
    ws_thread.start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
