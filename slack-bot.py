import ray
from ray import serve
from fastapi import FastAPI, Request, Body, Response
import json
from urllib.parse import unquote
import re
import requests
import os
from slack_sdk import WebClient
from airtable import UserInsightsAirtable, UserPost
import hashlib
import html

app = FastAPI()

print("Initializing slack-bot service")
SLACK_BOT_OAUTH_TOKEN = os.environ.get('SLACK_BOT_OAUTH_TOKEN')
AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
NGROK_AUTH_TOKEN = os.environ.get('NGROK_AUTH_TOKEN')

def get_user_real_name(client, user_id):
    # Fetch the user's real name if not yet in the record
    return client.users_info(
            user=user_id)['user']['profile']['real_name']

def preprocess_message(slack_client, message):        
    # Replace user id with real name
    user_ids = re.findall("(?<=\<@)[A-Z0-9]+(?=\>)", message)
    if len(user_ids) > 0:
        for user_id in user_ids:
            real_name = get_user_real_name(slack_client, user_id)
            message = re.sub("<@" + user_id + ">", real_name, message)

    # Remove slack emojis :___:
    pattern = re.compile(r":.+:", re.IGNORECASE)
    message = re.sub(pattern, "", message)
    
    # Replace "+" with space
    message = re.sub("\+", " ", message)
    return message

def generate_post_id(insight):
    return hashlib.md5(
        bytes(insight["timestamp"] + insight["message"], 'utf-8')
    ).hexdigest()
    
def write_to_airtable(insight):
    user_post = UserPost(
        ID = generate_post_id(insight),
        Timestamp = insight["timestamp"],
        Message = insight["message"],
        Source = insight["source"],
        Link = insight["link"],
        Created_by = insight["created_by"]
    )
    posts = []
    posts.append(user_post)

    airtable = UserInsightsAirtable(
        api_key = AIRTABLE_API_KEY,
        raw_table_name = "Feedback from various channels"
    )
    airtable.create_or_update_rows(posts)
    return

@ray.remote
def handle_request(req_info_json):
    # Render the modal for composing insight
    if (req_info_json["type"] == "message_action"):
        print("Responding to message_action")

        client = WebClient(token=SLACK_BOT_OAUTH_TOKEN)
        
        insight = {
            "link": "{msg_url}".format(msg_url = "https://anyscaleteam.slack.com/archives/" + req_info_json["channel"]["id"] + "/p" + re.sub("[^0-9]", "", req_info_json["message_ts"])),
            "source": get_user_real_name(client, req_info_json["message"]["user"]),
            "timestamp": req_info_json["message_ts"],
            "message": preprocess_message(client, req_info_json["message"]["text"]),
            "created_by": get_user_real_name(client, req_info_json["user"]["id"])
        }
        print("Parsed request:")
        print(insight)

        print("Writing to Airtable")
        write_to_airtable(insight)

        print("Sending confirmation back to the user")
        blocks = [
            {
                "type": 'section',
                "text": {
                    "type": 'mrkdwn',
                    "text": '*Insight submitted.*'
                }
            },
            {
                "type": 'section',
                "text": {
                    "type": 'mrkdwn',
                    "text": "From {user_name}: <{link}|original message>".format(user_name = insight["source"], link = insight["link"])
                }
            },
            {
                "type": 'section',
                "text": {
                    "type": 'mrkdwn',
                    "text": insight["message"]
                }
            },
        ]
        confirmation = {
            "token": SLACK_BOT_OAUTH_TOKEN,
            "channel": req_info_json["user"]["id"],
            "blocks": json.dumps(blocks)
        }
        confirmation_response = requests.post('https://slack.com/api/chat.postMessage', data=confirmation)
        print("Response from chat.postMessage: " + str(confirmation_response.content))

    return Response()

@serve.deployment
@serve.ingress(app)
class SlackBot:

    @app.get("/healthcheck")
    def healthcheck(self):
        return

    @app.post("/slack/events")
    async def on_event(self, event: Request):
        req_info = await event.body()
        req_info_json = json.loads(re.sub("payload=", "", unquote(req_info)))
        print("Received request")
        handle_request.remote(req_info_json)
        return Response()





from pyngrok import ngrok
ngrok.set_auth_token(NGROK_AUTH_TOKEN)
ngrok_tunnel = ngrok.connect(8000, bind_tls=True)
print(ngrok_tunnel.public_url)

slack_bot = SlackBot.bind()
