import asyncio
import os
from random import randint
from typing import Union
from uuid import uuid4

from youtubesearchpython import VideosSearch
from pyrogram import enums, types

import config
from Oneforall import YouTube, app
from Oneforall.core.call import Hotty
from Oneforall.misc import db
from Oneforall.utils.database import add_active_video_chat, is_active_chat, remove_active_video_chat
from Oneforall.utils.exceptions import AssistantErr
from Oneforall.utils.inline import close_markup
from Oneforall.utils.inline.rich import (
    deliver_rich,
    html_to_rich_blocks,
    release_mystic,
    send_now_playing_rich,
    send_queue_rich,
)
from Oneforall.utils.stream.queue import put_queue, put_queue_index


async def _fetch(_, chat_id, vidid, mystic, video):
    status = True if video else None
    task = asyncio.ensure_future(
        YouTube.download(vidid, mystic, videoid=True, video=status)
    )
    try:
        file_path, direct = await task
    except Exception:
        file_path, direct = None, False
    if not file_path:
        raise AssistantErr(_["play_14"] if "play_14" in _ else "Download failed.")
    return file_path, direct


async def _announce_queue(_, chat_id, original_chat_id, mystic, title, duration_min, user_name):
    position = len(db.get(chat_id)) - 1
    qid = uuid4().hex[:8]
    db[chat_id][-1]["qid"] = qid
    caption = _["queue_4"].format(position, title[:27], duration_min, user_name)
    await send_queue_rich(
        app,
        chat_id,
        original_chat_id,
        caption,
        qid,
        replace=mystic,
    )
    return position


async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    outcome = await _stream(
        _,
        mystic,
        user_id,
        result,
        chat_id,
        user_name,
        original_chat_id,
        video,
        streamtype,
        spotify,
        forceplay,
    )
    await release_mystic(mystic)
    return outcome


async def _stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return
    if forceplay:
        await Hotty.force_stop_stream(chat_id)

    # Boolean clean check
    is_video_mode = bool(video)
    status = True if is_video_mode else None

    if streamtype == "playlist":
        first_song = True
        added_count = 0

        # Video mode database sync
        if is_video_mode:
            await add_active_video_chat(chat_id)
        else:
            await remove_active_video_chat(chat_id)

        for search in result:
            if added_count >= config.PLAYLIST_FETCH_LIMIT:
                break

            search_str = str(search).strip()
            is_vid = len(search_str) == 11 and " " not in search_str

            title = "Playlist Track"
            duration_min = "03:30"
            duration_sec = 210
            thumbnail = None
            vidid = search_str

            try:
                (
                    t_title,
                    t_dur_min,
                    t_dur_sec,
                    t_thumb,
                    t_vidid,
                ) = await YouTube.details(search_str, videoid=is_vid)
                if t_vidid:
                    vidid = t_vidid
                if t_title:
                    title = t_title
                if t_dur_min:
                    duration_min = str(t_dur_min)
                if t_dur_sec:
                    duration_sec = int(t_dur_sec)
                if t_thumb:
                    thumbnail = t_thumb
            except Exception:
                pass

            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video_mode else "audio",
                )
                added_count += 1
            else:
                if first_song:
                    if not forceplay:
                        db[chat_id] = []

                    try:
                        file_path, direct = await _fetch(_, chat_id, vidid, mystic, is_video_mode)
                    except Exception:
                        continue

                    thumb_task = asyncio.ensure_future(get_thumb(vidid))
                    try:
                        # CRITICAL FIX: Jab video mode ho, tab image=None pass karo taaki VC video stream switch kare
                        await Hotty.join_call(
                            chat_id,
                            original_chat_id,
                            file_path,
                            video=status,
                            image=None if is_video_mode else thumbnail,
                        )
                    except Exception as e:
                        if mystic:
                            await mystic.edit_text(f"❌ Assistant failed to join VC: {e}")
                        return

                    await put_queue(
                        chat_id,
                        original_chat_id,
                        file_path if direct else f"vid_{vidid}",
                        title,
                        duration_min,
                        user_name,
                        vidid,
                        user_id,
                        "video" if is_video_mode else "audio",
                        forceplay=forceplay,
                    )
                    img = await thumb_task
                    caption = _["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:23],
                        duration_min,
                        user_name,
                    )
                    run = await send_now_playing_rich(
                        app,
                        chat_id,
                        original_chat_id,
                        img,
                        caption,
                        replace=mystic,
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                    first_song = False
                    added_count += 1
                else:
                    await put_queue(
                        chat_id,
                        original_chat_id,
                        f"vid_{vidid}",
                        title,
                        duration_min,
                        user_name,
                        vidid,
                        user_id,
                        "video" if is_video_mode else "audio",
                    )
                    added_count += 1

        if added_count == 0:
            if mystic:
                try:
                    await mystic.edit_text("❌ No valid songs could be played from this playlist.")
                except Exception:
                    pass
            return

        caption = (
            "<blockquote><emoji id=5895705279416241926>📑</emoji> <u><b>PLAYLIST STREAM STARTED</b></u></blockquote>\n\n"
            "<blockquote expandable>"
            f"👤 <b>Playlist Owner:</b> {user_name}\n"
            f"📊 <b>Total Queued:</b> <code>{added_count} tracks</code>\n"
            f"🎬 <b>Mode:</b> <code>{'Video' if is_video_mode else 'Audio'}</code></blockquote>"
        )
        blocks = html_to_rich_blocks(caption)
        blocks.append(
            types.InputRichBlockButtons(
                buttons=[
                    types.RichMessageButton(
                        text="» Skip",
                        style=enums.ButtonStyle.PRIMARY,
                        callback_data=f"ADMIN Skip|{chat_id}",
                    ),
                    types.RichMessageButton(
                        text="⟲ End Playlist",
                        style=enums.ButtonStyle.DANGER,
                        callback_data=f"ADMIN Stop|{chat_id}",
                    ),
                ]
            )
        )
        await deliver_rich(app, original_chat_id, blocks)
        return

    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        status = True if is_video_mode else None
        thumb_task = (
            None
            if await is_active_chat(chat_id)
            else asyncio.ensure_future(get_thumb(vidid))
        )
        file_path, direct = await _fetch(_, chat_id, vidid, mystic, is_video_mode)
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video_mode else "audio",
            )
            await _announce_queue(
                _, chat_id, original_chat_id, mystic, title, duration_min, user_name
            )
        else:
            if not forceplay:
                db[chat_id] = []
            if is_video_mode:
                await add_active_video_chat(chat_id)
            else:
                await remove_active_video_chat(chat_id)

            await Hotty.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=None if is_video_mode else thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video_mode else "audio",
                forceplay=forceplay,
            )
            img = await (thumb_task if thumb_task else get_thumb(vidid))
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name,
            )
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                img,
                caption,
                replace=mystic,
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            await _announce_queue(
                _, chat_id, original_chat_id, mystic, title, duration_min, user_name
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await remove_active_video_chat(chat_id)
            await Hotty.join_call(chat_id, original_chat_id, file_path, video=None)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            caption = _["stream_1"].format(
                config.SUPPORT_CHAT, title[:23], duration_min, user_name
            )
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                config.SOUNCLOUD_IMG_URL,
                caption,
                replace=mystic,
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if is_video_mode else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video_mode else "audio",
            )
            await _announce_queue(
                _, chat_id, original_chat_id, mystic, title, duration_min, user_name
            )
        else:
            if not forceplay:
                db[chat_id] = []
            if is_video_mode:
                await add_active_video_chat(chat_id)
            else:
                await remove_active_video_chat(chat_id)

            await Hotty.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video_mode else "audio",
                forceplay=forceplay,
            )
            thumb = config.TELEGRAM_VIDEO_URL if is_video_mode else config.TELEGRAM_AUDIO_URL
            caption = _["stream_1"].format(link, title[:23], duration_min, user_name)
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                thumb,
                caption,
                replace=mystic,
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "Live Track"
        status = True if is_video_mode else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video_mode else "audio",
            )
            await _announce_queue(
                _, chat_id, original_chat_id, mystic, title, duration_min, user_name
            )
        else:
            if not forceplay:
                db[chat_id] = []
            if is_video_mode:
                await add_active_video_chat(chat_id)
            else:
                await remove_active_video_chat(chat_id)

            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            await Hotty.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=None if is_video_mode else thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video_mode else "audio",
                forceplay=forceplay,
            )
            img = await get_thumb(vidid)
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name,
            )
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                img,
                caption,
                replace=mystic,
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        link = result
        title = "Index Stream"
        duration_min = "00:00"
        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video_mode else "audio",
            )
            await _announce_queue(
                _, chat_id, original_chat_id, mystic, title, duration_min, user_name
            )
        else:
            if not forceplay:
                db[chat_id] = []
            if is_video_mode:
                await add_active_video_chat(chat_id)
            else:
                await remove_active_video_chat(chat_id)

            await Hotty.join_call(
                chat_id,
                original_chat_id,
                link,
                video=status,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video_mode else "audio",
                forceplay=forceplay,
            )
            caption = _["stream_2"].format(user_name)
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                config.STREAM_IMG_URL,
                caption,
                replace=mystic,
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"


async def get_thumb(vidid):
    try:
        query = f"https://www.youtube.com/watch?v={vidid}"
        results = VideosSearch(query, limit=1)
        res = await results.next()
        for result in res["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            return thumbnail
    except Exception:
        pass
    return config.YOUTUBE_IMG_URL
