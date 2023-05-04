# File name: model_client.py
# import requests

# event = {"type": "foo"}

# response = requests.post("http://127.0.0.1:8000/slack/events/", json=event)
# french_text = response.text

# print(french_text)
import os
print(os.environ.get('ANYSCALE_SLACK_BOT_OAUTH_TOKEN'))

from slack_sdk import WebClient

ANYSCALE_SLACK_BOT_OAUTH_TOKEN = os.environ.get('ANYSCALE_SLACK_BOT_OAUTH_TOKEN')
slack_token = ANYSCALE_SLACK_BOT_OAUTH_TOKEN
print(slack_token)
client = WebClient(token=slack_token)
print(client)
user_id = "U020WC5D9Q8"
result = client.users_info(
            user=user_id)
print(result)