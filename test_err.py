import sys
import json
import urllib.request
try:
    req = urllib.request.Request('http://localhost:8000/export-status/fineract_rikalp')
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode('utf-8'))
except Exception as e:
    print(e)
