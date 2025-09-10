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


with Path("telegram_config.json").open("r") as f:
    CONFIG = json.load(f)


def send_message(message: str, parse_mode: str = "Markdown") -> bool:
    """Send message via Telegram"""
    if not CONFIG:
        print(f"[Telegram Disabled] {message}")
        return False

    url = f"https://api.telegram.org/bot{CONFIG['bot_token']}/sendMessage"

    payload = {"chat_id": CONFIG["chat_id"], "text": message}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram message: {e}")
        # Try again without markdown formatting if it fails
        if parse_mode in ["Markdown", "MarkdownV2"]:
            payload["parse_mode"] = None
            try:
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                logging.info("Sent message without markdown formatting")
                return True
            except:
                pass
        return False


def send_trade_alert(
    action: str, ticker: str, strike: float, expiry: str, price: float, **kwargs
):
    """Send formatted trade alert"""
    # Use emojis and plain text
    message = f"🔔 Trade Alert - {ticker} 📊\n"
    message += "━━━━━━━━━━━━━━━━━━\n"
    message += f"📌 Action: {action}\n"
    message += f"💵 Strike: ${strike}\n"
    message += f"📅 Expiry: {expiry}\n"
    message += f"💰 Price: ${price:.2f}\n"

    for key, value in kwargs.items():
        if value is not None:  # Skip None values
            key_formatted = key.replace("_", " ").title()
            # Add emojis for specific fields
            if "delta" in key.lower():
                message += f"📐 {key_formatted}: {value}\n"
            elif "pnl" in key.lower() or "profit" in key.lower():
                message += f"💸 {key_formatted}: {value}\n"
            elif "notes" in key.lower():
                message += f"📝 {key_formatted}: {value}\n"
            else:
                message += f"▫️ {key_formatted}: {value}\n"

    message += "━━━━━━━━━━━━━━━━━━"

    # Send without markdown parsing
    return send_message(message, parse_mode=None)


def format_trade_alert_params(
    delta: float = 0.0, pnl: float = 0.0, cumulative_pnl: float = 0.0, notes: str = ""
):
    """Format parameters for trade alert - returns dict for **kwargs"""
    params = {}

    if delta != 0.0:
        params["delta"] = f"{delta:.3f}"
    if pnl != 0.0:
        params["pnl"] = f"${pnl:.2f}"
    if cumulative_pnl != 0.0:
        params["total_pnl"] = f"${cumulative_pnl:.2f}"
    if notes:
        params["notes"] = notes

    return params


def send_stop_loss_alert(ticker: str, reason: str, loss_amount: float):
    """Send urgent stop loss alert"""
    message = "🚨🚨🚨 STOP LOSS TRIGGERED 🚨🚨🚨\n"
    message += "━━━━━━━━━━━━━━━━━━\n"
    message += f"📊 Ticker: {ticker}\n"
    message += f"⚠️ Reason: {reason}\n"
    message += f"💔 Loss Amount: ${loss_amount:.2f}\n"
    message += "━━━━━━━━━━━━━━━━━━\n"
    message += "🔴 All positions being liquidated"

    return send_message(message, parse_mode=None)


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


# Test function
if __name__ == "__main__":
    if CONFIG:
        success = send_message("✅ Telegram bot connected!")
        print("Test message sent" if success else "Failed to send")
    else:
        print("Telegram not configured - set up telegram_config.json")
