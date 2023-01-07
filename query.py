# File name: model_client.py
# import requests

# event = {"type": "foo"}

# response = requests.post("http://127.0.0.1:8000/slack/events/", json=event)
# french_text = response.text

# print(french_text)
import os
print(os.environ.get('SLACK_BOT_OAUTH_TOKEN'))