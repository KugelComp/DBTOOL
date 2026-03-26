import requests
import json
s = requests.Session()
r = s.post('http://localhost:8000/login', data={'username':'kartik', 'password':'password'})
r2 = s.get('http://localhost:8000/my-active-jobs')
print(json.dumps(r2.json(), indent=2))
