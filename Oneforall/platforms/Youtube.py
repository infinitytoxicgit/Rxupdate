import asyncio
import os
import random
import re
from typing import Union
import requests
import httpx
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython import VideosSearch

from Oneforall.utils.database import is_on_off
from Oneforall.utils.formatters import time_to_seconds


def cookies():
    url = "https://v0-mongo-db-api-setup.vercel.app/api/cookies.txt"
    filename = "cookies.txt"

    if os.path.exists(filename):
        os.remove(filename)

    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
        return filename
    else:
        raise Exception("Failed to fetch cookies from URL")


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()

    if errorz:
        if "unavailable videos are hidden" in errorz.decode("utf-8").lower():
            return out.decode("utf-8")
        return errorz.decode("utf-8")

    return out.decode("utf-8")


async def api_download(vidid, video=False):
    API = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    }

    if video:
        path = os.path.join("downloads", f"{vidid}.mp4")
        data = {"url": f"https://www.youtube.com/watch?v={vidid}", "vQuality": "480"}
    else:
        path = os.path.join("downloads", f"{vidid}.m4a")
        data = {
            "url": f"https://www.youtube.com/watch?v={vidid}",
            "isAudioOnly": "True",
            "aFormat": "opus",
        }

    async with httpx.AsyncClient(http2=True) as client:
        response = await client.post(API, headers=headers, json=data)
        response.raise_for_status()
        results = response.json()["url"]

    cmd = f"yt-dlp '{results}' -o '{path}'"
    await shell_cmd(cmd)
    if os.path.isfile(path):
        return path
    else:
        return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--extractor-args",
            "youtubepot-bgutilscript:script_path=/root/bgutil-ytdlp-pot-provider/server/build/generate_once.js",
            "--remote-components",
            "ejs:github",
            "--js-runtimes",
            "bun:/root/.bun/bin/bun",
            "--cookies",
            "/root/Unique-/youtube.txt",
            "-g",
            "-f",
            "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download --cookies cookies() {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        query = link
        if not re.search(r"(?:youtube\.com|youtu\.be)", link):
            query = f"ytsearch5:{link}"

        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "cookiefile": "/root/Unique-/youtube.txt",
            "js_runtimes": {
                "bun": {
                    "path": "/root/.bun/bin/bun"
                }
            },
            "remote_components": ["ejs:github"],
            "extractor_args": {
                "youtubepot-bgutilscript": {
                    "script_path": "/root/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
                }
            },
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)

        entries = info.get("entries") or [info]
        entry = next((x for x in entries if x and x.get("id")), None)

        if not entry:
            raise Exception("No YouTube result found")

        vidid = entry["id"]
        title = entry.get("title") or "Unknown Title"
        duration_sec = entry.get("duration")

        if duration_sec:
            duration_min = f"{int(duration_sec)//60}:{int(duration_sec)%60:02d}"
        else:
            duration_min = None

        yturl = f"https://www.youtube.com/watch?v={vidid}"
        thumbnail = entry.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "duration_sec": duration_sec or 0,
            "thumb": thumbnail,
        }

        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": "/root/Unique-/youtube.txt"}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            vidid = link
            link = self.base + link
        else:
            pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|live_stream\?stream_id=|(?:\/|\?|&)v=)?([^&\n]+)"
            match = re.search(pattern, link)
            vidid = match.group(1)
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": "/root/Unique-/youtube.txt",
                "extractor_args": {
                    "youtube": {
                        "player_client": ["mweb"],
                    }
                },
                "js_runtimes": {
                    "bun": {
                        "path": "/root/.bun/bin/bun"
                    }
                },
                "remote_components": ["ejs:github"],
                "extractor_args": {
                    "youtubepot-bgutilscript": {
                        "script_path": "/root/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
                    }
                },
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join(
                "downloads",
                f"{info['id']}.{info['ext']}"
            )
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        # FIXED: Ab yeh actual video + audio ko mp4 me download aur merge karega
        def video_dl():
            mp4_path = os.path.join("downloads", f"{vidid}.mp4")
            if os.path.exists(mp4_path):
                return mp4_path

            ydl_optssx = {
                "format": "(bestvideo[height<=720]+bestaudio/best[height<=720])/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "merge_output_format": "mp4",
                "prefer_ffmpeg": True,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": "/root/Unique-/youtube.txt",
                "extractor_args": {
                    "youtube": {
                        "player_client": ["mweb"],
                    }
                },
                "js_runtimes": {
                    "bun": {
                        "path": "/root/.bun/bin/bun"
                    }
                },
                "remote_components": ["ejs:github"],
                "extractor_args": {
                    "youtubepot-bgutilscript": {
                        "script_path": "/root/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
                    }
                },
            }

            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            
            if os.path.exists(mp4_path):
                return mp4_path
            
            # Agar ext alag ho toh match karo
            for f in os.listdir("downloads"):
                if f.startswith(vidid) and f.endswith((".mp4", ".mkv", ".webm")):
                    return os.path.join("downloads", f)
            return mp4_path

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
                "cookiefile": "/root/Unique-/youtube.txt",
                "extractor_args": {"youtube": {"player_client": ["mweb"]}},
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "cookiefile": "/root/Unique-/youtube.txt",
                "extractor_args": {"youtube": {"player_client": ["mweb"]}},
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            direct = True
            downloaded_file = await loop.run_in_executor(
                None, video_dl
            )
        else:
            direct = True
            downloaded_file = await loop.run_in_executor(
                None, audio_dl
            )

        if not downloaded_file:
            raise Exception("yt-dlp returned empty file/stream")
        return downloaded_file, direct
