"""
test_email.py - Run this to see the exact email error
python test_email.py
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENDER   = "727723euit275@skcet.ac.in"
PASSWORD = "tjzc azya rdnf cnci"
TO       = "visakavisaka2705@gmail.com"

print(f"Sender  : {SENDER}")
print(f"To      : {TO}")
print()

# Try Gmail SMTP (only works for @gmail.com accounts)
print("Trying smtp.gmail.com port 587...")
try:
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as s:
        s.starttls()
        s.login(SENDER, PASSWORD)
        print("  Gmail login SUCCESS")
except Exception as e:
    print(f"  Gmail FAILED: {e}")

# Try Office365 SMTP (works for many college/org accounts)
print("Trying smtp.office365.com port 587...")
try:
    with smtplib.SMTP("smtp.office365.com", 587, timeout=10) as s:
        s.starttls()
        s.login(SENDER, PASSWORD)
        print("  Office365 login SUCCESS")
except Exception as e:
    print(f"  Office365 FAILED: {e}")

# Try generic SMTP SSL port 465
print("Trying smtp.gmail.com port 465 (SSL)...")
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as s:
        s.login(SENDER, PASSWORD)
        print("  Gmail SSL login SUCCESS")
except Exception as e:
    print(f"  Gmail SSL FAILED: {e}")

print()
print("If all failed, your college email likely blocks external SMTP.")
print("Solution: use a personal Gmail account instead.")
print("  1. Create/use a Gmail account")
print("  2. Enable 2FA at myaccount.google.com")
print("  3. Generate App Password at myaccount.google.com/apppasswords")
print("  4. Update .env: SMTP_SENDER_EMAIL=yourgmail@gmail.com")
print("                  SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx")
