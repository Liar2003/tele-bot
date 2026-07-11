import os, aiohttp, asyncio, logging, shutil
from telegram import Update
from telegram.ext import ContextTypes
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename
from config import DOWNLOAD_DIR, MAX_FILE_SIZE
from bot.utils import format_bytes

async def process_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, status_msg, user_client: TelegramClient):
    try:
        # ----- 1. Fetch file info -----
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    await status_msg.edit_text(f"❌ URL returned {resp.status}")
                    return
                content_length = resp.headers.get("Content-Length")
                if not content_length:
                    await status_msg.edit_text("❌ Cannot determine file size (no Content-Length).")
                    return
                file_size = int(content_length)
                if file_size > MAX_FILE_SIZE:
                    await status_msg.edit_text(f"❌ File too large ({format_bytes(file_size)}). Max {format_bytes(MAX_FILE_SIZE)}.")
                    return
                # Extract filename from URL or Content-Disposition
                cd = resp.headers.get("Content-Disposition")
                filename = None
                if cd and "filename=" in cd:
                    filename = cd.split("filename=")[-1].strip('" ')
                if not filename:
                    filename = url.split("/")[-1].split("?")[0] or "file"
        
        # ----- 2. Download with progress -----
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        await status_msg.edit_text(f"⬇️ Downloading {filename} ({format_bytes(file_size)}) ...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await status_msg.edit_text(f"❌ Download failed ({resp.status})")
                    return
                with open(file_path, "wb") as f:
                    downloaded = 0
                    last_update = 0
                    async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded - last_update > 5 * 1024 * 1024:  # update every 5MB
                            pct = downloaded / file_size * 100
                            await status_msg.edit_text(
                                f"⬇️ Downloading {filename} … {pct:.0f}% ({format_bytes(downloaded)}/{format_bytes(file_size)})"
                            )
                            last_update = downloaded
        await status_msg.edit_text(f"⬇️ Downloaded {filename}. Uploading to Telegram...")

        # ----- 3. Upload via user account with progress callback -----
        async def progress_callback(current, total):
            pct = current / total * 100
            # Throttle updates to avoid flooding
            if not hasattr(progress_callback, "last_update"):
                progress_callback.last_update = 0
            if current - progress_callback.last_update > 5 * 1024 * 1024:
                await status_msg.edit_text(
                    f"⬆️ Uploading {filename} … {pct:.0f}% ({format_bytes(current)}/{format_bytes(total)})"
                )
                progress_callback.last_update = current

        uploaded_file = await user_client.send_file(
            update.effective_chat.id,  # send to the same chat
            file_path,
            caption=f"📁 {filename}",
            progress_callback=progress_callback,
            attributes=[DocumentAttributeFilename(os.path.basename(filename))],
            force_document=True,
            part_size_kb=512,   # good for large files
        )

        # ----- 4. Success + cleanup -----
        await status_msg.edit_text(f"✅ Upload complete! File: `{filename}`", parse_mode="Markdown")
        # Optionally delete the local file
        os.remove(file_path)

    except asyncio.CancelledError:
        await status_msg.edit_text("❌ Operation cancelled.")
    except Exception as e:
        logging.exception("Upload failed")
        await status_msg.edit_text(f"❌ Error: {e}")
        # Cleanup partial file if exists
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
