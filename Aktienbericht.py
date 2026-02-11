import yfinance as yf
from datetime import datetime
import time
import os
import smtplib
from email.mime.text import MIMEText

TICKERS = {
    "ABNB": "Airbnb", "BABA": "Alibaba", "GOOGL": "Alphabet", "AMZN": "Amazon",
    "AXP": "Amex", "AMP.MI": "Amplifon", "ASML": "ASML", "BIDU": "Baidu",
    "BBAR": "BBVA Arg", "SAN": "Santander", "BAC": "BofA",
    "BRK-B": "Berkshire", "BIRK": "Birkenst.", "BKNG": "Booking",
    "BYDDY": "BYD", "CP": "Can.Pacific", "COST": "Costco", "EA": "Elec.Arts", 
    "RACE": "Ferrari", "FTK.DE": "Flatex", "FND": "Floor&Dec", "GRAB": "Grab",
    "HOG": "Harley", "ISP.MI": "Intesa", "JD": "JD.com",
    "JPM": "JPMorgan", "MC.PA": "LVMH", "LYFT": "Lyft", "UNLYF": "Unilever",
    "MA": "Mastercard", "META": "Meta", "MU": "Micron",
    "MDLZ": "Mondelez", "NEM.DE": "Nemetschek", "NTDOY": "Nintendo",
    "PYPL": "PayPal", "PDD": "Pinduoduo", "PGR": "Progress.", "SAP": "SAP",
    "ENR.DE": "Siemens En", "SPOT": "Spotify", "TCEHY": "Tencent", 
    "TSM": "TSMC", "UCG.MI": "UniCredit", "UNP": "Union Pac",
    "V": "Visa", "WMT": "Walmart", "DIS": "Disney", "ZAL.DE": "Zalando",
    "TAVHL.IS": "TAV Airp"
}

def send_mail(content):
    # Diese Werte ziehen wir aus den GitHub Secrets
    sender_email = os.environ.get('EMAIL_USER')
    receiver_email = os.environ.get('EMAIL_USER') # Schickt es an dich selbst
    password = os.environ.get('EMAIL_PASSWORD')

    if not sender_email or not password:
        print("E-Mail-Zugangsdaten fehlen. Überspringe Versand.")
        return

    msg = MIMEText(content)
    msg['Subject'] = f"📊 Dein Aktienbericht - {datetime.now().strftime('%d.%m.%Y')}"
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("E-Mail erfolgreich gesendet!")
    except Exception as e:
        print(f"Fehler beim Mail-Versand: {e}")

# --- DATEN HOLEN ---
results = []
print(f"Lade {len(TICKERS)} Werte...")

for sym, name in TICKERS.items():
    try:
        t = yf.Ticker(sym)
        # Nutze fast_info für stabilere Cap-Werte
        cap = t.fast_info.get('market_cap', 0) / 1_000_000_000
        # Info für KGV
        pe = t.info.get('trailingPE') or t.info.get('forwardPE') or 999.0
        
        results.append({'name': name[:10], 'cap': cap, 'pe': pe})
    except:
        continue
    time.sleep(1.0) # Schutz vor 429-Fehler

results.sort(key=lambda x: x['pe'])

# --- BERICHT ERSTELLEN ---
bericht = f"📊 DEPOT-CHECK ({datetime.now().strftime('%d.%m. %H:%M')})\n"
bericht += "-" * 28 + "\n"
bericht += f"{'Name':<10} | {'Mrd.':>7} | {'KGV':>5}\n"
bericht += "-" * 28 + "\n"

for r in results:
    pe_fmt = f"{r['pe']:>5.1f}" if r['pe'] < 900 else "  n/a"
    cap_fmt = f"{r['cap']:>7.1f}" if r['cap'] > 0 else "    ?"
    bericht += f"{r['name']:<10} | {cap_fmt} | {pe_fmt}\n"

print(bericht)
send_mail(bericht)
