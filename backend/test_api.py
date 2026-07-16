import requests
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.myntra.com/'
}

response = requests.get('https://www.myntra.com/gateway/v2/search/nike-revolution-7', headers=headers)
print("Status:", response.status_code)
try:
    data = response.json()
    print(json.dumps(data, indent=2)[:500])
except Exception as e:
    print("Error:", e, response.text[:200])
