import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import logging
import json

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# File to persist banned users data
DATA_FILE = "banned_users.json"

# Load banned users database
def load_banned_users():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers
                return {int(k): v for k, v in data.items()}
        return {}
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return {}

# Save banned users database
def save_banned_users():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(banned_users_db, f)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

# Initialize database
banned_users_db = load_banned_users()

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user and add them to our tracking database"""
    
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("⚠️ This command only works in groups/supergroups!")
        return
    
    # Check if user is admin
    try:
        user = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if user.status not in ['creator', 'administrator']:
            await update.message.reply_text("⛔ Only admins can use this command!")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking admin status: {str(e)}")
        return
    
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("Usage: /ban <user_id> or reply to a user's message")
        return
    
    try:
        chat_id = update.effective_chat.id
        
        # Get user to ban
        if update.message.reply_to_message:
            user_id = update.message.reply_to_message.from_user.id
            user_name = update.message.reply_to_message.from_user.first_name
        else:
            user_id = int(context.args[0])
            user_name = f"User {user_id}"
        
        # Ban the user
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        
        # Add to our database
        if chat_id not in banned_users_db:
            banned_users_db[chat_id] = []
        
        if user_id not in banned_users_db[chat_id]:
            banned_users_db[chat_id].append(user_id)
            save_banned_users()
        
        await update.message.reply_text(f"✅ {user_name} (ID: {user_id}) has been banned and added to tracking list!")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID! Please provide a numeric ID.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to ban: {str(e)}")

async def unban_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban all tracked users with real-time updates"""
    
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("⚠️ This command only works in groups/supergroups!")
        return
    
    # Check if user is admin
    try:
        user = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if user.status not in ['creator', 'administrator']:
            await update.message.reply_text("⛔ Only admins can use this command!")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking admin status: {str(e)}")
        return
    
    chat_id = update.effective_chat.id
    
    # Check if there are banned users
    if chat_id not in banned_users_db or not banned_users_db[chat_id]:
        await update.message.reply_text("ℹ️ No banned users found in tracking database.")
        return
    
    total_users = len(banned_users_db[chat_id])
    
    # Send initial message
    status_message = await update.message.reply_text(
        f"🔄 Starting unban process...\n"
        f"Total users to unban: {total_users}\n"
        f"Progress: 0/{total_users}\n\n"
        f"⏳ Please wait, this will take approximately {int(total_users * 1.5)} seconds..."
    )
    
    unbanned_count = 0
    failed_count = 0
    failed_users = []
    
    # Create a copy of the list to iterate
    users_to_unban = banned_users_db[chat_id].copy()
    
    for index, user_id in enumerate(users_to_unban, 1):
        try:
            # Unban the user
            await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            unbanned_count += 1
            
            # Remove from database
            banned_users_db[chat_id].remove(user_id)
            save_banned_users()
            
            # Update progress message every user
            await status_message.edit_text(
                f"🔄 Unbanning users...\n\n"
                f"✅ User {user_id} unbanned!\n\n"
                f"📊 Progress: {index}/{total_users}\n"
                f"✅ Unbanned: {unbanned_count}\n"
                f"❌ Failed: {failed_count}\n"
                f"⏳ Estimated time remaining: {int((total_users - index) * 1.5)}s"
            )
            
            # Add delay to avoid rate limits (required by Telegram)
            await asyncio.sleep(1.5)
            
        except Exception as e:
            failed_count += 1
            failed_users.append(f"User {user_id}: {str(e)[:50]}")
            
            # Update with error
            await status_message.edit_text(
                f"🔄 Unbanning users...\n\n"
                f"❌ Failed to unban user {user_id}\n"
                f"Error: {str(e)[:50]}\n\n"
                f"📊 Progress: {index}/{total_users}\n"
                f"✅ Unbanned: {unbanned_count}\n"
                f"❌ Failed: {failed_count}"
            )
            
            await asyncio.sleep(1.5)
    
    # Final summary
    summary = (
        f"✅ Unban process completed!\n\n"
        f"📊 Summary:\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Total processed: {total_users}\n"
        f"✅ Successfully unbanned: {unbanned_count}\n"
        f"❌ Failed: {failed_count}\n"
        f"━━━━━━━━━━━━━━━"
    )
    
    if failed_users:
        summary += f"\n\n❌ Failed users:\n" + "\n".join(failed_users[:10])  # Show first 10 failures
        if len(failed_users) > 10:
            summary += f"\n... and {len(failed_users) - 10} more"
    
    await status_message.edit_text(summary)

async def list_banned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all banned users being tracked"""
    
    chat_id = update.effective_chat.id
    
    if chat_id not in banned_users_db or not banned_users_db[chat_id]:
        await update.message.reply_text("ℹ️ No banned users in tracking database.")
        return
    
    total = len(banned_users_db[chat_id])
    users_list = "\n".join([f"• {user_id}" for user_id in banned_users_db[chat_id][:50]])
    
    message = f"📋 Banned users ({total}):\n\n{users_list}"
    
    if total > 50:
        message += f"\n\n... and {total - 50} more users"
    
    await update.message.reply_text(message)

async def add_banned_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually add user ID to banned list for unbanning later"""
    
    # Check if user is admin
    try:
        user = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if user.status not in ['creator', 'administrator']:
            await update.message.reply_text("⛔ Only admins can use this command!")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking admin status: {str(e)}")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /add_banned <user_id1> <user_id2> ...")
        return
    
    chat_id = update.effective_chat.id
    
    if chat_id not in banned_users_db:
        banned_users_db[chat_id] = []
    
    added = 0
    for user_id_str in context.args:
        try:
            user_id = int(user_id_str)
            if user_id not in banned_users_db[chat_id]:
                banned_users_db[chat_id].append(user_id)
                added += 1
        except ValueError:
            continue
    
    save_banned_users()
    await update.message.reply_text(f"✅ Added {added} user(s) to banned list!")

async def clear_banned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all banned users from tracking"""
    
    # Check if user is admin
    try:
        user = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if user.status not in ['creator', 'administrator']:
            await update.message.reply_text("⛔ Only admins can use this command!")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking admin status: {str(e)}")
        return
    
    chat_id = update.effective_chat.id
    
    if chat_id in banned_users_db:
        count = len(banned_users_db[chat_id])
        banned_users_db[chat_id] = []
        save_banned_users()
        await update.message.reply_text(f"✅ Cleared {count} users from banned list!")
    else:
        await update.message.reply_text("ℹ️ No banned users to clear.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with commands"""
    
    help_text = (
        "🤖 *Unban Bot - Automated Mass Unbanner*\n\n"
        "*Admin Commands:*\n"
        "━━━━━━━━━━━━━━━\n"
        "/ban <user\\_id> - Ban a user and track them\n"
        "/unban\\_all - Unban ALL tracked users automatically\n"
        "/list\\_banned - Show all tracked banned users\n"
        "/add\\_banned <id1> <id2> - Add user IDs to unban list\n"
        "/clear\\_banned - Clear tracking database\n\n"
        "*How it works:*\n"
        "1️⃣ Ban users with /ban command (they get tracked)\n"
        "2️⃣ Use /unban\\_all to automatically unban everyone\n"
        "3️⃣ Watch real-time updates as each user is unbanned!\n\n"
        "⚠️ *Important:*\n"
        "• Bot needs admin rights with 'ban users' permission\n"
        "• Process takes ~1.5 seconds per user (Telegram limits)\n"
        "• You'll see live progress updates\n"
        "• All data is saved automatically\n\n"
        "💡 *Tip:* You can add multiple user IDs at once:\n"
        "`/add_banned 123456 789012 345678`"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot"""
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not set!")
        return
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban_all", unban_all))
    app.add_handler(CommandHandler("list_banned", list_banned))
    app.add_handler(CommandHandler("add_banned", add_banned_user))
    app.add_handler(CommandHandler("clear_banned", clear_banned))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Start bot
    logger.info("✅ Bot is running on Railway...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
