import yfinance as yf
from datetime import datetime
import time
import os
import smtplib
from email.mime.multipart import MIMEMultipart
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
    "MA": "Mastercard", "META": "Meta", "MU": "Micron", "MSFT": "Microsoft",
    "MDLZ": "Mondelez", "NEM.DE": "Nemetschek", "NTDOY": "Nintendo",
    "PYPL": "PayPal", "PDD": "Pinduoduo", "PGR": "Progress.", "SAP": "SAP",
    "ENR.DE": "Siemens En", "SPOT": "Spotify", "TCEHY": "Tencent",
    "TSM": "TSMC", 'TM': "Toyota", "UCG.MI": "UniCredit", "UNP": "Union Pac",
    "V": "Visa", "WMT": "Walmart", "DIS": "Disney", "ZAL.DE": "Zalando",
    "TAVHL.IS": "TAV Airp", "VSCO": "Vicoria Secret", "KASPI.KZ": "Kaspi",

    # Ergänzungen:
    "UBER": "Uber",
    "RDC.DE": "Redcare",
    "OGI.TO": "OrganiGram",
}

# --- FX Cache (nur für "nicht EUR/USD") ---
_fx_cache_to_eur = {}  # currency -> rate (currency->EUR)

def get_fx_rate_to_eur(currency: str):
    """
    Liefert den Wechselkurs currency->EUR als float.
    Nutzt yfinance Pair wie 'GBPEUR=X'. Cache inklusive.
    """
    if not currency or currency in ("EUR", "USD"):
        return None
    if currency in _fx_cache_to_eur:
        return _fx_cache_to_eur[currency]

    try:
        pair = f"{currency}EUR=X"
        fx = yf.Ticker(pair)
        hist = fx.history(period="5d")  # robust gegen leere Tage
        if hist is None or hist.empty:
            _fx_cache_to_eur[currency] = None
            return None
        rate = float(hist["Close"].dropna().iloc[-1])
        _fx_cache_to_eur[currency] = rate
        return rate
    except Exception:
        _fx_cache_to_eur[currency] = None
        return None

def quarter_label(dt: datetime) -> str:
    q = (dt.month - 1) // 3 + 1
    return f"Q{q} {dt.year}"

def most_recent_quarter_from_info(info: dict) -> str:
    """
    Gibt z.B. 'Q3 2025 (30.09.2025)' zurück oder 'n/a'
    """
    mrq = info.get("mostRecentQuarter")
    if not mrq:
        return "n/a"
    try:
        dt = datetime.fromtimestamp(mrq)
        return f"{quarter_label(dt)} ({dt.strftime('%d.%m.%Y')})"
    except Exception:
        return "n/a"

def send_mail(results, timestamp):
    sender = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASSWORD")
    receiver = "jan-eric.eilers@gmx.de"

    if not sender or not password:
        print("Mail-Secrets fehlen!")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Depot-Update {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = sender
    msg["To"] = receiver

    # HTML Tabelle bauen
    rows = ""
    for r in results:
        pe_fmt = f"{r['pe']:.1f}" if r["pe"] < 900 else "n/a"
        cap_fmt = f"{r['cap_b']:.1f}" if r["cap_b"] > 0 else "?"
        rows += f"""
        <tr>
            <td style="border-top:1px solid #e5e7eb; padding:8px;">{r['name']}</td>
            <td style="border-top:1px solid #e5e7eb; padding:8px; text-align:right;">{cap_fmt} {r['cap_ccy']}</td>
            <td style="border-top:1px solid #e5e7eb; padding:8px; text-align:right;">{pe_fmt}</td>
            <td style="border-top:1px solid #e5e7eb; padding:8px;">{r['report']}</td>
        </tr>
        """

    html = f"""
    <html>
      <body style="font-family:Arial, sans-serif; background:#f4f6f8; padding:20px;">
        <div style="max-width:900px; margin:0 auto;">
          <div style="background:#ffffff; border-radius:10px; padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
            <div style="display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap;">
              <h2 style="margin:0; color:#111827;">Depot Status</h2>
              <div style="color:#6b7280; font-size:12px;">{timestamp}</div>
            </div>

            <div style="margin-top:12px; overflow-x:auto;">
              <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; min-width:760px;">
                <thead>
                  <tr style="background:#111827; color:#ffffff;">
                    <th style="padding:10px; text-align:left;">Name</th>
                    <th style="padding:10px; text-align:right;">Market Cap</th>
                    <th style="padding:10px; text-align:right;">KGV</th>
                    <th style="padding:10px; text-align:left;">Letzter Bericht</th>
                  </tr>
                </thead>
                <tbody>
                  {rows}
                </tbody>
              </table>
            </div>

            <div style="margin-top:14px; color:#6b7280; font-size:12px; line-height:1.4;">
              Hinweis: Alle Währungen außer EUR oder USD werden in EUR umgerechnet (FX via yfinance). USD bleibt USD.
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print("Mail versendet!")
    except Exception as e:
        print(f"Fehler: {e}")

# --- DATEN SAMMELN ---
results = []
print(f"Sammle Daten für {len(TICKERS)} Aktien...")

for sym, name in TICKERS.items():
    try:
        t = yf.Ticker(sym)
        info = t.info

        # Market Cap + Currency
        raw_cap = info.get("marketCap")  # in Originalwährung
        ccy = info.get("currency") or info.get("financialCurrency") or "?"

        # KGV
        pe = info.get("trailingPE") or info.get("forwardPE")
        pe_val = float(pe) if pe else 999.0

        # Letzter Finanzbericht
        report = most_recent_quarter_from_info(info)

        cap_b = 0.0  # Market Cap in Milliarden
        cap_ccy = ccy

        if raw_cap:
            # Grundwert in Originalwährung (Milliarden)
            cap_b = float(raw_cap) / 1_000_000_000

            # Regel: alles außer EUR oder USD -> in EUR umrechnen
            if ccy not in ("EUR", "USD"):
                rate = get_fx_rate_to_eur(ccy)
                if rate:
                    cap_b = (float(raw_cap) * rate) / 1_000_000_000
                    cap_ccy = "EUR"
                else:
                    # wenn FX fehlt: anzeigen als "?" statt falsche Umrechnung
                    cap_b = 0.0
                    cap_ccy = "EUR"

        results.append({
            "symbol": sym,
            "name": name[:14],
            "cap_b": cap_b,
            "cap_ccy": cap_ccy,
            "pe": pe_val,
            "report": report,
        })

    except Exception:
        pass

    time.sleep(0.5)

# Sortierung nach KGV (wie bisher)
results.sort(key=lambda x: x["pe"])

timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
send_mail(results, timestamp)
