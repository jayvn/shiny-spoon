#!/usr/bin/env python
"""
Telegram bot for sending trading notifications
"""

import json
import logging
from pathlib import Path

import requests

# Global config
CONFIG = None


def load_config(config_file: str = "telegram_config.json"):
    """Load config from JSON file"""
    global CONFIG
    config_path = Path(config_file)

    if not config_path.exists():
        logging.warning(f"Config file not found: {config_file}")
        return False

    try:
        with config_path.open("r") as f:
            data = json.load(f)

        if not data.get("bot_token") or not data.get("chat_id"):
            logging.warning("Missing bot_token or chat_id in config")
            return False

        CONFIG = data
        return True
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return False


def send_message(message: str, parse_mode: str = "Markdown") -> bool:
    """Send message via Telegram"""
    if not CONFIG:
        print(f"[Telegram Disabled] {message}")
        return False

    url = f"https://api.telegram.org/bot{CONFIG['bot_token']}/sendMessage"

    payload = {"chat_id": CONFIG["chat_id"], "text": message, "parse_mode": parse_mode}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False


def send_trade_alert(
    action: str, ticker: str, strike: float, expiry: str, price: float, **kwargs
):
    """Send formatted trade alert"""
    message = f"🔔 *Trade Alert - {ticker}*\n\n"
    message += f"*Action:* {action}\n"
    message += f"*Strike:* ${strike}\n"
    message += f"*Expiry:* {expiry}\n"
    message += f"*Price:* ${price:.2f}\n"

    for key, value in kwargs.items():
        if value is not None:  # Skip None values
            message += f"*{key.replace('_', ' ').title()}:* {value}\n"

    return send_message(message)


def send_stop_loss_alert(ticker: str, reason: str, loss_amount: float):
    """Send urgent stop loss alert"""
    message = f"🚨 *STOP LOSS TRIGGERED - {ticker}* 🚨\n\n"
    message += f"*Reason:* {reason}\n"
    message += f"*Loss Amount:* ${loss_amount:.2f}\n"
    message += "\n⚠️ All positions being liquidated"

    return send_message(message)


def send_position_update(
    ticker: str, leaps_pnl: float, short_pnl: float, total_collected: float
):
    """Send position status update"""
    message = f"📊 *Position Update - {ticker}*\n\n"
    message += f"*LEAPS P&L:* ${leaps_pnl:.2f}\n"
    message += f"*Short Call P&L:* ${short_pnl:.2f}\n"
    message += f"*Total Premium:* ${total_collected:.2f}\n"
    message += f"*Net P&L:* ${leaps_pnl + short_pnl:.2f}"

    return send_message(message)


def send_error(error_msg: str):
    """Send error notification"""
    message = f"❌ *Error*\n\n{error_msg}"
    return send_message(message)


# Initialize on import
load_config()


# Test function
if __name__ == "__main__":
    if CONFIG:
        success = send_message("✅ Telegram bot connected!")
        print("Test message sent" if success else "Failed to send")
    else:
        print("Telegram not configured - set up telegram_config.json")
