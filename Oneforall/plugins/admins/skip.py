from pyrogram import enums, filters, types
from pyrogram.types import Message

import config
from config import BANNED_USERS
from Oneforall import YouTube, app
from Oneforall.core.call import Hotty
from Oneforall.misc import db
from Oneforall.utils.database import (
    add_active_video_chat,
    get_lang,
    get_loop,
    remove_active_video_chat,
)
from Oneforall.utils.decorators import AdminRightsCheck
from Oneforall.utils.decorators.language import languageCB
from Oneforall.utils.formatters import seconds_to_min
from Oneforall.utils.inline import close_markup
from Oneforall.utils.inline.rich import (
    deliver_rich,
    html_to_rich_blocks,
    send_now_playing_rich,
)
from Oneforall.utils.stream.autoclear import auto_clean
from Oneforall.utils.thumbnails import get_thumb
from strings import get_string


async def handle_autoplay_on_skip(chat_id, last_stream_mode="audio"):
    """Trigger next romantic hindi autoplay song if autoplay is ON when queue ends"""
    try:
        from Oneforall.plugins.misc.autoplay import (
            get_autoplay_mood,
            get_autoplay_recommendation,
            is_autoplay_on,
        )

        if await is_autoplay_on(chat_id):
            track_data, track_id = await get_autoplay_recommendation(chat_id)
            if track_data and track_id:
                clean_tid = str(track_id).replace("vid_", "").strip()
                mood_info = await get_autoplay_mood(chat_id)
                m_tag = mood_info.get("mood", "romantic").title()
                l_tag = mood_info.get("language", "hindi").title()
                auto_requester = f"Autoplay [{m_tag} | {l_tag}]"
                title = track_data.get("title", "Autoplay Track")
                dur_sec = track_data.get("duration_sec", 0)
                duration = seconds_to_min(dur_sec) or "03:30"

                # Clean previous autoplay card
                prev_auto_msg = getattr(Hotty, f"_auto_msg_{chat_id}", None)
                if prev_auto_msg:
                    try:
                        await prev_auto_msg.delete()
                    except Exception:
                        pass

                caption = (
                    "<blockquote><emoji id=5895705279416241926>🎲</emoji> <u><b>AUTOPLAY STREAMING</b></u></blockquote>\n\n"
                    "<blockquote expandable>"
                    f"🎵 <b>Track:</b> {title[:40]}\n"
                    f"⏱️ <b>Duration:</b> {duration}\n"
                    f"✨ <b>Vibe:</b> <code>{m_tag}</code> | <b>Language:</b> <code>{l_tag}</code>\n"
                    f"🤖 <b>Requested By:</b> <code>Autoplay Engine</code></blockquote>"
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
                                text="➕ Add Playlist",
                                style=enums.ButtonStyle.SUCCESS,
                                callback_data=f"add_playlist_{clean_tid}",
                            ),
                            types.RichMessageButton(
                                text="❌ Disable Autoplay",
                                style=enums.ButtonStyle.DANGER,
                                callback_data=f"AutoPlay|{chat_id}",
                            ),
                        ]
                    )
                )
                auto_msg = await deliver_rich(app, chat_id, blocks)
                setattr(Hotty, f"_auto_msg_{chat_id}", auto_msg)

                db[chat_id] = [
                    {
                        "title": title,
                        "dur": duration,
                        "streamtype": last_stream_mode,
                        "by": auto_requester,
                        "chat_id": chat_id,
                        "file": f"vid_{clean_tid}",
                        "vidid": clean_tid,
                        "seconds": dur_sec,
                        "played": 0,
                    }
                ]
                return db.get(chat_id)
    except Exception as e:
        print(f"Skip Autoplay Error: {e}")
    return None


async def execute_skip(chat_id: int, original_chat_id: int, user_mention: str, chat_title: str):
    language = await get_lang(chat_id)
    _ = get_string(language)

    check = db.get(chat_id)
    last_mode = "audio"
    if check and len(check) > 0:
        last_mode = str(check[0].get("streamtype", "audio")).lower().strip()

    try:
        popped = check.pop(0) if check else None
        if popped:
            await auto_clean(popped)
    except Exception:
        pass

    if not check:
        check = await handle_autoplay_on_skip(chat_id, last_stream_mode=last_mode)
        if not check:
            await app.send_message(
                original_chat_id,
                text=_["admin_6"].format(user_mention, chat_title),
                reply_markup=close_markup(_),
            )
            try:
                return await Hotty.stop_stream(chat_id)
            except Exception:
                return

    queued = check[0]["file"]
    title = (check[0]["title"]).title()
    user = check[0]["by"]
    streamtype = str(check[0]["streamtype"]).lower().strip()
    videoid = str(check[0]["vidid"]).replace("vid_", "").strip()

    status = (streamtype == "video")
    if status:
        await add_active_video_chat(chat_id)
    else:
        await remove_active_video_chat(chat_id)

    db[chat_id][0]["played"] = 0
    if exis := (check[0]).get("old_dur"):
        db[chat_id][0]["dur"] = exis
        db[chat_id][0]["seconds"] = check[0]["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0

    if "live_" in queued:
        n, link = await YouTube.video(videoid, True)
        if n == 0:
            return await app.send_message(original_chat_id, text=_["admin_7"].format(title))
        try:
            image = await YouTube.thumbnail(videoid, True)
        except Exception:
            image = None
        try:
            await Hotty.skip_stream(chat_id, link, video=status, image=image)
        except Exception:
            return await app.send_message(original_chat_id, text=_["call_6"])
        img = await get_thumb(videoid)
        run = await send_now_playing_rich(
            app,
            chat_id,
            original_chat_id,
            img,
            _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"

    elif "vid_" in queued or len(videoid) == 11:
        clean_id = videoid if len(videoid) == 11 else str(queued).replace("vid_", "").strip()
        mystic = await app.send_message(original_chat_id, _["call_7"], disable_web_page_preview=True)
        file_path = None
        try:
            file_path, direct = await YouTube.download(
                clean_id,
                mystic,
                videoid=True,
                video=status,
            )
        except Exception:
            return await mystic.edit_text(_["call_6"])

        try:
            image = await YouTube.thumbnail(clean_id, True)
        except Exception:
            image = None

        try:
            if not file_path:
                raise Exception("YT download failed: media_path=None")

            await Hotty.skip_stream(
                chat_id,
                file_path,
                video=status,
                image=image,
            )
        except Exception:
            return await mystic.edit_text(_["call_6"])

        img = await get_thumb(clean_id)
        run = await send_now_playing_rich(
            app,
            chat_id,
            original_chat_id,
            img,
            _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{clean_id}",
                title[:23],
                check[0]["dur"],
                user,
            ),
            replace=mystic,
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"

    elif "index_" in queued:
        try:
            await Hotty.skip_stream(chat_id, videoid, video=status)
        except Exception:
            return await app.send_message(original_chat_id, text=_["call_6"])
        run = await send_now_playing_rich(
            app,
            chat_id,
            original_chat_id,
            config.STREAM_IMG_URL,
            _["stream_2"].format(user),
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"

    else:
        try:
            image = await YouTube.thumbnail(videoid, True)
        except Exception:
            image = None

        try:
            await Hotty.skip_stream(chat_id, queued, video=status, image=image)
        except Exception:
            return await app.send_message(original_chat_id, text=_["call_6"])

        if videoid == "telegram":
            thumb_url = (
                config.TELEGRAM_AUDIO_URL
                if str(streamtype) == "audio"
                else config.TELEGRAM_VIDEO_URL
            )
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                thumb_url,
                _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        elif videoid == "soundcloud":
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                config.SOUNCLOUD_IMG_URL,
                _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        else:
            img = await get_thumb(videoid)
            run = await send_now_playing_rich(
                app,
                chat_id,
                original_chat_id,
                img,
                _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"


@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if len(message.command) >= 2:
        loop = await get_loop(chat_id)
        if loop != 0:
            return await message.reply_text(_["admin_8"])
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            check = db.get(chat_id)
            if check:
                count = len(check)
                if count > 2:
                    count = int(count - 1)
                    if 1 <= state <= count:
                        for x in range(state):
                            try:
                                popped = check.pop(0)
                                if popped:
                                    await auto_clean(popped)
                            except Exception:
                                return await message.reply_text(_["admin_12"])
                    else:
                        return await message.reply_text(_["admin_11"].format(count))
                else:
                    return await message.reply_text(_["admin_10"])
            else:
                return await message.reply_text(_["queue_2"])
        else:
            return await message.reply_text(_["admin_9"])

    await execute_skip(chat_id, message.chat.id, message.from_user.mention, message.chat.title)


# Handle Skip Button Callback from Autoplay & Now Playing Cards
@app.on_callback_query(filters.regex(r"^ADMIN Skip\|") & ~BANNED_USERS)
@languageCB
async def skip_callback_handler(client, CallbackQuery, _):
    chat_id = int(CallbackQuery.data.split("|")[1])
    await CallbackQuery.answer("⏭ Skipping track...", show_alert=False)
    await execute_skip(
        chat_id,
        CallbackQuery.message.chat.id,
        CallbackQuery.from_user.mention,
        CallbackQuery.message.chat.title or "Group",
    )
