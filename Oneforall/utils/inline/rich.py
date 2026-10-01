import math
import os
import random
import re
import aiohttp
from pyrogram import enums, errors, types
from Oneforall.misc import db
from Oneforall.core.mongo import mongodb
from Oneforall.utils.database import get_lang
from Oneforall.utils.formatters import seconds_to_min, time_to_seconds
from strings import get_string

autoplaydb = mongodb.autoplay
_consumed = set()
_FORBIDDEN = (errors.ChatSendPhotosForbidden, errors.ChatSendMediaForbidden)


async def _lang(chat_id):
    return get_string(await get_lang(chat_id))


def _wrap_plain(t):
    if not t:
        return ""
    if hasattr(types, "RichTextPlain"):
        try:
            return types.RichTextPlain(text=str(t))
        except Exception:
            pass
    return str(t)


def _to_rich_text(items):
    if not items:
        return _wrap_plain("")
    if not isinstance(items, list):
        items = [items]

    clean = []
    for it in items:
        if isinstance(it, str):
            clean.append(_wrap_plain(it))
        elif it is not None:
            clean.append(it)

    if not clean:
        return _wrap_plain("")
    if len(clean) == 1:
        return clean[0]

    if hasattr(types, "RichTextConcat"):
        try:
            return types.RichTextConcat(texts=clean)
        except Exception:
            pass
    return clean


def _make_custom_emoji(text, eid):
    digits = re.sub(r"\D", "", str(eid))
    if not digits:
        return _wrap_plain(text or "✨")

    if isinstance(text, list):
        flat_strs = []
        for x in text:
            if isinstance(x, str):
                flat_strs.append(x)
            elif hasattr(x, "text"):
                inner_t = getattr(x, "text")
                flat_strs.append(str(inner_t) if not hasattr(inner_t, "text") else str(getattr(inner_t, "text", "")))
            else:
                flat_strs.append(str(x))
        alt_text = "".join(flat_strs) or "✨"
    else:
        alt_text = str(text) if text else "✨"

    alt_text = str(alt_text).strip() or "✨"
    emoji_str_id = str(digits)
    emoji_int_id = int(digits)

    if hasattr(types, "RichTextCustomEmoji"):
        try:
            return types.RichTextCustomEmoji(
                custom_emoji_id=emoji_str_id,
                alternative_text=alt_text
            )
        except Exception:
            pass
        try:
            return types.RichTextCustomEmoji(
                custom_emoji_id=emoji_str_id,
                text=alt_text
            )
        except Exception:
            pass
        try:
            return types.RichTextCustomEmoji(
                custom_emoji_id=emoji_int_id,
                alternative_text=alt_text
            )
        except Exception:
            pass
        try:
            return types.RichTextCustomEmoji(
                document_id=emoji_int_id,
                text=alt_text
            )
        except Exception:
            pass

    return _wrap_plain(alt_text)


def _parse_inline(segment):
    if not segment:
        return ""

    tag_re = re.compile(
        r"<(/?)(b|strong|i|em|u|code|emoji|tg-emoji|a)(?:\s+(?:href|id)=(['\"]?)(.*?)\3)?\s*>",
        re.IGNORECASE,
    )

    parts = []
    stack = []
    pos = 0

    for m in tag_re.finditer(segment):
        if m.start() > pos:
            parts.append(segment[pos : m.start()])
        pos = m.end()

        closing = m.group(1)
        tag = m.group(2).lower()
        val = m.group(4) or ""

        if tag == "strong":
            tag = "b"
        elif tag == "em":
            tag = "i"
        elif tag == "tg-emoji":
            tag = "emoji"

        if not closing:
            stack.append((tag, val, len(parts)))
        elif stack and stack[-1][0] == tag:
            open_tag, attr_val, start = stack.pop()
            inner = parts[start:]
            del parts[start:]

            if open_tag == "emoji":
                parts.append(_make_custom_emoji(inner, attr_val))
            else:
                rich_inner = _to_rich_text(inner)
                if open_tag == "b":
                    parts.append(types.RichTextBold(text=rich_inner) if hasattr(types, "RichTextBold") else rich_inner)
                elif open_tag == "i":
                    parts.append(types.RichTextItalic(text=rich_inner) if hasattr(types, "RichTextItalic") else rich_inner)
                elif open_tag == "u":
                    parts.append(types.RichTextUnderline(text=rich_inner) if hasattr(types, "RichTextUnderline") else rich_inner)
                elif open_tag == "code":
                    parts.append(types.RichTextCode(text=rich_inner) if hasattr(types, "RichTextCode") else rich_inner)
                elif open_tag == "a":
                    url = str(attr_val).strip("\"' ")
                    parts.append(types.RichTextUrl(text=rich_inner, url=url) if hasattr(types, "RichTextUrl") else rich_inner)

    if pos < len(segment):
        parts.append(segment[pos:])

    return _to_rich_text(parts)


def _make_blockquote(items, is_expandable=False):
    rich_text = _to_rich_text(items)
    if is_expandable and hasattr(types, "InputRichBlockExpandableBlockQuotation"):
        try:
            return types.InputRichBlockExpandableBlockQuotation(text=rich_text)
        except Exception:
            pass
    if hasattr(types, "InputRichBlockBlockQuotation"):
        try:
            return types.InputRichBlockBlockQuotation(text=rich_text)
        except Exception:
            pass
    if hasattr(types, "InputRichBlockParagraph"):
        try:
            return types.InputRichBlockParagraph(text=rich_text)
        except Exception:
            pass
    return None


def _make_paragraph(parsed_items):
    rich_text = _to_rich_text(parsed_items)
    if hasattr(types, "InputRichBlockParagraph"):
        try:
            return types.InputRichBlockParagraph(text=rich_text)
        except Exception:
            pass
    return None


def html_to_rich_blocks(caption_html):
    if not caption_html:
        return []

    blocks = []
    bq_pattern = re.compile(
        r"<(blockquote(?:\s+[^>]*)?)>(.*?)</blockquote[^>]*>",
        re.DOTALL | re.IGNORECASE,
    )

    last_idx = 0
    for match in bq_pattern.finditer(caption_html):
        start, end = match.span()
        if start > last_idx:
            pre_text = caption_html[last_idx:start].strip()
            if pre_text:
                for line in pre_text.split("\n"):
                    clean_line = line.strip()
                    if clean_line:
                        parsed = _parse_inline(clean_line)
                        blk = _make_paragraph(parsed)
                        if blk:
                            blocks.append(blk)

        open_tag = match.group(1).lower()
        inner_content = match.group(2).strip()
        is_expandable = "expandable" in open_tag

        inner_items = []
        for line in inner_content.split("\n"):
            clean_line = line.strip()
            if clean_line:
                parsed = _parse_inline(clean_line)
                if parsed:
                    if isinstance(parsed, list):
                        inner_items.extend(parsed)
                    else:
                        inner_items.append(parsed)
                    inner_items.append("\n")

        if inner_items and inner_items[-1] == "\n":
            inner_items.pop()

        blk = _make_blockquote(inner_items, is_expandable=is_expandable)
        if blk:
            blocks.append(blk)

        last_idx = end

    if last_idx < len(caption_html):
        post_text = caption_html[last_idx:].strip()
        if post_text:
            for line in post_text.split("\n"):
                clean_line = line.strip()
                if clean_line:
                    parsed = _parse_inline(clean_line)
                    blk = _make_paragraph(parsed)
                    if blk:
                        blocks.append(blk)

    if not blocks:
        for line in caption_html.split("\n"):
            clean_line = line.strip()
            if clean_line:
                parsed = _parse_inline(clean_line)
                blk = _make_paragraph(parsed)
                if blk:
                    blocks.append(blk)

    return blocks


def _progress_line(played, dur):
    played_sec = time_to_seconds(played) if played else 0
    duration_sec = time_to_seconds(dur) if dur else 0
    percentage = (played_sec / duration_sec) * 100 if duration_sec else 0
    umm = math.floor(percentage)

    if 0 < umm <= 10:
        bar = "────────●"
    elif 10 < umm < 20:
        bar = "─●───────"
    elif 20 <= umm < 30:
        bar = "──●──────"
    elif 30 <= umm < 40:
        bar = "───●─────"
    elif 40 <= umm < 50:
        bar = "────●────"
    elif 50 <= umm < 60:
        bar = "─────●───"
    elif 60 <= umm < 70:
        bar = "──────●──"
    elif 70 <= umm < 80:
        bar = "───────●─"
    else:
        bar = "────────●"

    current_p = played or "00:00"
    current_d = dur or "00:00"
    return f"{current_p}  {bar}  {current_d}"


def _progress_row(played, dur, style=enums.ButtonStyle.DANGER):
    return types.InputRichBlockButtons(
        buttons=[
            types.RichMessageButton(
                text=_progress_line(played, dur),
                style=style,
                callback_data="GetTimer",
            )
        ]
    )


def _queue_len(chat_id):
    tracks = db.get(chat_id)
    return max(len(tracks) - 1, 0) if tracks else 0


async def _control_rows(chat_id, playing=True):
    q_len = _queue_len(chat_id)
    toggle = (
        types.RichMessageButton(
            text="II Pause",
            style=enums.ButtonStyle.SUCCESS,
            callback_data=f"ADMIN Pause|{chat_id}",
        )
        if playing
        else types.RichMessageButton(
            text="▷ Resume",
            style=enums.ButtonStyle.SUCCESS,
            callback_data=f"ADMIN Resume|{chat_id}",
        )
    )

    doc = await autoplaydb.find_one({"chat_id": chat_id})
    is_auto = doc.get("autoplay", False) if doc else False

    if is_auto:
        auto_btn = types.RichMessageButton(
            text="🟢 Autoplay On",
            style=enums.ButtonStyle.SUCCESS,
            callback_data=f"open_autoplay_card|{chat_id}",
        )
    else:
        auto_btn = types.RichMessageButton(
            text="🔴 Autoplay Off",
            style=enums.ButtonStyle.DANGER,
            callback_data=f"open_autoplay_card|{chat_id}",
        )

    return [
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="↺ Replay",
                    style=enums.ButtonStyle.DEFAULT,
                    callback_data=f"ADMIN Replay|{chat_id}",
                ),
                toggle,
                types.RichMessageButton(
                    text="» Skip",
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data=f"ADMIN Skip|{chat_id}",
                ),
            ]
        ),
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="➕ Playlist",
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data=f"add_playlist|{chat_id}",
                ),
                auto_btn,
                types.RichMessageButton(
                    text=f"≡ Queue · {q_len}",
                    style=enums.ButtonStyle.DEFAULT,
                    callback_data=f"nowplaying_queue {chat_id}",
                ),
            ]
        ),
    ]


async def _download_photo_if_url(photo):
    if not photo or not isinstance(photo, str):
        return None
    if photo.startswith("http://") or photo.startswith("https://"):
        os.makedirs("cache", exist_ok=True)
        local_path = os.path.join("cache", f"thumb_{abs(hash(photo))}.jpg")
        if os.path.isfile(local_path) and os.path.getsize(local_path) > 0:
            return local_path
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(photo, timeout=5) as resp:
                    if resp.status == 200:
                        with open(local_path, "wb") as f:
                            f.write(await resp.read())
                        return local_path
        except Exception:
            return None
    if os.path.isfile(photo) and os.path.getsize(photo) > 0:
        return photo
    return None


def _format_photo_block(photo):
    if not photo:
        return None
    try:
        return types.InputRichBlockPhoto(photo=types.InputMediaPhoto(str(photo)))
    except Exception:
        try:
            return types.InputRichBlockPhoto(photo=types.InputMediaPhoto(media=str(photo)))
        except Exception:
            return None


async def build_now_playing_blocks(
    _, photo, caption_html, chat_id, played=None, dur=None, playing=True
):
    blocks = []
    p_block = _format_photo_block(photo)
    if p_block:
        blocks.append(p_block)

    blocks += html_to_rich_blocks(caption_html)

    if not dur and db.get(chat_id):
        dur = db[chat_id][0].get("dur")

    cur_played = played if played else "00:00"
    cur_dur = dur if dur else "00:00"

    blocks.append(_progress_row(cur_played, cur_dur))
    ctrls = await _control_rows(chat_id, playing)
    blocks += ctrls
    return blocks


def _message_key(message):
    return (message.chat.id, message.id)


def _strip_photo(blocks):
    return [b for b in blocks if not isinstance(b, types.InputRichBlockPhoto)]


async def _try_deliver(client, target_chat_id, blocks, replace):
    rich = types.InputRichMessage(blocks=blocks)
    if replace is not None:
        try:
            edited = await replace.edit_text(rich_message=rich)
        except _FORBIDDEN:
            raise
        except Exception:
            try:
                await replace.delete()
            except Exception:
                pass
        else:
            _consumed.add(_message_key(replace))
            return edited or replace
    return await client.send_rich_message(target_chat_id, rich_message=rich)


async def _deliver(client, target_chat_id, blocks, replace=None):
    try:
        return await _try_deliver(client, target_chat_id, blocks, replace)
    except _FORBIDDEN:
        plain = _strip_photo(blocks)
        if len(plain) == len(blocks):
            raise
        return await _try_deliver(client, target_chat_id, plain, replace)
    except Exception:
        plain = _strip_photo(blocks)
        return await _try_deliver(client, target_chat_id, plain, replace)


async def _edit_rich(message, blocks):
    try:
        return await message.edit_text(
            rich_message=types.InputRichMessage(blocks=blocks)
        )
    except _FORBIDDEN:
        plain = _strip_photo(blocks)
        if len(plain) == len(blocks):
            raise
        return await message.edit_text(
            rich_message=types.InputRichMessage(blocks=plain)
        )
    except Exception:
        plain = _strip_photo(blocks)
        return await message.edit_text(
            rich_message=types.InputRichMessage(blocks=plain)
        )


def caption_blocks(caption_html):
    return html_to_rich_blocks(caption_html)


async def edit_rich(message, blocks):
    return await _edit_rich(message, blocks)


async def deliver_rich(client, target_chat_id, blocks, replace=None):
    result = await _deliver(client, target_chat_id, blocks, replace)
    if replace is not None:
        _consumed.discard(_message_key(replace))
    return result


async def send_now_playing_rich(
    client, chat_id, target_chat_id, photo, caption_html, replace=None
):
    _ = await _lang(chat_id)
    local_photo = await _download_photo_if_url(photo)
    resolved_photo = local_photo or photo
    dur = db[chat_id][0].get("dur") if db.get(chat_id) else None
    blocks = await build_now_playing_blocks(_, resolved_photo, caption_html, chat_id, played="00:00", dur=dur, playing=True)
    msg = await _deliver(client, target_chat_id, blocks, replace)
    if db.get(chat_id):
        db[chat_id][0]["np_photo"] = resolved_photo
        db[chat_id][0]["np_caption"] = caption_html
    return msg


def build_queue_blocks(_, caption_html, chat_id, qid):
    blocks = html_to_rich_blocks(caption_html)
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="▷ Play Now",
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data=f"ADMIN PlayNow|{chat_id}_{qid}",
                ),
            ]
        )
    )
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="» Skip",
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data=f"ADMIN Skip|{chat_id}",
                ),
                types.RichMessageButton(
                    text="⟲ End",
                    style=enums.ButtonStyle.DANGER,
                    callback_data=f"ADMIN Stop|{chat_id}",
                ),
            ]
        )
    )
    return blocks


async def send_queue_rich(
    client, chat_id, target_chat_id, caption_html, qid, replace=None
):
    _ = await _lang(chat_id)
    blocks = build_queue_blocks(_, caption_html, chat_id, qid)
    return await _deliver(client, target_chat_id, blocks, replace)


async def release_mystic(mystic):
    if mystic is None:
        return
    key = _message_key(mystic)
    if key in _consumed:
        _consumed.discard(key)
        return
    try:
        await mystic.delete()
    except Exception:
        pass


async def update_now_playing_progress(mystic, chat_id, played, dur, playing=True):
    info = db.get(chat_id)
    if not info:
        return None
    photo = info[0].get("np_photo")
    caption_html = info[0].get("np_caption")
    if not photo or not caption_html:
        return None
    _ = await _lang(chat_id)
    blocks = await build_now_playing_blocks(_, photo, caption_html, chat_id, played, dur, playing)
    return await _edit_rich(mystic, blocks)


async def set_now_playing_state(chat_id, playing):
    info = db.get(chat_id)
    if not info:
        return None
    mystic = info[0].get("mystic")
    photo = info[0].get("np_photo")
    caption_html = info[0].get("np_caption")
    if not mystic or not photo or not caption_html:
        return None
    played = seconds_to_min(info[0].get("played", 0)) or "00:00"
    dur = info[0].get("dur")
    _ = await _lang(chat_id)
    blocks = await build_now_playing_blocks(_, photo, caption_html, chat_id, played, dur, playing)
    try:
        return await _edit_rich(mystic, blocks)
    except Exception:
        return None


async def update_now_playing_markup(client, chat_id: int, playing: bool = True):
    tracks = db.get(chat_id)
    if not tracks:
        return
    cur = tracks[0]
    photo = cur.get("np_photo")
    caption = cur.get("np_caption")
    dur = cur.get("dur")
    msg_id = cur.get("mystic")

    if not msg_id or not caption:
        return

    _ = await _lang(chat_id)
    blocks = await build_now_playing_blocks(
        _, photo, caption, chat_id, played="00:00", dur=dur, playing=playing
    )
    rich = types.InputRichMessage(blocks=blocks)
    try:
        if isinstance(msg_id, types.Message):
            await msg_id.edit_text(rich_message=rich)
        else:
            await client.edit_message_text(
                chat_id=chat_id, message_id=msg_id, rich_message=rich
            )
    except Exception:
        try:
            plain = _strip_photo(blocks)
            if isinstance(msg_id, types.Message):
                await msg_id.edit_text(rich_message=types.InputRichMessage(blocks=plain))
            else:
                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    rich_message=types.InputRichMessage(blocks=plain),
                )
        except Exception:
            pass


def rich_autoplay_mood_blocks(caption_html: str):
    blocks = html_to_rich_blocks(caption_html)
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="✨ Chill",
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data="songconfig_mood:chill",
                ),
                types.RichMessageButton(
                    text="⚡ Party",
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data="songconfig_mood:party",
                ),
            ]
        )
    )
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="💔 Sad",
                    style=enums.ButtonStyle.DANGER,
                    callback_data="songconfig_mood:sad",
                ),
                types.RichMessageButton(
                    text="💖 Romantic",
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data="songconfig_mood:romantic",
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
                    callback_data="close_panel",
                )
            ]
        )
    )
    return blocks


def rich_autoplay_language_blocks(caption_html: str):
    blocks = html_to_rich_blocks(caption_html)
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="🇮🇳 Hindi",
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data="songconfig_language:hindi",
                ),
                types.RichMessageButton(
                    text="🌐 English",
                    style=enums.ButtonStyle.SUCCESS,
                    callback_data="songconfig_language:english",
                ),
            ]
        )
    )
    blocks.append(
        types.InputRichBlockButtons(
            buttons=[
                types.RichMessageButton(
                    text="🎸 Punjabi",
                    style=enums.ButtonStyle.DANGER,
                    callback_data="songconfig_language:punjabi",
                ),
                types.RichMessageButton(
                    text="💫 Haryanvi",
                    style=enums.ButtonStyle.PRIMARY,
                    callback_data="songconfig_language:haryanvi",
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
                    callback_data="close_panel",
                )
            ]
        )
    )
    return blocks