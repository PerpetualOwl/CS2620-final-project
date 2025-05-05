import requests
from requests import Response
BASE = "http://127.0.0.1:8000"
body = {
            "addr": "fae5af82-3a13-4a83-81d1-247408f3f45e",
            "size": 2,
            "price": 100,
            "buy": True,
        }
r = requests.post(f"{BASE}/add_order", json=body)
print(r.json())

