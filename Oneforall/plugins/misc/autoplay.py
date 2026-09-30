import random
from pyrogram import enums, filters, types

from config import BANNED_USERS, lyrical
from Oneforall import YouTube, app
from Oneforall.core.mongo import mongodb
from Oneforall.utils.decorators.language import languageCB
from Oneforall.utils.inline.rich import (
    deliver_rich,
    edit_rich,
    html_to_rich_blocks,
    rich_autoplay_language_blocks,
    rich_autoplay_mood_blocks,
    update_now_playing_markup,
)

autoplaydb = mongodb.autoplay
playlistdb = mongodb.playlist
previous_tracks = {}


# Database Helpers
async def is_autoplay_on(chat_id: int) -> bool:
    mode = await autoplaydb.find_one({"chat_id": chat_id})
    if not mode:
        return False
    return mode.get("autoplay", False)


async def set_autoplay(chat_id: int, status: bool):
    await autoplaydb.update_one(
        {"chat_id": chat_id},
        {"$set": {"autoplay": status}},
        upsert=True,
    )


async def get_autoplay_mood(chat_id: int):
    mode = await autoplaydb.find_one({"chat_id": chat_id})
    if not mode:
        return {"mood": "romantic", "language": "hindi"}
    return mode.get("mood_data", {"mood": "romantic", "language": "hindi"})


async def set_autoplay_mood(chat_id: int, mood_data: dict):
    await autoplaydb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mood_data": mood_data}},
        upsert=True,
    )


@app.on_message(filters.command("songconfig") & filters.group & ~BANNED_USERS)
@languageCB
async def songconfig_command(client, message, _):
    """Command to configure autoplay with mood and language"""
    caption = (
        "<blockquote><emoji id=5895705279416241926>🎵</emoji> <u><b>AUTOPLAY CONFIGURATION</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        "<emoji id=5974235702701853774>✨</emoji> Select preferred mood for continuous stream:\n"
        "<emoji id=5409132617750555920>⚡</emoji> Bot will stream matching tracks after current song ends.</blockquote>"
    )
    blocks = rich_autoplay_mood_blocks(caption)
    await deliver_rich(client, message.chat.id, blocks)


@app.on_callback_query(filters.regex(r"^songconfig_mood:"))
@languageCB
async def handle_mood_selection(client, CallbackQuery, _):
    """Handle mood selection callback"""
    chat_id = CallbackQuery.message.chat.id

    try:
        mood = CallbackQuery.data.split(":", 1)[1]
    except Exception:
        return await CallbackQuery.answer("ɪɴᴠᴀʟɪᴅ ᴍᴏᴏᴅ sᴇʟᴇᴄᴛɪᴏɴ", show_alert=True)

    if chat_id not in lyrical:
        lyrical[chat_id] = {}

    lyrical[chat_id]["autoplay_mood"] = mood

    caption = (
        f"<blockquote><emoji id=5895705279416241926>🎵</emoji> <u><b>MOOD: {mood.upper()}</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        "<emoji id=6066395745139824604>🌐</emoji> <b>Select language preference:</b>\n"
        "Song search will be based on this language.</blockquote>"
    )
    blocks = rich_autoplay_language_blocks(caption)
    await edit_rich(CallbackQuery.message, blocks)


@app.on_callback_query(filters.regex(r"^songconfig_language:"))
@languageCB
async def handle_language_selection(client, CallbackQuery, _):
    """Handle language selection callback and auto-close menu"""
    chat_id = CallbackQuery.message.chat.id

    try:
        language = CallbackQuery.data.split(":", 1)[1]
    except Exception:
        return await CallbackQuery.answer("ɪɴᴠᴀʟɪᴅ ʟᴀɴɢᴜᴀɢᴇ sᴇʟᴇᴄᴛɪᴏɴ", show_alert=True)

    if chat_id not in lyrical:
        lyrical[chat_id] = {}

    mood = lyrical[chat_id].get("autoplay_mood", "romantic")

    await set_autoplay(chat_id, True)
    await set_autoplay_mood(
        chat_id,
        {
            "mood": mood,
            "language": language,
        },
    )

    lyrical[chat_id].pop("autoplay_mood", None)

    await CallbackQuery.answer(
        f"✅ Autoplay Enabled!\nMood: {mood.title()} | Language: {language.title()}\nQueue khatam hote hi continuous bajega!",
        show_alert=True,
    )

    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass

    try:
        await update_now_playing_markup(client, chat_id, playing=True)
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^AutoPlay"))
@languageCB
async def toggle_autoplay(client, CallbackQuery, _):
    """Toggle autoplay on/off"""
    callback_data = CallbackQuery.data.strip()

    if callback_data == "AutoPlay_reconfig":
        caption = (
            "<blockquote><emoji id=5895705279416241926>🎵</emoji> <u><b>AUTOPLAY CONFIGURATION</b></u></blockquote>\n\n"
            "<blockquote expandable>"
            "<emoji id=5974235702701853774>✨</emoji> Select your desired mood vibe below:</blockquote>"
        )
        blocks = rich_autoplay_mood_blocks(caption)
        return await edit_rich(CallbackQuery.message, blocks)

    try:
        chat_id = int(callback_data.split("|")[1])
    except Exception:
        chat_id = CallbackQuery.message.chat.id

    autoplay_status = await is_autoplay_on(chat_id)

    if autoplay_status:
        await set_autoplay(chat_id, False)
        await CallbackQuery.answer("❌ Autoplay Disabled!", show_alert=True)
        try:
            await CallbackQuery.message.delete()
        except Exception:
            pass
        try:
            await update_now_playing_markup(client, chat_id, playing=True)
        except Exception:
            pass
        return

    caption = (
        "<blockquote><emoji id=5895705279416241926>🎵</emoji> <u><b>ENABLE AUTOPLAY</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        "<emoji id=5974235702701853774>✨</emoji> Select your preferred mood:</blockquote>"
    )
    blocks = rich_autoplay_mood_blocks(caption)
    await edit_rich(CallbackQuery.message, blocks)


# Interactive Add Playlist Callback
@app.on_callback_query(filters.regex(r"^add_playlist_"))
async def add_autoplay_to_playlist(client, CallbackQuery):
    user_id = CallbackQuery.from_user.id
    raw_vid = CallbackQuery.data.replace("add_playlist_", "").strip()

    if not raw_vid:
        return await CallbackQuery.answer("Failed to identify track!", show_alert=True)

    user_pl = await playlistdb.find_one({"user_id": user_id, "videoid": raw_vid})
    if user_pl:
        return await CallbackQuery.answer("Yeh song pehle se aapki playlist me hai!", show_alert=True)

    await playlistdb.insert_one(
        {
            "user_id": user_id,
            "videoid": raw_vid,
            "added_by": CallbackQuery.from_user.first_name,
        }
    )
    await CallbackQuery.answer("✅ Song aapki personal playlist me add ho gaya!", show_alert=True)


async def get_autoplay_recommendation(chat_id: int):
    """Get unique and playable autoplay song recommendation without repeats"""
    if chat_id not in previous_tracks:
        previous_tracks[chat_id] = []

    mood_data = await get_autoplay_mood(chat_id)
    mood = "romantic"
    language = "hindi"

    if isinstance(mood_data, dict):
        mood = mood_data.get("mood", "romantic")
        language = mood_data.get("language", "hindi")

    # Diverse romantic Hindi search queries to prevent repeats
    romantic_artists = [
        "Arijit Singh", "Atif Aslam", "Armaan Malik", "Jubin Nautiyal",
        "Mohit Chauhan", "KK", "Darshan Raval", "Shaan", "Papon", "Sonu Nigam"
    ]
    random_artist = random.choice(romantic_artists)

    search_queries = [
        f"{random_artist} romantic {language} songs audio",
        f"latest {language} {mood} songs lyrical",
        f"classic {language} romantic love track",
        f"heart touching {language} love song",
        f"bollywood romantic melodies jukebox {random.randint(2015, 2024)}",
        f"best {language} slow reverb acoustic romantic songs",
        f"popular {language} {mood} hit songs",
    ]
    random.shuffle(search_queries)

    used_ids = set([x.get("vidid") for x in previous_tracks[chat_id] if x.get("vidid")])

    for query in search_queries:
        try:
            # Check if multi-search is supported, otherwise fallback to track
            results = None
            if hasattr(YouTube, "search"):
                try:
                    results = await YouTube.search(query, limit=5)
                except Exception:
                    results = None

            if results and isinstance(results, list):
                random.shuffle(results)
                for item in results:
                    t_id = item.get("id") or item.get("vidid")
                    if t_id and t_id not in used_ids:
                        used_ids.add(t_id)
                        if len(previous_tracks[chat_id]) >= 50:
                            previous_tracks[chat_id].pop(0)
                        previous_tracks[chat_id].append({"title": item.get("title"), "vidid": t_id})
                        return item, t_id

            track_data, track_id = await YouTube.track(query)
            if not track_data or not track_id:
                continue

            if track_id in used_ids:
                continue

            try:
                valid = await YouTube.exists(track_id) if hasattr(YouTube, "exists") else True
                if not valid:
                    continue
            except Exception:
                pass

            if len(previous_tracks[chat_id]) >= 50:
                previous_tracks[chat_id].pop(0)

            previous_tracks[chat_id].append(
                {
                    "title": track_data.get("title"),
                    "vidid": track_id,
                    "mood": mood,
                    "language": language,
                }
            )
            return track_data, track_id
        except Exception:
            continue

    # Fallback with safety against repetition
    fallback_queries = [
        f"Arijit Singh {mood} songs",
        f"Bollywood {mood} love songs",
        f"Tum Hi Ho {language} romantic audio",
    ]
    for fb_q in fallback_queries:
        try:
            track_data, track_id = await YouTube.track(fb_q)
            if track_data and track_id and track_id not in used_ids:
                previous_tracks[chat_id].append({"title": track_data.get("title"), "vidid": track_id})
                return track_data, track_id
        except Exception:
            pass

    return None, None
