import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall
from pytgcalls.types import AudioQuality, MediaStream, Update, VideoQuality
from pytgcalls.types.stream import StreamAudioEnded

import config
from Oneforall import LOGGER, YouTube, app
from Oneforall.misc import db
from Oneforall.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from Oneforall.utils.exceptions import AssistantErr
from Oneforall.utils.formatters import check_duration, seconds_to_min, speed_converter
from Oneforall.utils.inline.rich import send_now_playing_rich
from Oneforall.utils.stream.autoclear import auto_clean
from Oneforall.utils.thumbnails import get_thumb
from strings import get_string

autoend = {}
counter = {}
loop = asyncio.get_event_loop_policy().get_event_loop()


async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="Oneforall 1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(
            self.userbot1,
            cache_duration=100,
        )
        self.userbot2 = Client(
            name="Oneforall 2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(
            self.userbot2,
            cache_duration=100,
        )
        self.userbot3 = Client(
            name="Oneforall 3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(
            self.userbot3,
            cache_duration=100,
        )
        self.userbot4 = Client(
            name="Oneforall 4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(
            self.userbot4,
            cache_duration=100,
        )
        self.userbot5 = Client(
            name="Oneforall 5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(
            self.userbot5,
            cache_duration=100,
        )

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause_stream(chat_id)

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute_stream(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute_stream(chat_id)

    async def get_participant(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        participant = await assistant.get_participants(chat_id)
        return participant

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume_stream(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_group_call(chat_id)
        except Exception:
            pass

    async def stop_stream_force(self, chat_id: int):
        for bot in [self.one, self.two, self.three, self.four, self.five]:
            try:
                await bot.leave_group_call(chat_id)
            except Exception:
                pass
        try:
            await _clear_(chat_id)
        except Exception:
            pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = 1.0
                if str(speed) == "0.5":
                    vs = 2.0
                elif str(speed) == "0.75":
                    vs = 1.35
                elif str(speed) == "1.5":
                    vs = 0.68
                elif str(speed) == "2.0":
                    vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
        dur = await loop.run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        stream_is_video = str(playing[0]["streamtype"]).lower().strip() == "video"
        stream = (
            MediaStream(
                out,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
                ffmpeg_parameters=f"-ss {played} -to {duration}",
            )
            if stream_is_video
            else MediaStream(
                out,
                audio_parameters=AudioQuality.HIGH,
                ffmpeg_parameters=f"-ss {played} -to {duration}",
                video_flags=MediaStream.IGNORE,
            )
        )
        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except Exception:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_group_call(chat_id)
        except Exception:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        if video:
            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )
        else:
            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.IGNORE,
            )
        try:
            await assistant.change_stream(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).warning(f"change_stream retry on skip: {e}")
            await asyncio.sleep(0.5)
            await assistant.change_stream(chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        is_vid = str(mode).lower().strip() == "video"
        stream = (
            MediaStream(
                file_path,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
                ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )
            if is_vid
            else MediaStream(
                file_path,
                audio_parameters=AudioQuality.HIGH,
                ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
                video_flags=MediaStream.IGNORE,
            )
        )
        await assistant.change_stream(chat_id, stream)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.join_group_call(
            config.LOGGER_ID,
            MediaStream(link),
        )
        await asyncio.sleep(0.2)
        await assistant.leave_group_call(config.LOGGER_ID)

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        if video:
            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )
        else:
            stream = MediaStream(
                link,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.IGNORE,
            )
        try:
            await assistant.join_group_call(
                chat_id,
                stream,
            )
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(_["call_9"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            if "phone.CreateGroupCall" in str(e):
                raise AssistantErr(_["call_8"])
            raise AssistantErr(f"Join VC failed: {e}")

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except Exception:
                pass

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        if not check:
            await _clear_(chat_id)
            return await client.leave_group_call(chat_id)

        popped = None
        loop_cnt = await get_loop(chat_id)
        try:
            if loop_cnt == 0:
                popped = check.pop(0)
            else:
                loop_cnt = loop_cnt - 1
                await set_loop(chat_id, loop_cnt)

            if popped:
                try:
                    await auto_clean(popped)
                except Exception:
                    pass

            if not check:
                from pyrogram import enums, types
                from Oneforall.plugins.misc.autoplay import (
                    get_autoplay_mood,
                    get_autoplay_recommendation,
                    is_autoplay_on,
                )
                from Oneforall.utils.inline.rich import (
                    deliver_rich,
                    html_to_rich_blocks,
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
                        duration = seconds_to_min(dur_sec) or "03:00"

                        prev_auto_msg = getattr(self, f"_auto_msg_{chat_id}", None)
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
                        setattr(self, f"_auto_msg_{chat_id}", auto_msg)

                        last_stream_mode = popped.get("streamtype", "audio") if popped else "audio"

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
                        check = db.get(chat_id)
                    else:
                        await _clear_(chat_id)
                        return await client.leave_group_call(chat_id)
                else:
                    await _clear_(chat_id)
                    return await client.leave_group_call(chat_id)

        except Exception as e:
            LOGGER(__name__).error(f"Stream end exception: {e}")
            await _clear_(chat_id)
            return await client.leave_group_call(chat_id)

        if not check:
            await _clear_(chat_id)
            return await client.leave_group_call(chat_id)

        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = str(check[0]["streamtype"]).lower().strip()
        raw_vidid = str(check[0]["vidid"]).replace("vid_", "").strip()
        db[chat_id][0]["played"] = 0
        if exis := (check[0]).get("old_dur"):
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        video = (streamtype == "video")
        if video:
            await add_active_video_chat(chat_id)
        else:
            await remove_active_video_chat(chat_id)

        if "live_" in queued:
            n, link = await YouTube.video(raw_vidid, True)
            if n == 0:
                return await app.send_message(original_chat_id, text=_["call_6"])
            stream = (
                MediaStream(
                    link,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )
                if video
                else MediaStream(
                    link,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.IGNORE,
                )
            )
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            img = await get_thumb(raw_vidid)
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{raw_vidid}",
                title[:23],
                check[0]["dur"],
                user,
            )
            run = await send_now_playing_rich(app, chat_id, original_chat_id, img, caption)
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        elif "vid_" in queued or len(raw_vidid) == 11:
            clean_id = raw_vidid if len(raw_vidid) == 11 else str(queued).replace("vid_", "").strip()
            mystic = await app.send_message(original_chat_id, _["call_7"])
            file_path = None
            try:
                file_path, direct = await YouTube.download(
                    clean_id,
                    mystic,
                    videoid=True,
                    video=video,
                )
            except Exception as e:
                return await mystic.edit_text(str(e), disable_web_page_preview=True)

            if not file_path:
                return await mystic.edit_text("Download failed: empty file_path")

            stream = (
                MediaStream(
                    file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )
                if video
                else MediaStream(
                    file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.IGNORE,
                )
            )
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])

            img = await get_thumb(clean_id)
            try:
                await mystic.delete()
            except Exception:
                pass
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{clean_id}",
                title[:23],
                check[0]["dur"],
                user,
            )
            run = await send_now_playing_rich(app, chat_id, original_chat_id, img, caption)
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

        elif "index_" in queued:
            stream = (
                MediaStream(
                    raw_vidid,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )
                if video
                else MediaStream(
                    raw_vidid,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.IGNORE,
                )
            )
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            caption = _["stream_2"].format(user)
            run = await send_now_playing_rich(app, chat_id, original_chat_id, config.STREAM_IMG_URL, caption)
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        else:
            stream = (
                MediaStream(
                    queued,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.SD_480p,
                )
                if video
                else MediaStream(
                    queued,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.IGNORE,
                )
            )
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])

            if raw_vidid == "telegram":
                thumb_img = config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL
                caption = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)
                run = await send_now_playing_rich(app, chat_id, original_chat_id, thumb_img, caption)
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif raw_vidid == "soundcloud":
                caption = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)
                run = await send_now_playing_rich(app, chat_id, original_chat_id, config.SOUNCLOUD_IMG_URL, caption)
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                img = await get_thumb(raw_vidid)
                caption = _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{raw_vidid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                )
                run = await send_now_playing_rich(app, chat_id, original_chat_id, img, caption)
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        pings = []
        for bot in [self.one, self.two, self.three, self.four, self.five]:
            try:
                pings.append(await bot.ping)
            except Exception:
                pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_kicked()
        @self.two.on_kicked()
        @self.three.on_kicked()
        @self.four.on_kicked()
        @self.five.on_kicked()
        @self.one.on_closed_voice_chat()
        @self.two.on_closed_voice_chat()
        @self.three.on_closed_voice_chat()
        @self.four.on_closed_voice_chat()
        @self.five.on_closed_voice_chat()
        @self.one.on_left()
        @self.two.on_left()
        @self.three.on_left()
        @self.four.on_left()
        @self.five.on_left()
        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def stream_end_handler(client, update: Update):
            if not isinstance(update, StreamAudioEnded):
                return
            await self.change_stream(client, update.chat_id)


Hotty = Call()
