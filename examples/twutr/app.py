"""
Twutr Microblogging Application
"""

import re
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

from markupsafe import escape, Markup
from MicroPie import App, SessionBackend

import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorCollection
import bcrypt
from bson import Binary # the bson package that is included with pymongo


# ------------------------------------------------------------------------------
# MongoDB Configuration (using Motor)
# ------------------------------------------------------------------------------
MONGO_URI = ("YOUR URI HERE OR IMPLEMENT ENV VARS")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client["twutr"]
user_collection = db["users"]


# ------------------------------------------------------------------------------
# Utilities for Password Security
# ------------------------------------------------------------------------------
def hash_password(password: str) -> bytes:
    """
    Hashes a password using bcrypt.

    Args:
        password (str): The plaintext password.

    Returns:
        The hashed password.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)


def check_password(password: str, hashed: Binary) -> bool:
    """
    Verifies a plaintext password against the hashed version.

    Args:
        password (str): The plaintext password.
        hashed (bytes): The hashed password.

    Returns:
        True if the passwords match, False otherwise.
    """
    if isinstance(hashed, Binary):
        hashed = bytes(hashed)  # Convert Binary to bytes
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


# ------------------------------------------------------------------------------
# Custom Motor Session Backend for MongoDB Sessions
# ------------------------------------------------------------------------------
class MotorSessionBackend(SessionBackend):
    """
    Custom session backend using MongoDB via Motor for asynchronous operations.
    Stores session data with an expiration timestamp.
    """

    def __init__(self, mongo_uri: str, db_name: str, collection_name: str = "sessions") -> None:
        self.db = client[db_name]
        self.collection = self.db[collection_name]


    async def load(self, session_id: str) -> Dict[str, Any]:
        """
        Load session data from MongoDB. If expired, delete it and return an empty dict.
        """
        doc = await self.collection.find_one({"_id": session_id})
        if not doc:
            return {}
        if "expires_at" in doc and datetime.utcnow() > doc["expires_at"]:
            await self.collection.delete_one({"_id": session_id})
            return {}
        return doc.get("data", {})


    async def save(self, session_id: str, data: Dict[str, Any], timeout: int) -> None:
        """
        Save session data into MongoDB with a specific timeout.
        """
        expires_at = datetime.utcnow() + timedelta(seconds=timeout)
        await self.collection.update_one(
            {"_id": session_id},
            {"$set": {"data": data, "expires_at": expires_at}},
            upsert=True
        )


# ------------------------------------------------------------------------------
# Helper Methods for User and Message Management
# ------------------------------------------------------------------------------
async def get_user_data(username: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user data by username.
    """
    found_doc = await user_collection.find_one({'username': username})
    return found_doc if found_doc else None


async def save_user_data(username: str, data: Dict[str, Any]) -> None:
    """
    Save updated user data back to the database with upsert.
    """
    await user_collection.update_one({'username': username}, {'$set': data}, upsert=True)


def sort_messages_by_timestamp(messages: List[Tuple[str, str, str]],
                               timestamp_index: int) -> List[Tuple[str, str, str]]:
    """
    Sort a list of messages based on a timestamp field.
    """
    return sorted(
        messages,
        key=lambda x: datetime.strptime(x[timestamp_index], '%m/%d/%Y %I:%M %p'),
        reverse=True
    )


async def get_all_messages_for_user_and_following(user_id: str) -> List[Tuple[str, str, str]]:
    """
    Retrieve messages for the given user and the users they follow.
    """
    all_messages: List[Tuple[str, str, str]] = []
    user_data = await get_user_data(user_id)
    if user_data:
        for message in user_data.get('messages', []):
            all_messages.append((user_id, message[0], message[1]))
        for following in user_data.get('following', []):
            followed_user_data = await get_user_data(following)
            if followed_user_data:
                for message in followed_user_data.get('messages', []):
                    all_messages.append((following, message[0], message[1]))
    return all_messages


async def get_all_messages_from_all_users() -> List[Tuple[str, str, str]]:
    """
    Retrieve messages from every user in the database.
    """
    all_messages: List[Tuple[str, str, str]] = []
    cursor = user_collection.find({})
    async for user_data in cursor:
        if 'messages' in user_data:
            for message in user_data['messages']:
                all_messages.append((user_data['username'], message[0], message[1]))
    return all_messages


async def update_follow_relationship(current_user: str, target_username: str, follow: bool = True) -> None:
    """
    Update the follow/unfollow relationship between the current user and target user.
    """
    current_user_data = await get_user_data(current_user)
    target_user_data = await get_user_data(target_username)
    if current_user_data and target_user_data:
        if follow:
            if target_username not in current_user_data.get('following', []):
                current_user_data.setdefault('following', []).append(target_username)
            if current_user not in target_user_data.get('followers', []):
                target_user_data.setdefault('followers', []).append(current_user)
        else:
            if target_username in current_user_data.get('following', []):
                current_user_data['following'].remove(target_username)
            if current_user in target_user_data.get('followers', []):
                target_user_data['followers'].remove(current_user)
        await save_user_data(current_user, current_user_data)
        await save_user_data(target_username, target_user_data)


async def get_most_recent_messages(user_collection: AsyncIOMotorCollection, limit: int = 200) -> List[Tuple[str, str, str]]:
    """
    Retrieve the most recent messages using an aggregation pipeline.
    """
    pipeline = [
        {"$match": {"messages": {"$exists": True, "$ne": []}}},
        {"$unwind": "$messages"},
        {"$project": {
            "username": 1,
            "message_text": {"$arrayElemAt": ["$messages", 0]},
            "message_timestamp": {"$arrayElemAt": ["$messages", 1]}
        }},
        {"$sort": {"message_timestamp": -1}},
        {"$limit": limit}
    ]
    results = []
    async for doc in user_collection.aggregate(pipeline):
        results.append((doc.get("username"), doc.get("message_text"), doc.get("message_timestamp")))
    return results


def convert_custom_syntax(text: str) -> str:
    """
    Convert custom user syntax into clickable HTML links.
    """
    link_pattern = r'@((?:https?:\/\/)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\/\S*)?)'
    internal_pattern = r'@(/[\w\-/]+)'

    # Escape the text to prevent any dangerous HTML content
    escaped_text = escape(text)

    # Process the custom syntax for links
    def replace_link(match: re.Match) -> str:
        url = match.group(1)
        if not url.startswith('http'):
            url = f'http://{url}'
        return f'<a href="{url}" target="_blank">{match.group(1)}</a>'


    def replace_internal(match: re.Match) -> str:
        path = match.group(1)
        return f'<a href="{path}">{path}</a>'

    # Convert links and internal references
    escaped_text = re.sub(link_pattern, replace_link, escaped_text)
    escaped_text = re.sub(internal_pattern, replace_internal, escaped_text)

    # Return the processed text as a safe Markup object, which will render the HTML tags
    return Markup(escaped_text)


# ------------------------------------------------------------------------------
# Main Twutr Application Class
# ------------------------------------------------------------------------------
class Twutr(App):
    """
    Main application class for the Twutr microblogging application.
    """

    async def index(self) -> Any:
        """
        Shows the user's timeline, combining their messages and those from followed users.
        """
        if not self.request.session.get('logged_in'):
            return self._redirect('/public')
        user_id = self.request.session.get('user_id')
        messages = await get_all_messages_for_user_and_following(user_id)
        messages = sort_messages_by_timestamp(messages, timestamp_index=2)
        return await self._render_template('timeline.html', messages=messages, session=self.request.session)


    async def public(self) -> Any:
        """
        Displays the latest messages from all users.
        """
        messages = await get_most_recent_messages(user_collection, limit=200)
        messages = sort_messages_by_timestamp(messages, timestamp_index=2)
        return await self._render_template('public.html', messages=messages, session=self.request.session)


    async def user(self, username: str) -> Any:
        """
        Displays a specific user's messages and profile information.
        """
        logged_in = self.request.session.get('logged_in')
        current_user = self.request.session.get('user_id')
        username = escape(username)

        if not logged_in or not current_user:
            following: Optional[bool] = False
        elif current_user == username:
            following = None  # Viewing own profile.
        else:
            current_user_data = await get_user_data(current_user)
            following = username in current_user_data.get('following', [])
        user_data = await get_user_data(username)
        if user_data:
            messages = user_data.get('messages', [])
            messages = sort_messages_by_timestamp(messages, timestamp_index=1)
            followers = user_data.get('followers', [])
            following_count = len(user_data.get('following', []))
            return await self._render_template(
                'user.html',
                messages=messages,
                username=username,
                session=self.request.session,
                following=following,
                followers=followers,
                following_count=following_count
            )
        return "User not found", 404


    async def follow(self, username: str) -> Any:
        """
        Allows the current user to follow another user.
        """
        if not self.request.session.get('logged_in'):
            return self._redirect('/login')
        username = escape(username)
        current_user = self.request.session.get('user_id')
        if username == current_user:
            return "You cannot follow yourself"
        await update_follow_relationship(current_user, username, follow=True)
        return self._redirect(f'/user/{username}')


    async def unfollow(self, username: str) -> Any:
        """
        Allows the current user to unfollow another user.
        """
        if not self.request.session.get('logged_in'):
            return self._redirect('/login')
        current_user = self.request.session.get('user_id')
        await update_follow_relationship(current_user, escape(username), follow=False)
        return self._redirect(f'/user/{username}')


    async def list_followers(self, username: str) -> Any:
        """
        Displays a list of followers for a specified user.
        """
        username = escape(username)
        user_data = await get_user_data(username)
        if not user_data:
            return "User not found", 404
        followers = user_data.get('followers', [])
        return await self._render_template(
            'list_followers.html',
            username=username,
            followers=followers,
            session=self.request.session
        )


    async def list_following(self, username: str) -> Any:
        """
        Displays the list of users that a specified user is following.
        """
        username = escape(username)
        user_data = await get_user_data(username)
        if not user_data:
            return "User not found", 404
        following = user_data.get('following', [])
        return await self._render_template(
            'list_following.html',
            username=username,
            following=following,
            session=self.request.session
        )


    async def add_message(self) -> Any:
        """
        Registers a new message for the logged-in user and processes custom syntax.
        """
        if not self.request.session.get('logged_in'):
            return self._redirect('/login')
        if self.request.method == 'POST':
            message = self.request.body_params.get('message', [''])[0]
            sanitized_message = convert_custom_syntax(message)
            if not sanitized_message.strip():
                return await self._render_template(
                    'timeline.html',
                    error="Message cannot be empty",
                    session=self.request.session
                )
            time_stamp = datetime.utcnow().strftime('%m/%d/%Y %I:%M %p')
            message_tuple = (sanitized_message, time_stamp)
            user_data = await get_user_data(self.request.session.get('user_id'))
            user_data.setdefault('messages', []).append(message_tuple)
            await save_user_data(self.request.session.get('user_id'), user_data)
        return self._redirect('/')


    async def login(self) -> Any:
        """
        Handles user login, verifying credentials with hashed passwords.
        """
        if self.request.session.get('logged_in'):
            return self._redirect('/')
        if self.request.method == 'POST':
            username = escape(self.request.body_params.get('username', [''])[0].strip())
            password = escape(self.request.body_params.get('password', [''])[0].strip())
            if not username or not password:
                return await self._render_template(
                    'login.html',
                    error="Fields cannot be empty",
                    session=self.request.session
                )
            user = await get_user_data(username)
            stored_password = user.get('password', None)

            if not user or not stored_password or not check_password(password, stored_password):
                return await self._render_template(
                    'login.html',
                    error="Invalid credentials",
                    session=self.request.session
                )
            self.request.session['user_id'] = username
            self.request.session['logged_in'] = True
            return self._redirect('/')
        return await self._render_template('login.html', session=self.request.session)


    async def register(self) -> Any:
        """
        Registers a new user account with password hashing.
        """
        if self.request.session.get('logged_in'):
            return self._redirect('/')
        if self.request.method == 'POST':
            username = escape(self.request.body_params.get('username', [''])[0].strip())
            password = escape(self.request.body_params.get('password', [''])[0].strip())
            if not username or not password:
                return await self._render_template(
                    'login.html',
                    error="Fields cannot be empty",
                    session=self.request.session
                )
            existing_user = await get_user_data(username)
            if existing_user:
                return await self._render_template(
                    'register.html',
                    session=self.request.session,
                    error="Username already taken."
                )
            await user_collection.insert_one({
                'username': username,
                'password': Binary(hash_password(password)),
                'messages': [],
                'followers': [],
                'following': []
            })
            return self._redirect('/login')
        return await self._render_template('register.html', session=self.request.session)


    def logout(self) -> Any:
        """
        Logs out the current user.
        """
        if self.request.session.get('logged_in'):
            self.request.session.pop('logged_in', None)
        return self._redirect('/public')


# ------------------------------------------------------------------------------
# Application Initialization
# ------------------------------------------------------------------------------
backend = MotorSessionBackend(MONGO_URI, "twutr")
app = Twutr(session_backend=backend)
