import os
import requests

GIST_ID = "3e8733471d5aee9429902b8c64c26764"
GIST_TOKEN = "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"

headers = {
    "Authorization": f"Bearer {GIST_TOKEN}",
    "Accept": "application/vnd.github+json"
}

url = f"https://api.github.com/gists/{GIST_ID}"
response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())
