
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
import uuid

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "7412494384:AAHj83iUAZdq3kjMBURF3hglOHX3j1rf7go"  # Replace with your bot token
API_ID = "26525481"  # Replace with your API ID
API_HASH = "f1cc42e92c80367009171e28d04ed2ee"  # Replace with your API hash
DATA_FILE = "user_data.json"

async def process_specific_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process and store specific group IDs for sending messages"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    text = update.message.text.strip()
    
    try:
        logger.info(f"User {user_id} is processing specific groups with text: {text}")
        def is_valid_group_id(gid):
            gid = gid.strip()
            if not gid:
                return False
            # Accept negative and positive integers
            if gid.startswith('-'):
                return gid[1:].isdigit()
            return gid.isdigit()

        group_ids = [int(gid.strip()) for gid in text.split(',') if is_valid_group_id(gid)]
        if not group_ids:
            await update.message.reply_text("❌ Please enter at least one valid group ID, separated by commas.")
            return

        # Validate that the group IDs exist in user's groups
        all_groups = user_session.get('all_groups', [])
        group_dict = {gid: name for gid, name in all_groups}
        
        valid_groups = []
        invalid_groups = []
        
        for gid in group_ids:
            if gid in group_dict:
                valid_groups.append(gid)
            else:
                invalid_groups.append(gid)
        
        if not valid_groups:
            logger.info(f"User {user_id} provided no valid specific group IDs. Invalid: {invalid_groups}")
            await update.message.reply_text("❌ None of the provided group IDs are valid. Please check and try again.")
            return
        logger.info(f"User {user_id} selected specific groups: {valid_groups}, invalid: {invalid_groups}")
        user_session['group_selection_mode'] = 'specific'
        user_session['specific_groups'] = valid_groups
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        valid_names = [group_dict[gid] for gid in valid_groups]
        success_text = f"✅ **Specific groups selected!**\n\n**Selected Groups:**\n" + '\n'.join(f"• {name}" for name in valid_names)
        if invalid_groups:
            success_text += f"\n\n⚠️ **Invalid IDs ignored:** {', '.join(map(str, invalid_groups))}"
        await update.message.reply_text(success_text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing group IDs: {str(e)}")

async def process_exclude_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process and store excluded group IDs"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    text = update.message.text.strip()
    
    try:
        logger.info(f"User {user_id} is processing exclude groups with text: {text}")
        def is_valid_group_id(gid):
            gid = gid.strip()
            if not gid:
                return False
            # Accept negative and positive integers
            if gid.startswith('-'):
                return gid[1:].isdigit()
            return gid.isdigit()

        group_ids = [int(gid.strip()) for gid in text.split(',') if is_valid_group_id(gid)]
        if not group_ids:
            await update.message.reply_text("❌ Please enter at least one valid group ID, separated by commas.")
            return

        # Validate that the group IDs exist in user's groups
        all_groups = user_session.get('all_groups', [])
        group_dict = {gid: name for gid, name in all_groups}
        
        valid_groups = []
        invalid_groups = []
        
        for gid in group_ids:
            if gid in group_dict:
                valid_groups.append(gid)
            else:
                invalid_groups.append(gid)
        
        if not valid_groups:
            logger.info(f"User {user_id} provided no valid exclude group IDs. Invalid: {invalid_groups}")
            await update.message.reply_text("❌ None of the provided group IDs are valid. Please check and try again.")
            return
        logger.info(f"User {user_id} excluded groups: {valid_groups}, invalid: {invalid_groups}")
        user_session['group_selection_mode'] = 'exclude'
        user_session['excluded_groups'] = valid_groups
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        valid_names = [group_dict[gid] for gid in valid_groups]
        target_count = len(all_groups) - len(valid_groups)
        success_text = f"✅ **Exclude groups set!**\n\n**Excluded Groups:**\n" + '\n'.join(f"• {name}" for name in valid_names)
        success_text += f"\n\n📊 **Will send to {target_count} other groups.**"
        if invalid_groups:
            success_text += f"\n\n⚠️ **Invalid IDs ignored:** {', '.join(map(str, invalid_groups))}"
        await update.message.reply_text(success_text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing group IDs: {str(e)}")
        await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
        return
    user_session['login_state'] = 'waiting_group_ids'
    bot_manager.save_user_data()
    await update.message.reply_text(
        "✅ **Select Groups**\n\n"
        "Reply with the IDs of the groups you want to send messages to, separated by commas.\n"
        "Example: 123456789,987654321\n\n"
        "You can view group IDs using '👥 View Groups'.\n"
        "Type /cancel to cancel."
    )
async def handle_view_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle view groups request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    if not user_session.get('session_string'):
        await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
        return

    try:
        session_string = user_session.get('session_string')
        if not session_string:
            await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
            return
        client = TelegramClient(
            StringSession(session_string),
            API_ID,
            API_HASH,
            device_model="PC",
            system_version="Windows 11",
            app_version="1.0.0",
            system_lang_code="en"
        )
        try:
            await client.start()
        except Exception as e:
            logger.error(f"Session string invalid or expired for user {user_id}: {e}")
            user_session['session_string'] = None
            bot_manager.save_user_data()
            await update.message.reply_text(
                "❌ Your session has expired or is invalid. Please login again using '📱 Login with Phone'."
            )
            return
        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                groups.append((dialog.id, dialog.name))
        # Cache groups for later use
        user_session['all_groups'] = groups
        bot_manager.save_user_data()
        await client.disconnect()
        if not groups:
            await update.message.reply_text("You have not joined any groups or channels.")
        else:
            # Get current selection mode info
            mode = user_session.get('group_selection_mode', 'all')
            mode_text = {
                'all': 'All Groups',
                'specific': f"Specific Groups ({len(user_session.get('specific_groups', []))} selected)",
                'exclude': f"Exclude Groups ({len(user_session.get('excluded_groups', []))} excluded)"
            }
            group_list = '\n'.join(f"• {name} (ID: {gid})" for gid, name in groups[:50])
            more = f"\n...and {len(groups)-50} more" if len(groups) > 50 else ""
            status_text = f"\n\n📊 **Current Mode:** {mode_text[mode]}\n\nUse '⚙️ Group Settings' to configure targeting options."
            await update.message.reply_text(f"👥 **Your Groups/Channels:**\n\n{group_list}{more}{status_text}")
    except Exception as e:
        logger.error(f"Error fetching groups: {e}")
        await update.message.reply_text(f"❌ Error fetching groups: {str(e)}")

async def handle_group_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group settings menu"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if not user_session.get('session_string'):
        await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
        return
    
    logger.info(f"User {user_id} opened group settings. Current mode: {user_session.get('group_selection_mode', 'all')}")
    keyboard = [
        [KeyboardButton("🌐 Send to All Groups"), KeyboardButton("🎯 Select Specific Groups")],
        [KeyboardButton("❌ Exclude Groups"), KeyboardButton("📋 View Current Settings")],
        [KeyboardButton("🔄 Refresh Groups"), KeyboardButton("⬅️ Back to Main")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    current_mode = user_session.get('group_selection_mode', 'all')
    mode_descriptions = {
        'all': '🌐 Sending to ALL joined groups',
        'specific': f'🎯 Sending to {len(user_session.get("specific_groups", []))} specific groups',
        'exclude': f'❌ Excluding {len(user_session.get("excluded_groups", []))} groups'
    }
    settings_text = f"""
⚙️ **Group Settings**

**Current Mode:** {mode_descriptions[current_mode]}

**Available Options:**
• **Send to All Groups** - Send messages to all your joined groups
• **Select Specific Groups** - Choose only specific groups to send to
• **Exclude Groups** - Send to all groups except selected ones
• **View Current Settings** - See detailed current configuration

Choose an option below:
    """
    await update.message.reply_text(settings_text, reply_markup=reply_markup)

async def handle_send_to_all_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set mode to send to all groups"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    logger.info(f"User {user_id} set group_selection_mode to ALL")
    user_session['group_selection_mode'] = 'all'
    user_session['specific_groups'] = []
    user_session['excluded_groups'] = []
    bot_manager.save_user_data()
    await update.message.reply_text(
        "✅ **Mode set to: Send to All Groups**\n\n"
        "Messages will be sent to all your joined groups and channels.\n\n"
        "Use '⚙️ Group Settings' to change this setting."
    )

async def handle_select_specific_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle specific groups selection"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if not user_session.get('all_groups'):
        await update.message.reply_text("❌ Please use '👥 View Groups' first to load your groups.")
        return
    logger.info(f"User {user_id} is entering select specific groups mode.")
    user_session['login_state'] = 'waiting_specific_groups'
    bot_manager.save_user_data()
    groups = user_session['all_groups']
    current_specific = user_session.get('specific_groups', [])
    current_names = [name for gid, name in groups if gid in current_specific]
    current_text = f"\n\n**Currently selected:** {', '.join(current_names) if current_names else 'None'}"
    group_list = '\n'.join(f"• {name} (ID: {gid})" for gid, name in groups[:30])
    more = f"\n...and {len(groups)-30} more" if len(groups) > 30 else ""
    await update.message.reply_text(
        f"🎯 **Select Specific Groups**\n\n"
        f"Enter the IDs of groups you want to send messages to, separated by commas.\n\n"
        f"**Available Groups:**\n{group_list}{more}{current_text}\n\n"
        f"Example: 123456789,987654321\n\n"
        f"Type /cancel to cancel."
    )

async def handle_exclude_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle exclude groups selection"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if not user_session.get('all_groups'):
        await update.message.reply_text("❌ Please use '👥 View Groups' first to load your groups.")
        return
    logger.info(f"User {user_id} is entering exclude groups mode.")
    user_session['login_state'] = 'waiting_exclude_groups'
    bot_manager.save_user_data()
    groups = user_session['all_groups']
    current_excluded = user_session.get('excluded_groups', [])
    current_names = [name for gid, name in groups if gid in current_excluded]
    current_text = f"\n\n**Currently excluded:** {', '.join(current_names) if current_names else 'None'}"
    group_list = '\n'.join(f"• {name} (ID: {gid})" for gid, name in groups[:30])
    more = f"\n...and {len(groups)-30} more" if len(groups) > 30 else ""
    await update.message.reply_text(
        f"❌ **Exclude Groups**\n\n"
        f"Enter the IDs of groups you want to EXCLUDE from sending, separated by commas.\n\n"
        f"**Available Groups:**\n{group_list}{more}{current_text}\n\n"
        f"Example: 123456789,987654321\n\n"
        f"Type /cancel to cancel."
    )

async def handle_view_current_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current group settings"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    mode = user_session.get('group_selection_mode', 'all')
    all_groups = user_session.get('all_groups', [])
    specific_groups = user_session.get('specific_groups', [])
    excluded_groups = user_session.get('excluded_groups', [])
    
    # Get group names
    group_dict = {gid: name for gid, name in all_groups}
    
    if mode == 'all':
        target_text = f"**All Groups** ({len(all_groups)} total)"
        details = "✅ Messages will be sent to all your joined groups and channels."
    elif mode == 'specific':
        specific_names = [group_dict.get(gid, f"ID: {gid}") for gid in specific_groups]
        target_text = f"**Specific Groups** ({len(specific_groups)} selected)"
        details = f"✅ Messages will be sent to:\n" + '\n'.join(f"• {name}" for name in specific_names[:10])
        if len(specific_names) > 10:
            details += f"\n• ...and {len(specific_names)-10} more"
    else:  # exclude
        excluded_names = [group_dict.get(gid, f"ID: {gid}") for gid in excluded_groups]
        target_groups = len(all_groups) - len(excluded_groups)
        target_text = f"**Exclude Mode** ({target_groups} groups targeted)"
        details = f"❌ Messages will NOT be sent to:\n" + '\n'.join(f"• {name}" for name in excluded_names[:10])
        if len(excluded_names) > 10:
            details += f"\n• ...and {len(excluded_names)-10} more"
        details += f"\n\n✅ Will send to {target_groups} other groups."
    
    settings_text = f"""
📋 **Current Group Settings**

**Mode:** {target_text}

{details}

Use '⚙️ Group Settings' to modify these settings.
    """
    
    await update.message.reply_text(settings_text)

async def handle_refresh_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh the groups list"""
    await update.message.reply_text("🔄 Refreshing groups...")
    await handle_view_groups(update, context)

async def handle_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu"""
    await start_command(update, context)

class TelegramBotManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(jobstores={'default': MemoryJobStore()})
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.temp_login: Dict[str, Dict[str, Any]] = {}  # Store temp login state per user
        self.password = None  # Store bot access password
        self.admin_user_id = None  # Store admin user id (set on first login)
        self.load_user_data()
        
    def load_user_data(self):
        """Load user data and password from JSON file"""
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.user_sessions = data.get('sessions', {})
                    self.password = data.get('bot_password', 'admin12323')
                    self.admin_user_id = data.get('admin_user_id', None)
            else:
                self.password = 'admin12323'
        except Exception as e:
            logger.error(f"Error loading user data: {e}")
            self.user_sessions = {}
            self.password = 'admin12323'
    
    def save_user_data(self):
        """Save user data and password to JSON file"""
        try:
            # Create a copy without temp_client for JSON serialization
            sessions_copy = {}
            for user_id, session in self.user_sessions.items():
                session_copy = session.copy()
                if 'temp_client' in session_copy:
                    del session_copy['temp_client']  # Remove non-serializable client
                sessions_copy[user_id] = session_copy
            data = {
                'sessions': sessions_copy,
                'bot_password': self.password or 'admin12323',
                'admin_user_id': self.admin_user_id,
                'last_updated': datetime.now().isoformat()
            }
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving user data: {e}")

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the bot password"""
        return password == (self.password or 'admin12323')

    def set_password(self, new_password: str):
        """Set a new bot password"""
        self.password = new_password
        self.save_user_data()

    def set_admin(self, user_id: str):
        """Set the admin user id (first successful login)"""
        if not self.admin_user_id:
            self.admin_user_id = user_id
            self.save_user_data()
    
    def get_user_session(self, user_id: str) -> Dict[str, Any]:
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'status': 'inactive',
                'phone': None,
                'session_string': None,
                'message_text': None,
                'interval_minutes': 30,
                'job_id': None,
                'login_state': 'idle',  # idle, waiting_phone, waiting_code, waiting_password
                'phone_code_hash': None,
                'groups_sent': [],
                'last_activity': datetime.now().isoformat(),
                'group_selection_mode': 'all',  # all, specific, exclude
                'specific_groups': [],  # List of group IDs to include
                'excluded_groups': [],  # List of group IDs to exclude
                'all_groups': []  # Cache of all available groups
            }
        return self.user_sessions[user_id]
    
    def set_temp_client(self, user_id: str, client: TelegramClient):
        """Store temporary client for user"""
        self.temp_clients[user_id] = client
    
    def get_temp_client(self, user_id: str) -> Optional[TelegramClient]:
        """Get temporary client for user"""
        return self.temp_clients.get(user_id)
    
    def remove_temp_client(self, user_id: str):
        """Remove temporary client for user"""
        if user_id in self.temp_clients:
            del self.temp_clients[user_id]

# Initialize bot manager
bot_manager = TelegramBotManager()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    # If not authenticated, ask for password
    if not user_session.get('authenticated', False):
        user_session['login_state'] = 'waiting_bot_password'
        bot_manager.save_user_data()
        await update.message.reply_text(
            "🔒 This bot is password protected.\n\nPlease enter the access password to continue:")
        return
    keyboard = [
        [KeyboardButton("📱 Login with Phone"), KeyboardButton("📊 Status")],
        [KeyboardButton("✏️ Set Message"), KeyboardButton("⏰ Set Interval")],
        [KeyboardButton("👥 View Groups"), KeyboardButton("⚙️ Group Settings")],
        [KeyboardButton("▶️ Start Sending"), KeyboardButton("⏸️ Pause")],
        [KeyboardButton("⏹️ Stop"), KeyboardButton("📋 View Logs")]
    ]
    # Only admin can see change password
    if bot_manager.admin_user_id == user_id:
        keyboard.append([KeyboardButton("🔑 Change Password")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome_text = """
🤖 **Telegram Auto-Messenger Bot**

Welcome! This bot helps you send messages to your Telegram groups automatically.

**Features:**
• Login with your own Telegram account
• Set custom messages and intervals
• Advanced group targeting (All/Specific/Exclude)
• Control sending: start, pause, resume, stop
• View logs and status

**Quick Start:**
1. Click "📱 Login with Phone"
2. Enter your phone number
3. Enter the verification code
4. Set your message and interval
5. Configure group settings
6. Start sending!

Choose an option below:
    """
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_login_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone login request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if user_session['session_string']:
        await update.message.reply_text("✅ You're already logged in! Use other commands to manage your session.")
        return
    
    user_session['login_state'] = 'waiting_phone'
    bot_manager.save_user_data()
    
    await update.message.reply_text(
        "📱 **Phone Login**\n\n"
        "Please enter your phone number in international format.\n"
        "Example: +1234567890\n\n"
        "Type /cancel to cancel the login process."
    )

async def handle_set_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle set message request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if not user_session['session_string']:
        await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
        return
    
    user_session['login_state'] = 'waiting_message'
    bot_manager.save_user_data()
    
    await update.message.reply_text(
        "✏️ **Set Message**\n\n"
        "Please enter the message you want to send to your groups.\n"
        "This message will be sent automatically at your specified interval.\n\n"
        "Type /cancel to cancel."
    )

async def handle_set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle set interval request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if not user_session['session_string']:
        await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
        return
    
    user_session['login_state'] = 'waiting_interval'
    bot_manager.save_user_data()
    
    await update.message.reply_text(
        "⏰ **Set Interval**\n\n"
        "Please enter the interval in minutes between messages.\n"
        "Example: 30 (for 30 minutes)\n\n"
        f"Current interval: {user_session['interval_minutes']} minutes\n\n"
        "Type /cancel to cancel."
    )

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle status request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    status_emoji = {
        'active': '🟢',
        'paused': '🟡',
        'inactive': '🔴'
    }
    
    # Get group selection info
    mode = user_session.get('group_selection_mode', 'all')
    all_groups = user_session.get('all_groups', [])
    specific_groups = user_session.get('specific_groups', [])
    excluded_groups = user_session.get('excluded_groups', [])
    
    if mode == 'all':
        group_info = f"All groups ({len(all_groups)})"
    elif mode == 'specific':
        group_info = f"Specific groups ({len(specific_groups)} selected)"
    else:  # exclude
        target_count = len(all_groups) - len(excluded_groups)
        group_info = f"Exclude mode ({target_count} targeted)"
    
    status_text = f"""
📊 **Your Status**

**Account:** {'✅ Logged in' if user_session['session_string'] else '❌ Not logged in'}
**Phone:** {user_session['phone'] or 'Not set'}
**Status:** {status_emoji.get(user_session['status'], '🔴')} {user_session['status'].title()}
**Message:** {'✅ Set' if user_session['message_text'] else '❌ Not set'}
**Interval:** {user_session['interval_minutes']} minutes
**Group targeting:** {group_info}
**Groups sent:** {len(user_session['groups_sent'])}
**Last activity:** {user_session['last_activity'][:16] if user_session['last_activity'] else 'Never'}
    """
    
    await update.message.reply_text(status_text)

async def handle_start_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle start sending request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if not user_session['session_string']:
        await update.message.reply_text("❌ Please login first using '📱 Login with Phone'")
        return
    
    if not user_session['message_text']:
        await update.message.reply_text("❌ Please set a message first using '✏️ Set Message'")
        return
    
    if user_session['status'] == 'active':
        await update.message.reply_text("⚠️ Sending is already active!")
        return
    
    # Start the scheduler job
    job_id = f"user_{user_id}_job"
    
    try:
        bot_manager.scheduler.add_job(
            send_message_job,
            'interval',
            minutes=user_session['interval_minutes'],
            id=job_id,
            args=[user_id],
            replace_existing=True
        )
        user_session['status'] = 'active'
        user_session['job_id'] = job_id
        user_session['last_activity'] = datetime.now().isoformat()
        bot_manager.save_user_data()
        # Send the first message immediately
        await send_message_job(user_id)
        await update.message.reply_text(
            f"▶️ **Started sending!**\n\n"
            f"Message: {user_session['message_text'][:50]}...\n"
            f"Interval: Every {user_session['interval_minutes']} minutes\n\n"
            f"Use '⏸️ Pause' or '⏹️ Stop' to control sending."
        )
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        await update.message.reply_text(f"❌ Error starting scheduler: {str(e)}")

async def handle_pause_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pause sending request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if user_session['status'] != 'active':
        await update.message.reply_text("⚠️ Sending is not active!")
        return
    
    user_session['status'] = 'paused'
    user_session['last_activity'] = datetime.now().isoformat()
    bot_manager.save_user_data()
    
    await update.message.reply_text("⏸️ **Sending paused!**\n\nUse '▶️ Start Sending' to resume.")

async def handle_stop_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stop sending request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    if user_session['status'] == 'inactive':
        await update.message.reply_text("⚠️ Sending is already inactive!")
        return
    
    # Remove scheduler job
    if user_session['job_id']:
        try:
            bot_manager.scheduler.remove_job(user_session['job_id'])
        except:
            pass
    
    user_session['status'] = 'inactive'
    user_session['job_id'] = None
    user_session['last_activity'] = datetime.now().isoformat()
    bot_manager.save_user_data()
    
    await update.message.reply_text("⏹️ **Sending stopped!**\n\nUse '▶️ Start Sending' to start again.")

async def handle_view_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle view logs request"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    logs_text = f"""
📋 **Your Logs**

**Total groups sent:** {len(user_session['groups_sent'])}
**Status:** {user_session['status'].title()}
**Last activity:** {user_session['last_activity'][:16] if user_session['last_activity'] else 'Never'}

**Recent groups:**
{chr(10).join(user_session['groups_sent'][-10:]) if user_session['groups_sent'] else 'No groups sent yet'}
    """
    
    await update.message.reply_text(logs_text)

async def send_message_job(user_id: str):
    """Background job to send messages"""
    user_session = bot_manager.get_user_session(user_id)
    
    if user_session['status'] != 'active':
        return
    
    if not user_session['session_string'] or not user_session['message_text']:
        return
    
    try:
        # Create Telethon client with user-specific session string
        client = TelegramClient(
            StringSession(user_session['session_string']),
            API_ID,
            API_HASH,
            device_model="PC",
            system_version="Windows 11",
            app_version="1.0.0",
            system_lang_code="en"
        )
        try:
            await client.start()
        except Exception as e:
            logger.error(f"Session string invalid or expired for user {user_id}: {e}")
            user_session['session_string'] = None
            user_session['status'] = 'inactive'
            bot_manager.save_user_data()
            # Optionally, notify the user here if you have a way to send a message
            return
        # Determine target groups based on selection mode
        mode = user_session.get('group_selection_mode', 'all')
        specific_groups = user_session.get('specific_groups', [])
        excluded_groups = user_session.get('excluded_groups', [])
        logger.info(f"User {user_id} mode: {mode}, specific: {specific_groups}, excluded: {excluded_groups}")
        groups_found = 0
        messages_sent = 0
        skipped_groups = 0
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                groups_found += 1
                logger.info(f"[SCHEDULER] User {user_id}: Found group: {dialog.name} (ID: {dialog.id})")
                # Apply group filtering based on mode
                should_send = False
                if mode == 'all':
                    should_send = True
                elif mode == 'specific':
                    should_send = dialog.id in specific_groups
                elif mode == 'exclude':
                    should_send = dialog.id not in excluded_groups
                if not should_send:
                    logger.info(f"[SCHEDULER] User {user_id}: Skipping group {dialog.name} (ID: {dialog.id}) - filtered by {mode} mode")
                    skipped_groups += 1
                    continue
                try:
                    logger.info(f"[SCHEDULER] User {user_id}: Sending message to {dialog.name} (ID: {dialog.id}): {user_session['message_text']}")
                    await client.send_message(dialog.entity, user_session['message_text'])
                    group_name = dialog.name
                    user_session['groups_sent'].append(f"{datetime.now().strftime('%H:%M')} - {group_name}")
                    messages_sent += 1
                    logger.info(f"[SCHEDULER] User {user_id}: Message sent to {group_name} (ID: {dialog.id})")
                    # Keep only last 100 entries
                    if len(user_session['groups_sent']) > 100:
                        user_session['groups_sent'] = user_session['groups_sent'][-100:]
                except Exception as e:
                    logger.error(f"[SCHEDULER] User {user_id}: Error sending to {dialog.name}: {e}")
                    continue
        logger.info(f"User {user_id}: Found {groups_found} groups, sent {messages_sent} messages, skipped {skipped_groups} groups (mode: {mode})")
        await client.disconnect()
        user_session['last_activity'] = datetime.now().isoformat()
        bot_manager.save_user_data()
    except Exception as e:
        logger.error(f"Error in send_message_job for user {user_id}: {e}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on user state"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    text = update.message.text

    # Log every user message and button press
    logger.info(f"User {user_id} sent text: {text} (login_state: {user_session.get('login_state')})")

    # Password protection: block all actions until authenticated
    if not user_session.get('authenticated', False):
        if user_session.get('login_state') == 'waiting_bot_password':
            # Check password
            if bot_manager.check_password(text):
                user_session['authenticated'] = True
                user_session['login_state'] = 'idle'
                bot_manager.set_admin(user_id)  # Set admin on first correct login
                bot_manager.save_user_data()
                await update.message.reply_text("✅ Password correct! Welcome.")
                await start_command(update, context)
            else:
                await update.message.reply_text("❌ Incorrect password. Please try again:")
        else:
            user_session['login_state'] = 'waiting_bot_password'
            bot_manager.save_user_data()
            await update.message.reply_text("🔒 This bot is password protected.\n\nPlease enter the access password to continue:")
        return

    # Handle button presses
    if text == "📱 Login with Phone":
        logger.info(f"User {user_id} selected: Login with Phone")
        await handle_login_phone(update, context)
    elif text == "📊 Status":
        logger.info(f"User {user_id} selected: Status")
        await handle_status(update, context)
    elif text == "✏️ Set Message":
        logger.info(f"User {user_id} selected: Set Message")
        await handle_set_message(update, context)
    elif text == "⏰ Set Interval":
        logger.info(f"User {user_id} selected: Set Interval")
        await handle_set_interval(update, context)
    elif text == "👥 View Groups":
        logger.info(f"User {user_id} selected: View Groups")
        await handle_view_groups(update, context)
    elif text == "⚙️ Group Settings":
        logger.info(f"User {user_id} selected: Group Settings")
        await handle_group_settings(update, context)
    elif text == "🌐 Send to All Groups":
        logger.info(f"User {user_id} selected: Send to All Groups")
        await handle_send_to_all_groups(update, context)
    elif text == "🎯 Select Specific Groups":
        logger.info(f"User {user_id} selected: Select Specific Groups")
        await handle_select_specific_groups(update, context)
    elif text == "❌ Exclude Groups":
        logger.info(f"User {user_id} selected: Exclude Groups")
        await handle_exclude_groups(update, context)
    elif text == "📋 View Current Settings":
        logger.info(f"User {user_id} selected: View Current Settings")
        await handle_view_current_settings(update, context)
    elif text == "� Refresh Groups":
        logger.info(f"User {user_id} selected: Refresh Groups")
        await handle_refresh_groups(update, context)
    elif text == "⬅️ Back to Main":
        logger.info(f"User {user_id} selected: Back to Main")
        await handle_back_to_main(update, context)
    elif text == "▶️ Start Sending":
        logger.info(f"User {user_id} selected: Start Sending")
        await handle_start_sending(update, context)
    elif text == "⏸️ Pause":
        logger.info(f"User {user_id} selected: Pause Sending")
        await handle_pause_sending(update, context)
    elif text == "⏹️ Stop":
        logger.info(f"User {user_id} selected: Stop Sending")
        await handle_stop_sending(update, context)
    elif text == "📋 View Logs":
        logger.info(f"User {user_id} selected: View Logs")
        await handle_view_logs(update, context)
    elif text == "🔑 Change Password" and bot_manager.admin_user_id == user_id:
        logger.info(f"User {user_id} selected: Change Password")
        user_session['login_state'] = 'waiting_old_password'
        bot_manager.save_user_data()
        await update.message.reply_text("Please enter the current password:")
        return

    # Password change flow (admin only)
    elif user_session.get('login_state') == 'waiting_old_password' and bot_manager.admin_user_id == user_id:
        if bot_manager.check_password(text):
            user_session['login_state'] = 'waiting_new_password'
            bot_manager.save_user_data()
            await update.message.reply_text("Current password correct. Please enter the new password:")
        else:
            await update.message.reply_text("❌ Incorrect current password. Try again or type /cancel to abort.")
        return
    elif user_session.get('login_state') == 'waiting_new_password' and bot_manager.admin_user_id == user_id:
        new_pw = text.strip()
        if len(new_pw) < 4:
            await update.message.reply_text("❌ Password too short. Please enter at least 4 characters:")
            return
        bot_manager.set_password(new_pw)
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        await update.message.reply_text("✅ Password changed successfully!")
        return

    # Handle login states
    elif user_session['login_state'] == 'waiting_phone':
        logger.info(f"User {user_id} is entering phone number: {text}")
        await process_phone_number(update, context)
    elif user_session['login_state'] == 'waiting_code':
        logger.info(f"User {user_id} is entering verification code: {text}")
        await process_verification_code(update, context)
    elif user_session['login_state'] == 'waiting_password':
        logger.info(f"User {user_id} is entering password (hidden)")
        await process_password(update, context)
    elif user_session['login_state'] == 'waiting_message':
        logger.info(f"User {user_id} is setting message text: {text}")
        await process_message_text(update, context)
    elif user_session['login_state'] == 'waiting_interval':
        logger.info(f"User {user_id} is setting interval: {text}")
        await process_interval(update, context)
    elif user_session['login_state'] == 'waiting_specific_groups':
        logger.info(f"User {user_id} is selecting specific groups: {text}")
        await process_specific_groups(update, context)
    elif user_session['login_state'] == 'waiting_exclude_groups':
        logger.info(f"User {user_id} is selecting exclude groups: {text}")
        await process_exclude_groups(update, context)

async def process_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process phone number for login"""
    user_id = str(update.effective_user.id)
    phone = update.message.text.strip()
    # Validate phone number format
    if not phone.startswith('+') or not phone[1:].replace(' ', '').isdigit():
        await update.message.reply_text(
            "❌ Invalid phone number format!\n"
            "Please use international format: +1234567890"
        )
        return
    try:
        client1 = TelegramClient(StringSession(), API_ID, API_HASH)
        if not client1.is_connected():
            await client1.connect()
        await update.message.reply_text("📱 Sending verification code...")
        result = await client1.send_code_request(phone)
        phone_code_hash = result.phone_code_hash
        session_str = client1.session.save()
        await client1.disconnect()
        # Store temp login state in memory only
        bot_manager.temp_login[user_id] = {
            'phone': phone,
            'phone_code_hash': phone_code_hash,
            'session_str': session_str,
            'client': None
        }
        user_session = bot_manager.get_user_session(user_id)
        user_session['phone'] = phone  # Store phone in persistent session
        user_session['login_state'] = 'waiting_code'
        bot_manager.save_user_data()
        await update.message.reply_text(
            f"✅ Verification code sent to {phone}\n\n"
            "Please enter the verification code you received:"
        )
    except PhoneNumberInvalidError:
        await update.message.reply_text(
            "❌ Invalid phone number!\n"
            "Please check your phone number and try again."
        )
        user_session = bot_manager.get_user_session(user_id)
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
    except Exception as e:
        logger.error(f"Error sending code: {e}")
        await update.message.reply_text(
            f"❌ Error sending code: {str(e)}\n"
            "Please check your phone number and try again."
        )
        user_session = bot_manager.get_user_session(user_id)
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        try:
            await client1.disconnect()
        except:
            pass

async def process_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process verification code"""
    user_id = str(update.effective_user.id)
    code = update.message.text.strip()
    code=code.replace("_","")  # Remove underscores if any
    temp = bot_manager.temp_login.get(user_id)
    user_session = bot_manager.get_user_session(user_id)
    if not temp:
        await update.message.reply_text("❌ Session expired. Please start over with login")
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        return
    try:
        client2 = TelegramClient(StringSession(temp['session_str']), API_ID, API_HASH)
        if not client2.is_connected():
            await client2.connect()
        try:
            result = await client2.sign_in(
                phone=temp['phone'],
                code=code,
                phone_code_hash=temp['phone_code_hash']
            )
        except SessionPasswordNeededError:
            # 2FA required
            temp['client'] = client2
            user_session['login_state'] = 'waiting_password'
            bot_manager.save_user_data()
            await update.message.reply_text(
                "🔐 Two-factor authentication is enabled.\n"
                "Please enter your password:"
            )
            return
        # Success - get final session string
        final_session = client2.session.save()
        user_info = await client2.get_me()
        user_session['session_string'] = final_session
        user_session['login_state'] = 'idle'
        user_session['last_activity'] = datetime.now().isoformat()
        bot_manager.save_user_data()
        await client2.disconnect()
        del bot_manager.temp_login[user_id]
        await update.message.reply_text(
            f"🎉 **Login Successful!**\n\n"
            f"👤 **Account**: {user_info.first_name}"
            f"{' ' + user_info.last_name if user_info.last_name else ''}\n"
            f"📱 **Phone**: {temp['phone']}\n"
            f"🆔 **User ID**: {user_info.id}\n\n"
            "You can now:\n"
            "• Set your message text\n"
            "• Set sending interval\n"
            "• View and configure groups\n"
            "• Start sending messages"
        )
    except PhoneCodeInvalidError:
        await update.message.reply_text(
            "❌ Invalid verification code!\n"
            "Please check the code and try again:"
        )
        await client2.disconnect()
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        await update.message.reply_text(
            f"❌ Error during login: {str(e)}\n"
            "Please try again with login"
        )
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        try:
            await client2.disconnect()
        except:
            pass

async def process_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 2FA password input"""
    user_id = str(update.effective_user.id)
    password = update.message.text.strip()
    temp = bot_manager.temp_login.get(user_id)
    user_session = bot_manager.get_user_session(user_id)
    if not temp or not temp.get('client'):
        await update.message.reply_text("❌ Session expired. Please start over with login")
        user_session['login_state'] = 'idle'
        bot_manager.save_user_data()
        return
    client = temp['client']
    try:
        result = await client.sign_in(password=password)
        final_session = client.session.save()
        user_info = await client.get_me()
        user_session['session_string'] = final_session
        user_session['login_state'] = 'idle'
        user_session['last_activity'] = datetime.now().isoformat()
        bot_manager.save_user_data()
        await client.disconnect()
        del bot_manager.temp_login[user_id]
        await update.message.reply_text(
            f"🎉 **Login Successful!**\n\n"
            f"👤 **Account**: {user_info.first_name}"
            f"{' ' + user_info.last_name if user_info.last_name else ''}\n"
            f"📱 **Phone**: {temp['phone']}\n"
            f"🆔 **User ID**: {user_info.id}\n\n"
            "You can now:\n"
            "• Set your message text\n"
            "• Set sending interval\n"
            "• View and configure groups\n"
            "• Start sending messages"
        )
    except Exception as e:
        logger.error(f"Error with password: {e}")
        await update.message.reply_text(
            "❌ Invalid password!\n"
            "Please try again:"
        )

async def process_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process message text"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    message_text = update.message.text.strip()
    
    user_session['message_text'] = message_text
    user_session['login_state'] = 'idle'
    user_session['last_activity'] = datetime.now().isoformat()
    bot_manager.save_user_data()
    
    await update.message.reply_text(
        f"✅ **Message set successfully!**\n\n"
        f"Your message: {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n\n"
        f"Current interval: {user_session['interval_minutes']} minutes\n\n"
        f"Use '▶️ Start Sending' to begin sending messages."
    )

async def process_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process interval setting"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    try:
        interval = int(update.message.text.strip())
        if interval < 1:
            await update.message.reply_text("❌ Interval must be at least 1 minute.")
            return
        user_session['interval_minutes'] = interval
        user_session['login_state'] = 'idle'
        user_session['last_activity'] = datetime.now().isoformat()
        bot_manager.save_user_data()
        await update.message.reply_text(
            f"✅ **Interval set successfully!**\n\n"
            f"New interval: {interval} minutes\n\n"
            f"Messages will be sent every {interval} minutes when active."
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for minutes.")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = str(update.effective_user.id)
    user_session = bot_manager.get_user_session(user_id)
    
    # Clean up temp login state if exists
    temp = bot_manager.temp_login.get(user_id)
    if temp and temp.get('client'):
        try:
            await temp['client'].disconnect()
        except:
            pass
    if user_id in bot_manager.temp_login:
        del bot_manager.temp_login[user_id]
    user_session['login_state'] = 'idle'
    bot_manager.save_user_data()
    await update.message.reply_text("❌ **Operation cancelled.**\n\nUse the buttons below to continue.")


async def post_init(application):
    # Start the scheduler after the event loop is running
    bot_manager.scheduler.start()

def main():
    """Main function to run the bot"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your BOT_TOKEN in the configuration!")
        return

    if not API_ID or API_ID == "YOUR_API_ID":
        print("❌ Please set your API_ID in the configuration!")
        return

    if not API_HASH or API_HASH == "YOUR_API_HASH":
        print("❌ Please set your API_HASH in the configuration!")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Run the bot
    print("🤖 Bot started! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()