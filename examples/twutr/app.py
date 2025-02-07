"""
    twutr, a really basic Twitter clone. "Instead of tweets, just utr."
    Built with MicroPie and KenobiDB.
    Written by Harrison Erd as an example application using MicroPie.
    https://patx.github.io/
"""
from datetime import datetime
import re
import os

from MicroPie import App
from kenobi import KenobiDB
from markupsafe import escape


# Database configuration
DB_PATH = 'minitwit.db'

# Set up database, we are using KenobiDB
db = KenobiDB(DB_PATH)

# ----------------
#  HELPER METHODS
# ----------------

def get_user_data(username):
    """Retrieve user data from the database by username."""
    results = db.search('username', username)
    return results[0] if results else None

def save_user_data(username, data):
    """Save updated user data back to the database."""
    user = get_user_data(username)
    if user:
        db.update('username', username, data)
    else:
        db.insert(data)

def sort_messages_by_timestamp(messages, timestamp_index):
    """
    Sort a list of messages (tuples) by a timestamp field located
    at the specified index in each tuple. The timestamp format
    is '%m/%d/%Y %I:%M %p'.
    """
    return sorted(
        messages,
        key=lambda x: datetime.strptime(x[timestamp_index], '%m/%d/%Y %I:%M %p'),
        reverse=True
    )

def get_all_messages_for_user_and_following(user_id):
    """
    Retrieve all messages from the specified user and from
    any users they are following. Returns a list of tuples:
    (username, message, timestamp).
    """
    all_messages = []
    user_data = get_user_data(user_id)

    if user_data:
        # User's own messages
        for message in user_data.get('messages', []):
            all_messages.append((user_id, message[0], message[1]))

        # Followed users' messages
        for following in user_data.get('following', []):
            followed_user_data = get_user_data(following)
            if followed_user_data:
                for message in followed_user_data.get('messages', []):
                    all_messages.append((following, message[0], message[1]))
    return all_messages

def get_all_messages_from_all_users():
    """
    Retrieve messages from every user in the database.
    Returns a list of tuples: (username, message, timestamp).
    """
    all_messages = []
    for user in db.all():
        user_data = user
        if user_data and 'messages' in user_data:
            for message in user_data['messages']:
                all_messages.append((user_data['username'], message[0], message[1]))
    return all_messages

def update_follow_relationship(current_user, username, follow=True):
    """
    Handle following or unfollowing logic between current_user and username.
    If follow=True, current_user follows username; if follow=False, unfollows.
    """
    current_user_data = get_user_data(current_user)
    target_user_data = get_user_data(username)

    if current_user_data and target_user_data:
        if follow:
            # Add username to following if not present
            if username not in current_user_data['following']:
                current_user_data['following'].append(username)
            # Add current_user to the target's followers if not present
            if current_user not in target_user_data['followers']:
                target_user_data['followers'].append(current_user)
        else:
            # Remove username from following if present
            if username in current_user_data['following']:
                current_user_data['following'].remove(username)
            # Remove current_user from the target's followers if present
            if current_user in target_user_data['followers']:
                target_user_data['followers'].remove(current_user)

        save_user_data(current_user, current_user_data)
        save_user_data(username, target_user_data)

def convert_custom_syntax(text):
    """
    Convert @link.com, @https://link.com/page to clickable links,
    and @/user/name to internal site links.
    """
    # Regex patterns
    link_pattern = r'@((?:https?:\/\/)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\/\S*)?)'  # External links
    internal_pattern = r'@(/[\w\-/]+)'  # Internal site links (e.g., @/user/name)

    # Escape the entire input first to avoid XSS
    escaped_text = escape(text)

    # Convert @link.com, @https://link.com/page to clickable links
    def replace_link(match):
        url = match.group(1)
        if not url.startswith('http'):
            url = f'http://{url}'
        return f'<a href="{url}" target="_blank">@{match.group(1)}</a>'

    # Convert @/user/name to internal links
    def replace_internal(match):
        path = match.group(1)
        return f'<a href="{path}">@{path}</a>'

    # Apply replacements
    escaped_text = re.sub(link_pattern, replace_link, escaped_text)
    escaped_text = re.sub(internal_pattern, replace_internal, escaped_text)

    return escaped_text


#-----------------
# MAIN APPLICATION
# ----------------


class Twutr(App):
    """
    Main application class for handling routes.
    The helper functions above are outside the class,
    so MicroPie does not treat them as routes.
    """

    async def index(self):
        """Shows the user's timeline (the messages of people they follow, including their own)."""
        if not self.request.session.get('logged_in'):
            return self._redirect('/public')

        user_id = self.request.session.get('user_id')
        all_messages = get_all_messages_for_user_and_following(user_id)
        all_messages = sort_messages_by_timestamp(all_messages, timestamp_index=2)

        return await self._render_template('timeline.html', messages=all_messages, session=self.request.session)

    async def public(self):
        """Displays the latest messages of all users with usernames."""
        all_messages = get_all_messages_from_all_users()
        all_messages = sort_messages_by_timestamp(all_messages, timestamp_index=2)

        return await self._render_template('public.html', messages=all_messages, session=self.request.session)

    async def user(self, username):
        """Displays a specific user's messages."""
        logged_in = self.request.session.get('logged_in')
        current_user = self.request.session.get('user_id')
        username = escape(username)

        # Determine if current_user is following, is the same user, or is not logged in
        if not logged_in or not current_user:
            following = False
        elif current_user == username:
            following = None  # Viewing own profile
        else:
            current_user_data = get_user_data(current_user)
            following = username in current_user_data.get('following', [])

        user_data = get_user_data(username)
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

    def follow(self, username):
        """Follow another user."""
        if not self.request.session.get('logged_in'):
            return self._redirect('/login')

        username = escape(username)
        current_user = self.request.session.get('user_id')

        if username == current_user:
            return "You cannot follow yourself"

        update_follow_relationship(current_user, username, follow=True)
        return self._redirect(f'/user/{username}')

    def unfollow(self, username):
        """Unfollow another user."""
        if not self.request.session.get('logged_in'):
            return self._redirect('/login')

        current_user = self.request.session.get('user_id')
        update_follow_relationship(current_user, escape(username), follow=False)

        return self._redirect(f'/user/{username}')

    async def list_followers(self, username):
        """Displays the list of followers for a given user."""
        username = escape(username)
        user_data = get_user_data(username)
        if not user_data:
            return "User not found", 404

        followers = user_data.get('followers', [])
        return await self._render_template(
            'list_followers.html',
            username=username,
            followers=followers,
            session=self.request.session
        )

    async def list_following(self, username):
        """Displays the list of users that a given user is following."""
        username = escape(username)
        user_data = get_user_data(username)
        if not user_data:
            return "User not found", 404

        following = user_data.get('following', [])
        return await self._render_template(
            'list_following.html',
            username=username,
            following=following,
            session=self.request.session
        )

    def add_message(self):
        """Registers a new message for the logged-in user with custom link and mention handling."""
        if not self.request.session.get('logged_in'):
            return self._redirect('/login')

        if self.request.method == 'POST':
            message = self.request.body_params.get('message', [''])[0]

            # Convert @link syntax and escape everything else
            sanitized_message = convert_custom_syntax(message)

            # Prevent empty message submissions
            if not sanitized_message.strip():
                return self._render_template('timeline.html', error="Message cannot be empty", session=self.request.session)

            time_stamp = str(datetime.utcnow().strftime('%m/%d/%Y %I:%M %p'))
            message_tuple = (sanitized_message, time_stamp)

            user_data = get_user_data(self.request.session.get('user_id'))
            user_data['messages'].append(message_tuple)
            save_user_data(self.request.session.get('user_id'), user_data)

        return self._redirect('/')

    async def login(self):
        """Logs the user in."""
        if self.request.session.get('logged_in'):
            return self._redirect('/')

        if self.request.method == 'POST':
            username = escape(self.request.body_params.get('username', [''])[0].strip())
            password = escape(self.request.body_params.get('password', [''])[0].strip())

            if not username or not password:
                return await self._render_template('login.html', error="Fields cannot be empty", session=self.request.session)

            user = get_user_data(username)
            if not user or user['password'] != password:
                return await self._render_template('login.html', error="Invalid credentials", session=self.request.session)

            self.request.session['user_id'] = username
            self.request.session['logged_in'] = True
            return self._redirect('/')

        return await self._render_template('login.html', session=self.request.session)

    async def register(self):
        """Registers a new user."""
        if self.request.session.get('logged_in'):
            return self._redirect('/')

        if self.request.method == 'POST':
            username = escape(self.request.body_params.get('username', [''])[0].strip())
            password = escape(self.request.body_params.get('password', [''])[0].strip())

            if not username or not password:
                return await self._render_template('login.html', error="Fields cannot be empty", session=self.request.session)
            if get_user_data(username):
                return await self._render_template('register.html', session=self.request.session, error="Username already taken.")

            db.insert({
                'username': username,
                'password': password,
                'messages': [],
                'followers': [],
                'following': []
            })
            return self._redirect('/login')

        return await self._render_template('register.html', session=self.request.session)

    def logout(self):
        """Logs the user out."""
        if self.request.session.get('logged_in'):
            self.request.session.clear()
        return self._redirect('/public')


app = Twutr()

if __name__ == '__main__':
    app.run()
