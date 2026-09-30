import os
import re
import random 

from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = int(os.getenv("API_ID", "235218869"))
API_HASH = os.getenv("API_HASH", "80baadcfd00a39a0ff1f5f529d23156f")

# Get your token from @BotFather on Telegram.
BOT_TOKEN = os.getenv("BOT_TOKEN","")
SUDOERS = [8564072723] 

YOUTUBE_API_KEY = os.getenv("")
# OpenAI Token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Get your mongo url from cloud.mongodb.com
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb+srv://knight4563:knight4563@cluster0.a5br0se.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
MUSIC_BOT_NAME = os.getenv("MUSIC_BOT_NAME", "roohi_queen_bot")
PRIVATE_BOT_MODE = os.getenv("PRIVATE_BOT_MODE", None)

DURATION_LIMIT_MIN = int(os.getenv("DURATION_LIMIT", 100000))

# Chat id of a group for logging bot's activities
LOGGER_ID = int(os.getenv("LOGGER_ID", -1003809966719))

# Get this value from @BRANDRD_ROBOT on Telegram by /id
OWNER_ID = int(os.getenv("OWNER_ID", "8676835917"))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "8564072723").split()))

## Fill these variables if you're deploying on heroku.

FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1", "https://t.me/Roohi_Soul")
FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2", "https://t.me/Roohi_Soul_Gc")

# Your heroku app name
HEROKU_APP_NAME = os.getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = os.getenv("HEROKU_API_KEY")

UPSTREAM_REPO = os.getenv(
    "UPSTREAM_REPO",
    "https://github.com/txkuze/snowy",
)
UPSTREAM_BRANCH = os.getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = os.getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private

SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "https://t.me/Roohi_Soul")
SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/Roohi_Soul_Gc")

# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(os.getenv("AUTO_LEAVING_ASSISTANT", False))

# Auto Gcast/Broadcast Handler (True = broadcast on , False = broadcast off During Hosting, Dont Do anything here.)
AUTO_GCAST = os.getenv("AUTO_GCAST")

# Auto Broadcast Message That You Want Use In Auto Broadcast In All Groups.
AUTO_GCAST_MSG = os.getenv("AUTO_GCAST_MSG", "")

# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "6fb7e1766693439b86ec57e3deb3c36f")
SPOTIFY_CLIENT_SECRET = os.getenv(
    "SPOTIFY_CLIENT_SECRET", "da3f94c6a68d49f6b64a7216ec9eb905"
)


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
SERVER_PLAYLIST_LIMIT = int(os.getenv("SERVER_PLAYLIST_LIMIT", "1000"))
PLAYLIST_FETCH_LIMIT = int(os.getenv("PLAYLIST_FETCH_LIMIT", "1000"))

SONG_DOWNLOAD_DURATION = int(os.getenv("SONG_DOWNLOAD_DURATION_LIMIT", "180"))
SONG_DOWNLOAD_DURATION_LIMIT = int(os.getenv("SONG_DOWNLOAD_DURATION_LIMIT", "2000"))

# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(os.getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(os.getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes


# Get your pyrogram v2 session from @BRANDEDSTRINGSESSION_BOT on Telegram
STRING1 = os.getenv("STRING_SESSION","")
STRING2 = os.getenv("STRING_SESSION2", None)
STRING3 = os.getenv("STRING_SESSION3", None)
STRING4 = os.getenv("STRING_SESSION4", None)
STRING5 = os.getenv("STRING_SESSION5", None)


BANNED_USERS = filters.user()
TEMP_DB_FOLDER = "tempdb"
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}


PING_IMG_URL = os.getenv("PING_IMG_URL", "https://files.catbox.moe/nndfm5.jpg")
PLAYLIST_IMG_URL = "https://graph.org/file/3a907478d7a13ff1e8ecb-606e29f797b109ab82.jpg"
STATS_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
TELEGRAM_AUDIO_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
TELEGRAM_VIDEO_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
STREAM_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
SOUNCLOUD_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
YOUTUBE_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://graph.org/file/d22cec7c75e26f36edff7-0ce8cae0037d4aa0aa.jpg"

START_IMG_URL = os.getenv("START_IMG_URL")

if START_IMG_URL:
    START_IMG_URL = random.choice(START_IMG_URL.split(","))
else:
    START_IMG_URL = random.choice([

"https://graph.org/file/04c9167f4c5f6c7263857-06574d12f7d9e655f8.jpg",
        "https://graph.org/file/2f8e61c55d311070339c8-17b572b5c7c8ad0907.jpg",
        "https://graph.org/file/1c82daf46ac2ec57b7827-3a05aa863a378ed34a.jpg",

"https://graph.org/file/2f8e61c55d311070339c8-17b572b5c7c8ad0907.jpg",

"https://graph.org/file/1c82daf46ac2ec57b7827-3a05aa863a378ed34a.jpg",
        "https://graph.org/file/2f8e61c55d311070339c8-17b572b5c7c8ad0907.jpg"
    ])

def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))

def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))

if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
        )
