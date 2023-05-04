from datetime import datetime
import os
import pandas as pd
# from model_based.qa import get_qa_model, ask
from pyairtable import Table
from pyairtable.formulas import match, EQUAL, LOWER, FIELD, STR_VALUE, OR, FIND
import pydantic
from pydantic import BaseModel
from typing import List, Optional


JSONABLE_TYPES = (dict, list, tuple, str, int, float, bool, type(None))

def to_jsonable_dict(obj):
    if isinstance(obj, dict):
        return {key: to_jsonable_dict(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [to_jsonable_dict(value) for value in obj]
    elif isinstance(obj, tuple):
        return tuple(to_jsonable_dict(value) for value in obj)
    elif isinstance(obj, JSONABLE_TYPES):
        return obj
    return pydantic.json.pydantic_encoder(obj)


class UserPost(BaseModel):
    ID: str
    # name: str  # Name of user (if individual) or company
    Timestamp: datetime
    Message: str  # Raw slack message
    Source: str  # Slack username of person who posted this message
    Link: str # Link to the original Slack message
    Created_by: str
    

# class UserMetadata(BaseModel):
#     name: str
#     first_contact_timestamp: datetime
#     latest_contact_timestamp: datetime
#     industry: Optional[str] = None


class UserInsightsAirtable:
    def __init__(self, api_key: Optional[str] = None, raw_table_name = "none"):
        # User Insights Text Mining Base ID
        # self.base_id = "appsUIEv4mHYrFtZ8" # The deprecated base
        self.base_id = "appRtu1F3kQOLUxIA" # The latest UX dashboard

        self.api_key = api_key
        if not api_key:
            self.api_key = os.environ.get("AIRTABLE_API_KEY", None)
            assert self.api_key, (
                "Must provide `api_key` through constructor or as an"
                "environment variable called `AIRTABLE_API_KEY`"
            )

        self.data_table: Table = Table(self.api_key, self.base_id, raw_table_name)
        # self.metadata_table: Table = Table(self.api_key, self.base_id, metadata_table_name)

    def to_user_posts(self, posts: List[dict]):
        return [UserPost(**post["fields"]) for post in posts]

    def get_posts(self, group_key = None, group_val: Optional[str] = None, exact_match=True):
        formula = None
        if group_key and group_val:
            match_str = group_val.lower()
            if exact_match:
                formula = EQUAL(LOWER(FIELD(group_key)), STR_VALUE(match_str))
            else:
                formula = FIND(STR_VALUE(match_str), LOWER(FIELD(group_key))) + "> 0"
        posts = self.data_table.all(formula=formula)
        return self.to_user_posts(posts)

    def create_row(self, post: UserPost):
        self.data_table.create(to_jsonable_dict(post.dict()))

    def create_or_update_rows(self, posts: List[UserPost]):
        # Try matching existing ID's with ones that we're trying to upload
        post_ids = [post.ID for post in posts]
        formulae = [EQUAL(FIELD("ID"), STR_VALUE(post_id)) for post_id in post_ids]
        formula = OR(*formulae)
        existing_posts = self.data_table.all(formula=formula)
        # Map [unique post ID] -> [airtable entry reference ID]
        
      

        existing_post_ids = {
            post["fields"]["ID"]: post["id"] # post["id"] is the Airtable record ID, post["fields"]["ID"] is the Slack message ID (hashed)
            for post in existing_posts
        }

        print(existing_post_ids)

        posts_to_create = [
            to_jsonable_dict(post.dict()) for post in posts
            if post.ID not in existing_post_ids
        ]
        print(f"Creating {len(posts_to_create)} posts")
        self.data_table.batch_create(posts_to_create, typecast=True)

        return len(posts_to_create)

        # Update existing entries rather than creating a new row
        # posts_to_update = [
        #     {"ID": existing_post_ids[post.ID], "fields": to_jsonable_dict(post.dict())}
        #     for post in posts
        #     if post.ID in existing_post_ids
        # ]
        # print(f"Updating {len(posts_to_update)} posts, Creating {len(posts_to_create)} posts")
        # self.data_table.batch_update(posts_to_update, typecast=True)