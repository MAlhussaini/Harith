import hashlib
import requests

host = "http://192.168.100.30"
password = "opendoor"

pw_hash = hashlib.md5(password.encode()).hexdigest()

response = requests.get(f"{host}/ja", params={"pw": pw_hash}, timeout=5)
response.raise_for_status()

data = response.json()
print(data)