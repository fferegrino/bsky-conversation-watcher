from atproto import Client
from atproto_client.models.app.bsky.feed.defs import PostView, NotFoundPost
from datetime import datetime, timedelta
import streamlit as st
import os

client = Client()

st.set_page_config(
    page_title="Bluesky Conversation Watcher",
    page_icon="💬",
    layout="wide",
)

handle = os.getenv("HANDLE")
app_password = os.getenv("APP_PASSWORD")

client.login(handle, app_password)


st.title("Bluesky Conversation Watcher")

st.text("Do you want to know who of the people you follow are most active in replying to others?")

user_handle = st.text_input("Enter your username")
min_date = datetime.now() - timedelta(days=7)

MAX_POSTS = 100

def get_follows(handle):
    query_settings = {'actor': handle, 'limit': 100}
    follows_response = client.app.bsky.graph.get_follows(query_settings)

    follows = follows_response.follows
    query_settings['cursor'] = follows_response.cursor

    while query_settings['cursor']:
        follows_response = client.app.bsky.graph.get_follows(query_settings)
        follows.extend(follows_response.follows)
        query_settings['cursor'] = follows_response.cursor
    return follows

def get_author_feed(handle, min_date=None, max_posts=None):
    if not min_date:
        min_date = datetime.min
    if not max_posts:
        max_posts = 100
    query_settings = {'actor':handle, 'limit': 100}
    author_feed_response = client.app.bsky.feed.get_author_feed(query_settings)
    feed = author_feed_response.feed
    query_settings['cursor'] = author_feed_response.cursor
    cursor_date = None if not query_settings['cursor'] else datetime.strptime(query_settings['cursor'][:19], "%Y-%m-%dT%H:%M:%S")
    while query_settings['cursor'] and cursor_date > min_date and len(feed) < max_posts:
        author_feed_response = client.app.bsky.feed.get_author_feed(query_settings)
        feed.extend(author_feed_response.feed)
        query_settings['cursor'] = author_feed_response.cursor
        cursor_date = None if not query_settings['cursor'] else datetime.strptime(query_settings['cursor'][:19], "%Y-%m-%dT%H:%M:%S")
    return feed

def is_reply(post):
    """Check if a post is a reply to another post by a different author"""
    if post.reply is None:
        return False
    
    if isinstance(post.reply.parent, NotFoundPost):
        return True
    
    if isinstance(post.reply.parent, PostView):
        return post.reply.parent.author.handle != post.post.author.handle
    
    return False

def calculate_reply_rate(feed): 
    post_count = len(feed)
    reply_count = 0
    for idx, post in enumerate(feed):
        if is_reply(post):
            reply_count += 1
    
    return post_count, reply_count, reply_count / post_count if post_count > 0 else 0


if user_handle:
    follows = get_follows(user_handle)

    if len(follows) > 1000:
        st.error("Too many follows, please try a different user")
    else:
        follow_data = []
        progress_text = "Fetching data..."
        my_bar = st.progress(0, text=progress_text)
        progress_value = 1/len(follows)
        for idx, follow in enumerate(follows):
            my_bar.progress(progress_value * (idx + 1), text=f"Fetching {follow.handle}")
            feed = get_author_feed(follow.handle, min_date, MAX_POSTS)
            post_count, reply_count, reply_rate = calculate_reply_rate(feed)
            follow_data.append({
                'avatar': follow.avatar,
                'handle': f"https://bsky.app/profile/{follow.handle}",
                'post_count': post_count,
                'reply_count': reply_count,
                'reply_rate': reply_rate
            })

        follow_data = sorted(follow_data, key=lambda x: x['reply_rate'])
        my_bar.empty()
        
        st.dataframe(
            follow_data,
            use_container_width=True,
            height=500,
            column_config={
                "avatar": st.column_config.ImageColumn(
                    "Avatar", help="User avatar"
                ),
                "handle": st.column_config.LinkColumn(
                    "Handle", help="User handle",
                    display_text=r"https://bsky\.app/profile/([a-zA-Z\.\-_]+)"
                ),
                "post_count": st.column_config.NumberColumn(
                    "Posts", help="Number of posts"
                ),
                "reply_count": st.column_config.NumberColumn(
                    "Replies", help="Number of replies"
                ),
                "reply_rate": st.column_config.NumberColumn(
                    "Reply Rate", help="Percentage of replies to posts",
                    format="%.2f"
                )
            },
            hide_index=True
        )