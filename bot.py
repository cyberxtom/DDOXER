#!/usr/bin/env python3
"""
DDOXER Telegram Bot - Remote control for network stress testing tool
"""

import os
import sys
import json
import subprocess
import logging
import threading
import time
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

import main as ddoxer

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("DDOXER_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT_PASSWORD = os.environ.get("DDOXER_BOT_PASSWORD", "ddoxer_admin")
ALLOWED_USERS = [int(x) for x in os.environ.get("DDOXER_ALLOWED_USERS", "").split(",") if x]

auth_users = {}
attack_process = None
attack_type = None
attack_start = None


def check_auth(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id not in auth_users:
            await update.message.reply_text("Unauthorized. Use /login <password>")
            return
        return await func(update, context)
    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        "DDOXER Telegram Bot\n\n"
        "Remote control for network stress testing.\n\n"
        "Commands:\n"
        "/login <password> - Authenticate\n"
        "/target <ip> [port] - Set target\n"
        "/attack - Show attack menu\n"
        "/stop - Stop current attack\n"
        "/status - Show target and attack status\n"
        "/config - Show full configuration\n"
        "/help - Show this message"
    )
    await update.message.reply_text(msg)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in auth_users:
        await update.message.reply_text("Already authorized.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /login <password>")
        return
    
    if context.args[0] != BOT_PASSWORD:
        await update.message.reply_text("Wrong password.")
        return
    
    auth_users[user.id] = True
    await update.message.reply_text(f"Authorized. Welcome {user.first_name}.")


@check_auth
async def target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            f"Current target: {ddoxer.TARGET_IP}:{ddoxer.TARGET_PORT}\n"
            "Usage: /target <ip> [port]"
        )
        return
    
    ip = context.args[0]
    port = int(context.args[1]) if len(context.args) > 1 else ddoxer.TARGET_PORT
    
    ddoxer.TARGET_IP = ip
    ddoxer.TARGET_PORT = port
    ddoxer.TARGET_HTTP_HOST = f"http://{ip}:{port}"
    
    await update.message.reply_text(f"Target set to {ip}:{port}")


@check_auth
async def attack_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Full Attack", callback_data="attack_full")],
        [InlineKeyboardButton("SYN Flood", callback_data="attack_syn"),
         InlineKeyboardButton("HTTP Flood", callback_data="attack_http")],
        [InlineKeyboardButton("ICMP Flood", callback_data="attack_icmp"),
         InlineKeyboardButton("Nmap Scan", callback_data="attack_nmap")],
        [InlineKeyboardButton("Stop Attack", callback_data="stop")],
        [InlineKeyboardButton("Status", callback_data="status")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select attack type:", reply_markup=reply_markup)


@check_auth
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "status":
        await show_status(update, context)
        return
    
    if data == "stop":
        result = stop_attack()
        await query.edit_message_text(result)
        return
    
    if data.startswith("attack_"):
        atype = data.replace("attack_", "")
        result = start_attack(atype)
        await query.edit_message_text(result)
        return


def start_attack(atype):
    global attack_process, attack_type, attack_start
    
    if attack_process and attack_process.poll() is None:
        return f"Attack already running ({attack_type}). Use /stop first."
    
    target = ddoxer.TARGET_IP
    port = ddoxer.TARGET_PORT
    
    config = json.dumps({
        "attack": atype,
        "target_ip": target,
        "target_port": port,
        "http_host": f"http://{target}:{port}",
        "scapy_pps": ddoxer.SCAPY_PPS,
        "http_threads": ddoxer.HTTP_THREADS,
        "http_loops": ddoxer.HTTP_LOOPS_PER_THREAD,
        "http_timeout": ddoxer.HTTP_TIMEOUT,
        "icmp_processes": ddoxer.ICMP_PROCESSES,
        "nmap_timeout": ddoxer.NMAP_TIMEOUT,
    })
    
    attack_type = atype
    attack_start = time.time()
    attack_process = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "runner.py"), config],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    
    names = {
        "full": "Full Attack (Nmap + SYN + HTTP + ICMP)",
        "syn": "SYN Flood",
        "http": "HTTP Flood",
        "icmp": "ICMP Flood",
        "nmap": "Nmap Scan",
    }
    return f"{names.get(atype, atype)} launched against {target}:{port}"


def stop_attack():
    global attack_process, attack_type, attack_start
    
    if attack_process and attack_process.poll() is None:
        attack_process.terminate()
        try:
            attack_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            attack_process.kill()
            attack_process.wait()
        
        elapsed = time.time() - attack_start
        name = attack_type or "Unknown"
        attack_process = None
        attack_type = None
        attack_start = None
        return f"{name} stopped after {elapsed:.1f}s"
    
    if attack_type == "full":
        ddoxer.stop_attacks()
        elapsed = time.time() - attack_start
        attack_type = None
        attack_start = None
        return f"Full attack stopped after {elapsed:.1f}s"
    
    return "No attack running."


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    running = attack_process and attack_process.poll() is None
    
    elapsed = ""
    if running and attack_start:
        elapsed = f", running {time.time() - attack_start:.0f}s"
    
    msg = (
        f"Target: {ddoxer.TARGET_IP}:{ddoxer.TARGET_PORT}\n"
        f"Attack: {attack_type or 'IDLE'}{elapsed}\n"
        f"Status: {'RUNNING' if running else 'IDLE'}\n"
        f"Root: {'YES' if not ddoxer.NO_ROOT_MODE else 'NO'}\n"
    )
    
    if hasattr(update.callback_query, 'edit_message_text'):
        await update.callback_query.edit_message_text(msg)
    else:
        await update.message.reply_text(msg)


@check_auth
async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Configuration:\n"
        f"Target IP: {ddoxer.TARGET_IP}\n"
        f"Target Port: {ddoxer.TARGET_PORT}\n"
        f"HTTP Host: {ddoxer.TARGET_HTTP_HOST}\n"
        f"SYN PPS: {ddoxer.SCAPY_PPS}\n"
        f"HTTP Threads: {ddoxer.HTTP_THREADS}\n"
        f"HTTP Requests/Thread: {ddoxer.HTTP_LOOPS_PER_THREAD}\n"
        f"HTTP Timeout: {ddoxer.HTTP_TIMEOUT}s\n"
        f"ICMP Processes: {ddoxer.ICMP_PROCESSES}\n"
        f"Nmap Timeout: {ddoxer.NMAP_TIMEOUT}s\n"
        f"Root Mode: {'NO' if ddoxer.NO_ROOT_MODE else 'YES'}"
    )
    await update.message.reply_text(msg)


@check_auth
async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = stop_attack()
    await update.message.reply_text(result)


@check_auth
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_status(update, context)


def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")


def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Set DDOXER_BOT_TOKEN environment variable.")
        sys.exit(1)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("target", target))
    app.add_handler(CommandHandler("attack", attack_menu))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    print("DDOXER Telegram Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
