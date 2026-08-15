import yfinance as yf
from datetime import datetime
import time
import os
import random
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
    "TAVHL.IS": "TAV Airp", "VSXY": "Vicoria Secret", "KSPI": "Kaspi",
    "BN": "Brookfield", "BAM": "Brookfield Asset Management", "BYDDY": "BYD",
    "KO": "Coca-Cola",

    # Ergänzungen:
    "UBER": "Uber",
    "RDC.DE": "Redcare",
    "OGI.TO": "OrganiGram",
    "ARM": "Arm Holding",
    "HCC": "Warrior Met",
    "AMR": "Alpha Met.Res",
    "RIG": "Transocean",
    "SIE.DE": "Siemens AG",
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
    except Exception as e:
        print(f"  FX-Fehler {currency}: {e}")
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


def fetch_info_with_retry(t: yf.Ticker, sym: str, retries: int = 3):
    """
    Holt info-dict mit Retries + Backoff, da yfinance bei
    Rate-Limits (429) oder Yahoo-Hickups leere/unvollständige
    Daten liefern kann, ohne eine Exception zu werfen.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            info = t.get_info()  # frischer als das gecachte .info
            if info and (info.get("marketCap") or info.get("regularMarketPrice")):
                return info
            # info leer/unvollständig -> als "noch nicht gut genug" werten
            last_err = "leere/unvollständige Antwort"
        except Exception as e:
            last_err = str(e)

        if attempt < retries:
            wait = attempt * 2 + random.uniform(0, 1.5)
            print(f"  [{sym}] Versuch {attempt} fehlgeschlagen ({last_err}), warte {wait:.1f}s ...")
            time.sleep(wait)

    print(f"  [{sym}] Alle Versuche fehlgeschlagen: {last_err}")
    return None


def get_market_cap_fallback(t: yf.Ticker, info: dict):
    """
    Fallback-Kette für Market Cap, falls info['marketCap'] fehlt:
    1) info['marketCap']
    2) t.fast_info['market_cap']
    3) sharesOutstanding * aktueller Preis
    """
    raw_cap = info.get("marketCap")
    if raw_cap:
        return raw_cap

    try:
        fi = t.fast_info
        cap = fi.get("market_cap") if hasattr(fi, "get") else getattr(fi, "market_cap", None)
        if cap:
            return cap
    except Exception:
        pass

    try:
        shares = info.get("sharesOutstanding")
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if shares and price:
            return shares * price
    except Exception:
        pass

    return None


def send_mail(results, errors, timestamp):
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

    error_block = ""
    if errors:
        items = "".join(f"<li>{sym}: {msg_txt}</li>" for sym, msg_txt in errors)
        error_block = f"""
        <div style="margin-top:14px; color:#b91c1c; font-size:12px; line-height:1.4;">
          <b>Nicht geladen ({len(errors)}):</b>
          <ul style="margin:6px 0 0 18px; padding:0;">{items}</ul>
        </div>
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
            {error_block}
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
        print(f"Fehler beim Mailversand: {e}")


# --- DATEN SAMMELN ---
results = []
errors = []
print(f"Sammle Daten für {len(TICKERS)} Aktien...")

for sym, name in TICKERS.items():
    print(f"-> {sym} ({name})")
    try:
        t = yf.Ticker(sym)
        info = fetch_info_with_retry(t, sym)

        if not info:
            errors.append((sym, "keine Daten erhalten (Rate-Limit/leere Antwort)"))
            time.sleep(1.0 + random.uniform(0, 1.0))
            continue

        # Market Cap + Currency (mit Fallback-Kette)
        raw_cap = get_market_cap_fallback(t, info)
        ccy = info.get("currency") or info.get("financialCurrency") or "?"

        # KGV
        pe = info.get("trailingPE") or info.get("forwardPE")
        pe_val = float(pe) if pe else 999.0

        # Letzter Finanzbericht
        report = most_recent_quarter_from_info(info)

        cap_b = 0.0  # Market Cap in Milliarden
        cap_ccy = ccy

        if raw_cap:
            cap_b = float(raw_cap) / 1_000_000_000

            # Regel: alles außer EUR oder USD -> in EUR umrechnen
            if ccy not in ("EUR", "USD"):
                rate = get_fx_rate_to_eur(ccy)
                if rate:
                    cap_b = (float(raw_cap) * rate) / 1_000_000_000
                    cap_ccy = "EUR"
                else:
                    cap_b = 0.0
                    cap_ccy = "EUR"
                    errors.append((sym, f"FX-Kurs für {ccy} nicht verfügbar"))
        else:
            errors.append((sym, "marketCap nicht verfügbar (auch nicht über Fallback)"))

        results.append({
            "symbol": sym,
            "name": name[:14],
            "cap_b": cap_b,
            "cap_ccy": cap_ccy,
            "pe": pe_val,
            "report": report,
        })

    except Exception as e:
        print(f"  [{sym}] Fehler: {e}")
        errors.append((sym, str(e)))

    # etwas höherer, leicht zufälliger Delay -> schont Yahoo-Rate-Limit
    time.sleep(0.8 + random.uniform(0, 0.6))

# Sortierung nach KGV (wie bisher)
results.sort(key=lambda x: x["pe"])

timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
print(f"\nFertig: {len(results)} OK, {len(errors)} Fehler.")
if errors:
    for sym, msg_txt in errors:
        print(f"  - {sym}: {msg_txt}")

send_mail(results, errors, timestamp)
