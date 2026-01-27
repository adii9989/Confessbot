# This is database.py
import pymongo 
from datetime import datetime, timezone

# --- Guild/Channel Configuration ---

async def set_confession_channel(db, guild_id, channel_id):
    """Registers the main confession channel for a guild."""
    await db.guild_config.update_one(
        {"_id": guild_id},
        {"$set": {"channel_id": channel_id}},
        upsert=True
    )

async def get_confession_channel(db, guild_id):
    """Gets the configured confession channel for a guild."""
    return await db.guild_config.find_one({"_id": guild_id})

async def is_confession_channel(db, channel_id):
    """Checks if a channel ID is registered as a confession channel."""
    doc = await db.guild_config.find_one({"channel_id": channel_id})
    return doc is not None

# --- Confession Index (Counter) ---

async def set_confession_index(db, channel_id, number):
    """Sets the confession counter for a SPECIFIC CHANNEL."""
    await db.channel_counters.update_one(
        {"_id": channel_id},
        {"$set": {"index": number - 1}},
        upsert=True
    )

async def get_next_confession_index(db, channel_id):
    """Increments and returns the next confession index."""
    result = await db.channel_counters.find_one_and_update(
        {"_id": channel_id},
        {"$inc": {"index": 1}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )
    return result.get("index", 1) 

# --- Log Channel Configuration ---

async def set_log_channel(db, source_channel_id, target_guild_id, target_channel_id):
    """Maps a SOURCE confession channel to a TARGET log channel."""
    await db.log_config.update_one(
        {"_id": source_channel_id},
        {"$set": {
            "target_guild_id": target_guild_id,
            "target_channel_id": target_channel_id
        }},
        upsert=True
    )

async def get_log_channel(db, source_channel_id):
    """Gets the log channel destination."""
    return await db.log_config.find_one({"_id": source_channel_id})


# --- Confession Mapping & Backup ---

async def save_confession_map(db, main_channel_id, index, actual_channel_id, message_id, type_):
    """Saves the mapping of index -> message ID."""
    await db.confession_map.update_one(
        {"channel_id": main_channel_id, "index": index},
        {
            "$set": {
                "actual_channel_id": actual_channel_id, 
                "message_id": message_id, 
                "type": type_
            }
        },
        upsert=True
    )

async def get_confession_map(db, main_channel_id, index):
    """Retrieves message details by main channel and index."""
    return await db.confession_map.find_one({"channel_id": main_channel_id, "index": index})

async def save_full_confession_log(db, channel_id, index, user_id, content, attachment_url):
    """Saves the FULL content and AUTHOR of a confession."""
    # --- FIX: Use Python datetime instead of Mongo command ---
    await db.full_logs.insert_one({
        "channel_id": channel_id,
        "index": index,
        "user_id": user_id,
        "content": content,
        "attachment_url": attachment_url,
        "timestamp": datetime.now(timezone.utc)
    })


