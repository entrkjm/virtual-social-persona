import requests

client_id = "869946672551823"
client_secret = "dbc091b5bb69e02ea72d0c5388f1f1b7"
code = "AQDn8NYRAW4Ha96KkwA2jDpHSPwvrSEsDdiHynKlL0mF2HxnTyvB7BXT8Xp-RCpUFZDapStswrFfnRDHeKpkh8T8DkRbMBnyJ7kqa2I69YXh28CV_pySwPD9zExMCUJrQk4DtaBQGHrbivy2rvjmhxNwxBCEgDER9Lvan7nsyVHCPqm-3AqjJdxN2qr2vqLensT6P2tRhQNX9vZCQPqlFILENdmZ3QvzbSujmFWMXLmYtg"
# This Code came from the Token Generator button, so we MUST use its specific redirect_uri
# NOTE: This usually fails from external scripts, but worth a try since user saved settings.
redirect_uri = "https://developers.facebook.com/threads/token_generator/oauth/"

url = "https://graph.threads.net/oauth/access_token"
payload = {
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "authorization_code",
    "redirect_uri": redirect_uri,
    "code": code
}

try:
    print(f"Exchanging code for token...")
    print(f"URI used: {redirect_uri}")
    response = requests.post(url, data=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
