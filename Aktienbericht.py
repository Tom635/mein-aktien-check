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
    sender = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASSWORD')
    receiver = "jan-eric.eilers@gmx.de"

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

def quarter_label(dt: datetime) -> str:
    q = (dt.month - 1) // 3 + 1
    return f"Q{q} {dt.year}"

def most_recent_quarter_from_info(info: dict) -> tuple[str, str]:
    """
    Returns (quarter_form, date_str) like ("Q3 2025", "30.09.2025")
    If missing -> ("n/a", "")
    """
    mrq = info.get("mostRecentQuarter")
    if not mrq:
        return ("n/a", "")
    try:
        dt = datetime.fromtimestamp(mrq)
        return (quarter_label(dt), dt.strftime("%d.%m.%Y"))
    except Exception:
        return ("n/a", "")

# --- DATEN SAMMELN ---
results = []
print(f"Sammle Daten für {len(TICKERS)} Aktien...")

for sym, name in TICKERS.items():
    try:
        t = yf.Ticker(sym)
        info = t.info

        raw_cap = info.get('marketCap')
        mcap = raw_cap / 1_000_000_000 if raw_cap else 0.0

        # Währung: oft "currency", sonst "financialCurrency"
        ccy = info.get("currency") or info.get("financialCurrency") or "?"

        pe = info.get('trailingPE') or info.get('forwardPE')
        pe_val = float(pe) if pe else 999.0

        q_form, q_date = most_recent_quarter_from_info(info)
        report = f"{q_form} ({q_date})" if q_date else q_form

        results.append({
            'name': name[:14],
            'cap': mcap,
            'ccy': ccy,
            'pe': pe_val,
            'report': report
        })
    except Exception:
        continue
    time.sleep(0.5)

results.sort(key=lambda x: x['pe'])

# --- BERICHT BAUEN ---
timestamp = datetime.now().strftime('%d.%m. %H:%M')
bericht = f"📊 DEPOT-STATUS ({timestamp})\n"
bericht += "=" * 70 + "\n"
bericht += f"{'NAME':<14} | {'MRD.':>8} {'CCY':<3} | {'KGV':>6} | {'LETZTER BERICHT':<28}\n"
bericht += "-" * 70 + "\n"

for r in results:
    pe_fmt = f"{r['pe']:>6.1f}" if r['pe'] < 900 else "   n/a"
    cap_fmt = f"{r['cap']:>8.1f}" if r['cap'] > 0 else "     ?"
    ccy_fmt = f"{r['ccy']:<3}" if r['ccy'] else "  ?"

    clean_name = r['name'][:14]
    report_fmt = (r['report'] or "n/a")[:28]
    bericht += f"{clean_name:<14} | {cap_fmt} {ccy_fmt} | {pe_fmt} | {report_fmt:<28}\n"

bericht += "=" * 70

print(bericht)
send_mail(bericht)
