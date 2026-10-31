import asyncio
import random

from pyrogram import Client, filters
from pyrogram.raw.functions.messages import DeleteHistory
from pyrogram.types import Message

from Oneforall import app
from Oneforall import userbot as us
from Oneforall.core.userbot import assistants


@app.on_message(filters.command(["sg", "stalk"]))
async def sg(client: Client, message: Message):
    # 1. Target user extract karna (Reply, ID, Username, ya Mention)
    user = None
    if message.reply_to_message:
        if message.reply_to_message.from_user:
            user = message.reply_to_message.from_user
        else:
            return await message.reply("Kisi user ke message par reply karo (channel/anon admin par nahi).")
    elif len(message.command) > 1:
        # Check text mention entity agar bina username ka mention ho
        if message.entities and len(message.entities) > 1:
            for entity in message.entities:
                if entity.type.name == "TEXT_MENTION" and entity.user:
                    user = entity.user
                    break

        # Normal Username ya User ID se fetch karna
        if not user:
            user_input = message.text.split(None, 1)[1].strip()
            # Agar user ID di hai to integer me convert karo
            if user_input.isdigit() or (user_input.startswith("-") and user_input[1:].isdigit()):
                user_input = int(user_input)

            try:
                user = await client.get_users(user_input)
            except Exception:
                return await message.reply("<code>User nahi mila! Valid ID/Username ya Tag use karo.</code>")
    else:
        return await message.reply("<b>Usage:</b>\n• <code>/sg @username</code>\n• <code>/sg user_id</code>\n• Reply to a user's message with <code>/sg</code>")

    if not user:
        return await message.reply("<code>User details fetch nahi ho paayi!</code>")

    lol = await message.reply("<code>Searching history from SangMata...</code>")

    # Userbot check
    if 1 in assistants:
        ubot = us.one
    else:
        return await lol.edit("<code>Userbot assistant available nahi hai!</code>")

    bo = ["sangmata_bot", "sangmata_beta_bot"]
    sg_bot = random.choice(bo)

    try:
        # SangMata ko user ki ID bhejna
        sent = await ubot.send_message(sg_bot, f"{user.id}")
        await sent.delete()
    except Exception as e:
        return await lol.edit(f"Error: {e}")

    # SangMata response aane ke liye wait loop (max 7-8 seconds)
    response_text = None
    for _ in range(8):
        await asyncio.sleep(1)
        async for stalk in ubot.get_chat_history(sg_bot, limit=3):
            if stalk.from_user and stalk.from_user.is_bot and stalk.text:
                response_text = stalk.text
                break
        if response_text:
            break

    if response_text:
        await message.reply(f"<b>Name History for {user.first_name}:</b>\n\n{response_text}")
    else:
        await message.reply("<code>SangMata bot ne response nahi diya ya bot offline hai.</code>")

    # Chat history clean karna
    try:
        user_info = await ubot.resolve_peer(sg_bot)
        await ubot.send(DeleteHistory(peer=user_info, max_id=0, revoke=True))
    except Exception:
        pass

    await lol.delete()