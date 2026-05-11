#!/usr/bin/env python3
"""Helper to run an interactive pytr web login from host (not inside the container).

Usage:
  source .venv/bin/activate
  python tools/pytr_login.py

This script will:
 - instantiate TradeRepublicApi using TR_PHONE_NUMBER/TR_PIN from environment
 - call initiate_weblogin() to start the flow (may open a headless browser)
 - prompt you to enter the verification code if required and call complete_weblogin(code)
 - save cookies to the file configured by TR_COOKIES_FILE (default: ./pytr_cookies.json)

Make sure you run this on the host where Playwright browsers can be installed and executed.
If Playwright browsers are not installed, run: playwright install
"""
import os
from pytr.api import TradeRepublicApi
from app.core.config import settings

cookies_file = getattr(settings, 'tr_cookies_file', './pytr_cookies.json')
print('Using cookies file:', cookies_file)

api = TradeRepublicApi(phone_no=settings.tr_phone or None, pin=settings.tr_pin or None, save_cookies=True, cookies_file=cookies_file)
print('Starting web login flow...')
try:
    api.initiate_weblogin()
    print('Web login initiated. If a verification code was sent to your device, enter it now.')
except Exception as e:
    print('Error initiating weblogin:', e)

code = input('Enter verification code (or press Enter to skip): ').strip()
if code:
    try:
        ok = api.complete_weblogin(code)
        print('complete_weblogin returned:', ok)
    except Exception as e:
        print('Error completing weblogin:', e)

try:
    api.save_websession()
    print('Saved web session / cookies to', cookies_file)
except Exception as e:
    print('Could not save web session:', e)

print('Done. You can now restart the docker container and it should reuse the saved cookies.')

