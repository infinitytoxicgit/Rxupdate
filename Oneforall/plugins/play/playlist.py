import asyncio
import math
import os
import time
from random import randint
from time import time
from typing import Dict, List, Union

import requests
from pyrogram import enums, filters, types
from pyrogram.types import Message
from youtube_search import YoutubeSearch

from config import BANNED_USERS, SERVER_PLAYLIST_LIMIT
from Oneforall import Carbon, app
from Oneforall.core.mongo import mongodb
from Oneforall.misc import db
from Oneforall.utils.database import add_active_video_chat, get_lang, remove_active_video_chat
from Oneforall.utils.decorators.language import language, languageCB
from Oneforall.utils.inline.playlist import (
    botplaylist_markup,
    get_playlist_markup,
    warning_markup,
)
from Oneforall.utils.inline.rich import (
    deliver_rich,
    edit_rich,
    html_to_rich_blocks,
    rich_autoplay_mood_blocks,
)
from Oneforall.utils.pastebin import HottyBin
from Oneforall.utils.stream.stream import stream
from strings import get_string

playlistdb = mongodb.playlist
user_last_message_time = {}
user_command_count = {}
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5

ADDPLAYLIST_COMMAND = "addplaylist"
PLAYLIST_COMMAND = "playlist"
DELETEPLAYLIST_COMMAND = "delplaylist"
DELETE_ALL_PLAYLIST_COMMAND = "delallplaylist"

PAGE_SIZE = 7


async def _lang(chat_id):
    return get_string(await get_lang(chat_id))


async def _get_playlists(chat_id: int) -> Dict[str, dict]:
    _notes = await playlistdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes.get("notes", {})


async def get_playlist_names(chat_id: int) -> List[str]:
    notes = await _get_playlists(chat_id)
    return list(notes.keys())


async def get_playlist(chat_id: int, name: str) -> Union[bool, dict]:
    _notes = await _get_playlists(chat_id)
    return _notes.get(name, False)


async def save_playlist(chat_id: int, name: str, note: dict):
    _notes = await _get_playlists(chat_id)
    _notes[name] = note
    await playlistdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_playlist(chat_id: int, name: str) -> bool:
    notesd = await _get_playlists(chat_id)
    if name in notesd:
        del notesd[name]
        await playlistdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def get_rich_del_page(user_id: int, page: int = 0):
    all_tracks = await get_playlist_names(user_id)
    total_tracks = len(all_tracks)
    if total_tracks == 0:
        return [], 0, 0

    total_pages = math.ceil(total_tracks / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_batch = all_tracks[start:end]

    blocks = []
    for x in current_batch:
        _note = await get_playlist(user_id, x)
        title = _note["title"].title() if (_note and isinstance(_note, dict) and "title" in _note) else str(x)
        blocks.append(
            types.InputRichBlockButtons(
                buttons=[
                    types.RichMessageButton(
                        text=f"🗑️ {title[:28]}",
                        style=enums.ButtonStyle.PRIMARY,
                        callback_data=f"del_track|{page}|{x}",
                    )
                ]
            )
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.RichMessageButton(
                text="⬅️ Back",
                style=enums.ButtonStyle.DEFAULT,
                callback_data=f"del_page|{page - 1}",
            )
        )
    nav_buttons.append(
        types.RichMessageButton(
            text=f"📄 {page + 1}/{total_pages}",
            style=enums.ButtonStyle.DEFAULT,
            callback_data="del_page_indicator",
        )
    )
    if page < total_pages - 1:
        nav_buttons.append(
            types.RichMessageButton(
                text="Next ➡️",
                style=enums.ButtonStyle.DEFAULT,
                callback_data=f"del_page|{page + 1}",
            )
        )
    blocks.append(types.InputRichBlockButtons(buttons=nav_buttons))

    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="⚠️ Delete All",
                    style=enums.ButtonStyle.DANGER,
                    callback_data="delete_warning",
                ),
                types.RichMessageButton(
                    text="✖ Close",
                    style=enums.ButtonStyle.DANGER,
                    callback_data="close",
                ),
            ]
        )
    )
    return blocks, total_tracks, total_pages


@app.on_message(filters.command(PLAYLIST_COMMAND) & ~BANNED_USERS)
@language
async def check_playlist(client, message: Message, _):
    user_id = message.from_user.id
    current_time = time()
    last_message_time = user_last_message_time.get(user_id, 0)

    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            hu = await message.reply_text(
                f"**{message.from_user.mention} ᴘʟᴇᴀsᴇ ᴅᴏɴᴛ ᴅᴏ sᴘᴀᴍ, ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 5 sᴇᴄ**"
            )
            await asyncio.sleep(3)
            await hu.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    _playlist = await get_playlist_names(message.from_user.id)
    if not _playlist:
        return await message.reply_text(_["playlist_3"])

    caption = (
        "<blockquote><emoji id=5895705279416241926>📑</emoji> <u><b>YOUR SAVED PLAYLIST</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        f"<emoji id=6066395745139824604>👤</emoji> <b>User :</b> {message.from_user.mention}\n"
        f"📊 <b>Total Saved :</b> <code>{len(_playlist)} tracks</code>\n\n"
        "<emoji id=5409132617750555920>⚡</emoji> Choose an option below to stream directly:</blockquote>"
    )
    blocks = html_to_rich_blocks(caption)

    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="🎧 Audio",
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data=f"stream_user_plist|a|{user_id}",
                ),
                types.RichMessageButton(
                    text="🎬 Video",
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data=f"stream_user_plist|v|{user_id}",
                ),
            ]
        )
    )
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="✖ Close",
                    style=enums.ButtonStyle.DANGER,
                    callback_data="close",
                )
            ]
        )
    )
    await deliver_rich(client, message.chat.id, blocks)


# Stream Whole Playlist (Audio or Video) directly on tap
@app.on_callback_query(filters.regex(r"^stream_user_plist\|") & ~BANNED_USERS)
async def stream_user_playlist_callback(client, CallbackQuery):
    parts = CallbackQuery.data.split("|")
    mode = parts[1]
    target_user_id = int(parts[2])

    notes = await _get_playlists(target_user_id)
    if not notes:
        return await CallbackQuery.answer("❌ Playlist is empty!", show_alert=True)

    chat_id = CallbackQuery.message.chat.id
    user_name = CallbackQuery.from_user.first_name or "User"

    try:
        await CallbackQuery.answer("▶️ Starting Playlist Stream...", show_alert=False)
    except Exception:
        pass

    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass

    # Ensure explicit video boolean and sync active video db state
    is_video = True if mode == "v" else None
    if is_video:
        await add_active_video_chat(chat_id)
    else:
        await remove_active_video_chat(chat_id)

    mystic = await client.send_message(chat_id, "🔄 **Fetching playlist & starting stream...**")

    result = [str(k).strip() for k in notes.keys()]

    try:
        _ = await _lang(chat_id)
        await stream(
            _,
            mystic,
            target_user_id,
            result,
            chat_id,
            user_name,
            chat_id,
            video=is_video,
            streamtype="playlist",
        )
    except Exception as e:
        return await mystic.edit_text(f"❌ Error starting stream: {e}")


@app.on_message(filters.command(DELETEPLAYLIST_COMMAND) & ~BANNED_USERS)
@language
async def del_plist_msg(client, message: Message, _):
    user_id = message.from_user.id
    del_blocks, total_tracks, total_pages = await get_rich_del_page(user_id, page=0)
    if total_tracks == 0:
        return await message.reply_text(_["playlist_3"])

    caption = (
        "<blockquote><emoji id=5895705279416241926>🗑️</emoji> <u><b>MANAGE & REMOVE TRACKS</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        f"Total <b>{total_tracks}</b> tracks inside playlist.\n"
        "Use ⬅️ / ➡️️ to switch pages and tap any song to delete.</blockquote>"
    )
    blocks = html_to_rich_blocks(caption)
    blocks += del_blocks
    await deliver_rich(client, message.chat.id, blocks)


@app.on_callback_query(filters.regex(r"^del_page\|") & ~BANNED_USERS)
async def paginate_del_playlist(client, CallbackQuery):
    page = int(CallbackQuery.data.split("|")[1])
    user_id = CallbackQuery.from_user.id
    del_blocks, total_tracks, total_pages = await get_rich_del_page(user_id, page=page)
    if total_tracks == 0:
        caption = "<blockquote><emoji id=5895705279416241926>✨</emoji> <b>Your playlist is empty.</b></blockquote>"
        blocks = html_to_rich_blocks(caption)
        return await edit_rich(CallbackQuery.message, blocks)

    caption = (
        "<blockquote><emoji id=5895705279416241926>🗑️</emoji> <u><b>MANAGE & REMOVE TRACKS</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        f"Total <b>{total_tracks}</b> tracks inside playlist.\n"
        "Use ⬅️ / ➡️ to switch pages and tap any song to delete.</blockquote>"
    )
    blocks = html_to_rich_blocks(caption)
    blocks += del_blocks
    await edit_rich(CallbackQuery.message, blocks)


@app.on_callback_query(filters.regex(r"^del_track\|") & ~BANNED_USERS)
async def delete_single_track(client, CallbackQuery):
    parts = CallbackQuery.data.split("|")
    page = int(parts[1])
    videoid = parts[2]
    user_id = CallbackQuery.from_user.id

    deleted = await delete_playlist(user_id, videoid)
    if deleted:
        await CallbackQuery.answer("🗑️ Song removed!", show_alert=False)
    else:
        await CallbackQuery.answer("❌ Song not found!", show_alert=True)

    del_blocks, total_tracks, total_pages = await get_rich_del_page(user_id, page=page)
    if total_tracks == 0:
        caption = "<blockquote><emoji id=5895705279416241926>✨</emoji> <b>Your playlist is now empty.</b></blockquote>"
        blocks = html_to_rich_blocks(caption)
        return await edit_rich(CallbackQuery.message, blocks)

    caption = (
        "<blockquote><emoji id=5895705279416241926>🗑️</emoji> <u><b>MANAGE & REMOVE TRACKS</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        f"Total <b>{total_tracks}</b> tracks inside playlist.\n"
        "Use ⬅️ / ➡️ to switch pages and tap any song to delete.</blockquote>"
    )
    blocks = html_to_rich_blocks(caption)
    blocks += del_blocks
    await edit_rich(CallbackQuery.message, blocks)


@app.on_callback_query(filters.regex(r"^open_autoplay_card\|") & ~BANNED_USERS)
async def open_autoplay_modal(client, CallbackQuery):
    caption = (
        "<blockquote><emoji id=5895705279416241926>🎲</emoji> <u><b>AUTOPLAY & MOOD CONFIG</b></u></blockquote>\n\n"
        "<blockquote expandable>"
        "<emoji id=5974235702701853774>✨</emoji> Select preferred mood for automatic continuous streaming:\n"
        "<emoji id=5409132617750555920>⚡</emoji> Bot streams related tracks when queue ends.</blockquote>"
    )
    blocks = rich_autoplay_mood_blocks(caption)
    await deliver_rich(client, CallbackQuery.message.chat.id, blocks)
    await CallbackQuery.answer()


# Unified Add to Playlist Handler (works for both normal now-playing and autoplay button)
@app.on_callback_query(filters.regex(r"^(add_playlist\||add_playlist_)") & ~BANNED_USERS)
@languageCB
async def add_current_playing_to_playlist(client, CallbackQuery, _):
    user_id = CallbackQuery.from_user.id
    raw_data = CallbackQuery.data

    clean_vid = None
    title = "Song Track"
    duration = "03:30"

    if raw_data.startswith("add_playlist_"):
        clean_vid = raw_data.replace("add_playlist_", "").strip()
        try:
            from Oneforall import YouTube
            title, duration, _, _, _ = await YouTube.details(clean_vid, True)
            title = title[:50].title()
        except Exception:
            pass
    else:
        try:
            chat_id = int(raw_data.split("|")[1])
        except Exception:
            chat_id = CallbackQuery.message.chat.id

        tracks = db.get(chat_id)
        if not tracks:
            return await CallbackQuery.answer("❌ Currently no track is streaming.", show_alert=True)

        current_track = tracks[0]
        raw_vid = current_track.get("vidid") or current_track.get("file", "")
        clean_vid = str(raw_vid).replace("vid_", "").strip()
        title = current_track.get("title", "Unknown Track")
        duration = current_track.get("dur", "00:00")

    if not clean_vid:
        return await CallbackQuery.answer("❌ Track ID not found.", show_alert=True)

    _check = await get_playlist(user_id, clean_vid)
    if _check:
        return await CallbackQuery.answer("⚠️ Already in your playlist!", show_alert=True)

    _count = await get_playlist_names(user_id)
    if len(_count) >= SERVER_PLAYLIST_LIMIT:
        return await CallbackQuery.answer(_["playlist_9"].format(SERVER_PLAYLIST_LIMIT), show_alert=True)

    plist = {
        "videoid": clean_vid,
        "title": title,
        "duration": duration,
    }
    await save_playlist(user_id, clean_vid, plist)
    await CallbackQuery.answer(f"✅ Added to playlist:\n{title[:30]}...", show_alert=True)


@app.on_message(filters.command(ADDPLAYLIST_COMMAND) & ~BANNED_USERS)
@language
async def add_playlist_cmd(client, message: Message, _):
    if len(message.command) < 2:
        return await message.reply_text(
            "**➻ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ᴀ sᴏɴɢ ɴᴀᴍᴇ ᴏʀ ʟɪɴᴋ ᴀғᴛᴇʀ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ..**\n\n▷ `/addplaylist Blue Eyes`"
        )

    query = " ".join(message.command[1:])
    user_id = message.from_user.id
    _count = await get_playlist_names(user_id)
    if len(_count) >= SERVER_PLAYLIST_LIMIT:
        return await message.reply_text(_["playlist_9"].format(SERVER_PLAYLIST_LIMIT))

    m = await message.reply("**🔄 ᴀᴅᴅɪɴɢ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ... **")
    try:
        from Oneforall import YouTube

        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            return await m.edit_text("❌ No tracks found.")

        videoid = results[0]["id"]
        title, duration_min, _, _, _ = await YouTube.details(videoid, True)
        title = (title[:50]).title()
        plist = {
            "videoid": videoid,
            "title": title,
            "duration": duration_min,
        }
        await save_playlist(user_id, videoid, plist)
        await m.delete()

        caption = (
            "<blockquote><emoji id=5895705279416241926>✅</emoji> <u><b>ADDED TO PLAYLIST</b></u></blockquote>\n\n"
            "<blockquote expandable>"
            f"🎵 <b>Track :</b> <code>{title}</code>\n"
            f"⏱️ <b>Duration :</b> <code>{duration_min}</code>\n\n"
            "Use <code>/playlist</code> to view or <code>/play</code> in group!</blockquote>"
        )
        blocks = html_to_rich_blocks(caption)
        blocks += get_playlist_markup(_)
        await deliver_rich(client, message.chat.id, blocks)
    except Exception as e:
        await m.edit_text(f"Error: {e}")


@app.on_message(filters.command(DELETE_ALL_PLAYLIST_COMMAND) & ~BANNED_USERS)
@language
async def delete_all_playlists(client, message, _):
    user_id = message.from_user.id
    _playlist = await get_playlist_names(user_id)
    if _playlist:
        caption = "<blockquote>⚠ <b>Are you sure you want to delete entire playlist?</b></blockquote>"
        blocks = html_to_rich_blocks(caption)
        blocks += warning_markup(_)
        await deliver_rich(client, message.chat.id, blocks)
    else:
        await message.reply_text(_["playlist_3"])


@app.on_callback_query(filters.regex("close_panel") & ~BANNED_USERS)
async def close_panel_cb(client, CallbackQuery):
    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass


@app.on_callback_query(filters.regex("delete_whole_playlist") & ~BANNED_USERS)
@languageCB
async def del_whole_playlist(client, CallbackQuery, _):
    _playlist = await get_playlist_names(CallbackQuery.from_user.id)
    for x in _playlist:
        await delete_playlist(CallbackQuery.from_user.id, x)
    await CallbackQuery.answer("✅ Playlist cleared!", show_alert=True)
    return await CallbackQuery.message.delete()
