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
        self.handle_request(req_info_json)
        return Response()

    def preprocess_message(self, message):
        # Remove markdown links (keep the plaintext only)
        # `<https://www.anyscale.com/|Anyscale>` -> `Anyscale`
        # pattern = re.compile(r"<.*\|(?P<plaintext>.+)>", re.IGNORECASE)
        # message = re.sub(pattern, lambda m: m.group(1), message)

        # Remove slack emojis :___:
        pattern = re.compile(r":.+:", re.IGNORECASE)
        message = re.sub(pattern, "", message)

        # Unwrwap bolded and italicized text _italic_ -> italic, *bold* -> bold
        # pattern = re.compile(r"\*(?P<bold>.+)\*", re.IGNORECASE)
        # message = re.sub(pattern, lambda m: m.group(1), message)
        # pattern = re.compile(r"_(?P<italic>.+)_", re.IGNORECASE)
        # message = re.sub(pattern, lambda m: m.group(1), message)

        # Remove standalone links with no label
        # pattern = re.compile(r"<http.*>")
        # message = re.sub(pattern, "", message)

        # Convert all HTML encodings to plaintext, ex: `&amp;` -> `&``
        # message = html.unescape(message)

        # Replace "+" with space
        message = re.sub("\+", " ", message)
        return message

    def generate_post_id(self, insight):    
        return hashlib.md5(
            bytes(insight["timestamp"] + insight["message"], 'utf-8')
        ).hexdigest()

    def write_to_airtable(self, insight):
        user_post = UserPost(
            ID = self.generate_post_id(insight),
            Timestamp = insight["timestamp"],
            Message = insight["message"],
            Source = insight["source"],
            Link = insight["link"]
        )
        posts = []
        posts.append(user_post)

        airtable = UserInsightsAirtable(
            api_key = AIRTABLE_API_KEY,
            raw_table_name = "Feedback from various channels"
        )
        airtable.create_or_update_rows(posts)
        return

    def handle_request(self, req_info_json):        
        # Render the modal for composing insight
        if (req_info_json["type"] == "message_action"):
            print("Responding to message_action")

            client = WebClient(token=SLACK_BOT_OAUTH_TOKEN)
            insight = {
                "link": "{msg_url}".format(msg_url = "https://anyscaleteam.slack.com/archives/" + req_info_json["channel"]["id"] + "/p" + re.sub("[^0-9]", "", req_info_json["message_ts"])),
                "source": client.users_info(user=req_info_json["message"]["user"])['user']['profile']['real_name'],
                "timestamp": req_info_json["message_ts"],
                "message": self.preprocess_message(req_info_json["message"]["text"])
            }
            print("Parsed request:")
            print(insight)

            print("Writing to Airtable")
            self.write_to_airtable(insight)

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

            # # Render a modal for edit / confirmation
            # view_data = {
            #     "token": SLACK_BOT_OAUTH_TOKEN,
            #     "trigger_id": req_info_json["trigger_id"],
            #     "view": json.dumps({
            #         "type": 'modal',
            #         "title": {
            #             "type": 'plain_text',
            #             "text": 'Log to UX dashboard'
            #         },
            #         "callback_id": 'log_insight',
            #         "submit": {
            #             "type": 'plain_text',
            #             "text": 'Submit'
            #         },
            #         "blocks": [ # Block Kit
            #             {
            #                 "type": "context",                            
            #                 "block_id": "link",
            #                 "elements": [{
            #                     "type": "mrkdwn",
            #                     "text": insight["link"]
            #                 }]
            #             },
            #             {
            #                 "type": "context",                            
            #                 "block_id": "source",
            #                 "elements": [{
            #                     "type": "mrkdwn",
            #                     "text": insight["source"]
            #                 }]
            #             },
            #             {
            #                 "type": "context",                            
            #                 "block_id": "timestamp",
            #                 "elements": [{
            #                     "type": "mrkdwn",
            #                     "text": insight["timestamp"]
            #                 }]
            #             },
            #             {
            #                 "block_id": 'message',
            #                 "type": 'input',
            #                 "element": {
            #                     "action_id": 'message_id',
            #                     "type": 'plain_text_input',
            #                     "multiline": True,
            #                     "initial_value": insight["message"]
            #                 },
            #                 "label": {
            #                     "type": 'plain_text',
            #                     "text": 'Insight'
            #                 }
            #             }
            #         ]
            #     })
            # }
            # dialog_response = requests.post('https://slack.com/api/views.open', data=view_data)
            # print("Response from view.open: " + str(dialog_response.content))
        
        # # Submit the insight and return a confirmation to the user
        # elif (req_info_json["type"] == "view_submission"):
        #     original_msg = re.sub("\+", " ", req_info_json["view"]["state"]["values"]["message"]["message_id"]["value"])
        #     # print(req_info_json)
        #     blocks = [
        #         {
        #             "type": 'section',
        #             "text": {
        #                 "type": 'mrkdwn',
        #                 "text": 'Insight submitted.'
        #             }
        #         },
        #         {
        #             "type": 'section',
        #             "text": {
        #                 "type": 'mrkdwn',
        #                 "text": original_msg
        #             }
        #         },
        #     ]
        #     confirmation = {
        #         "token": SLACK_BOT_OAUTH_TOKEN,
        #         "channel": req_info_json["user"]["id"],
        #         "blocks": json.dumps(blocks)
        #     }
        #     confirmation_response = requests.post('https://slack.com/api/chat.postMessage', data=confirmation)
        #     print("Response from chat.postMessage: " + str(confirmation_response.content))

        return Response()


        # req_info = await event.json()
        # print(parse(req_info))
        
        # return {
        #     "status": 200,
        #     "data": req_info
        # }

slack_bot = SlackBot.bind()
# ray.serve.deployment(runtime_env={"env_vars": {"SLACK_BOT_OAUTH_TOKEN": os.environ.get('SLACK_BOT_OAUTH_TOKEN')}})
