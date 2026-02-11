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
    # Holt Daten aus GitHub Secrets
    sender = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = os.environ.get('EMAIL_RECEIVER') or sender

    if not sender or not password:
        print("Mail-Secrets fehlen!")
        return

    msg = MIMEText(content)
    msg['Subject'] = f"📊 Depot-Update {datetime.now().strftime('%d.%m.%Y')}"
    msg['From'] = sender
    msg['To'] = receiver

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print("📧 Mail versendet!")
    except Exception as e:
        print(f"Fehler: {e}")

# --- DATEN SAMMELN ---
results = []
print(f"Sammle Daten für {len(TICKERS)} Aktien...")

for sym, name in TICKERS.items():
    try:
        t = yf.Ticker(sym)
        info = t.info
        raw_cap = info.get('marketCap')
        mcap = raw_cap / 1_000_000_000 if raw_cap else 0
        pe = info.get('trailingPE') or info.get('forwardPE')
        
        results.append({
            'name': name[:12], 
            'cap': mcap,
            'pe': pe if pe else 999.0
        })
    except:
        continue
    time.sleep(0.5)

results.sort(key=lambda x: x['pe'])

# --- BERICHT BAUEN ---
bericht = f"📊 DEPOT-STATUS ({datetime.now().strftime('%d.%m. %H:%M')})\n"
bericht += "-" * 30 + "\n"
bericht += f"{'Name':<12} | {'Mrd.':>7} | {'KGV':>5}\n"
bericht += "-" * 30 + "\n"

for r in results:
    pe_fmt = f"{r['pe']:>5.1f}" if r['pe'] < 900 else "  n/a"
    cap_fmt = f"{r['cap']:>7.1f}" if r['cap'] > 0 else "    ?"
    bericht += f"{r['name']:<12} | {cap_fmt} | {pe_fmt}\n"

bericht += "-" * 30

print(bericht)
send_mail(bericht)
