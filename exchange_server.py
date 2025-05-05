from flask import Flask, jsonify, request
from exchange import Market, Order

app = Flask(__name__)

market = Market()

@app.get("/")
def hello():
    return "Hello, world!"

@app.post("/add_order")
def add_order():
    payload = request.json
    id = market.add_order(Order(payload["addr"], payload["size"], payload["price"], payload["buy"]))
    if id == None:
        return jsonify({"status": "error", "msg": "insufficient balance"})
    else:
        return jsonify({"status": "success", "msg": id})

@app.post("/cancel_order")
def cancel_order():
    payload = request.json
    success = market.cancel(payload["id"])
    if not success:
        return jsonify({"status": "error"})
    else:
        return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
