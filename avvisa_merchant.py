# =============================================================================
# AVVISA MERCHANT — Auto Occasioni Milano
# =============================================================================
# Dopo che il workflow ha pubblicato il feed nuovo, chiede a Google Merchant
# Center di leggerlo subito (Merchant API, dataSources.fetch), invece di
# aspettare la lettura programmata delle 00:00, che resta come riserva.
#
# Prima di avvisare Merchant aspetta che l'indirizzo pubblico del feed
# (GitHub Pages, quello impostato in Merchant; tiene una copia in cache fino
# a 10 minuti) serva davvero il file nuovo: lo confronta byte per byte con quello appena
# generato. Se dopo ATTESA_MAX secondi non è ancora uguale, si ferma con errore
# e Merchant NON viene avvisato (meglio il feed di ieri che uno a metà).
#
# Chiave: variabile d'ambiente MERCHANT_SA_JSON (segreto di GitHub, mai nel
# codice né nei registri). Se manca, lo script non fa niente ed esce senza
# errore: il feed continua a funzionare come prima.
#
# Il repo è pubblico: nei registri solo esiti, mai chiavi o contenuti.
# =============================================================================

import hashlib
import json
import os
import sys
import time

import requests

ACCOUNT_ID    = "5347086491"     # Merchant Center Auto Occasioni Milano
DATASOURCE_ID = "10651790139"    # origine "PRODUCTS SOURCE 1"
# Indirizzo GitHub Pages di QUESTO archivio (ricavato da GITHUB_REPOSITORY).
# Prima di avvisare, lo script legge da Merchant quale indirizzo legge davvero
# (fetchUri dell'origine dati): se non è questo, non avvisa (es. durante la
# settimana di prova dopo lo spostamento, quando Merchant legge ancora il vecchio).
_ARCHIVIO     = os.environ.get("GITHUB_REPOSITORY", "tramontie-maker/vehicle-feed")
_PROPR, _NOME = _ARCHIVIO.split("/", 1)
FEED_URL      = os.environ.get("FEED_URL") or f"https://{_PROPR.lower()}.github.io/{_NOME}/feed_auto_google.xml"
FEED_LOCALE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feed_auto_google.xml")
SCOPE         = "https://www.googleapis.com/auth/content"
FETCH_URL     = (f"https://merchantapi.googleapis.com/datasources/v1/"
                 f"accounts/{ACCOUNT_ID}/dataSources/{DATASOURCE_ID}:fetch")
ATTESA_MAX    = int(os.environ.get("ATTESA_MAX", "900"))   # secondi
PAUSA         = int(os.environ.get("PAUSA", "60"))         # secondi tra un controllo e l'altro
ATTESA_CACHE  = int(os.environ.get("ATTESA_CACHE", "600"))  # secondi dopo che il feed pubblico è aggiornato


def impronta(dati):
    return hashlib.sha256(dati).hexdigest()


def aspetta_feed_pubblico(atteso):
    """Ritorna True quando l'indirizzo pubblico serve esattamente il file atteso."""
    inizio = time.time()
    while True:
        try:
            r = requests.get(FEED_URL, timeout=30)
            if r.status_code == 200 and impronta(r.content) == atteso:
                print(f"✅ Feed pubblico aggiornato dopo {int(time.time() - inizio)} s")
                return True
            print(f"   feed pubblico non ancora aggiornato (risposta {r.status_code})")
        except requests.RequestException:
            print("   feed pubblico non raggiungibile, riprovo")
        if time.time() - inizio + PAUSA > ATTESA_MAX:
            return False
        time.sleep(PAUSA)


def token_accesso(chiave_json):
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    info = json.loads(chiave_json)
    cred = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    cred.refresh(Request())
    return cred.token


def indirizzo_letto_da_merchant(tok):
    """Ritorna l'indirizzo che Merchant legge per l'origine dati, o None."""
    url = (f"https://merchantapi.googleapis.com/datasources/v1/"
           f"accounts/{ACCOUNT_ID}/dataSources/{DATASOURCE_ID}")
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
        js = r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(js, dict):
        return None
    return ((js.get("fileInput") or {}).get("fetchSettings") or {}).get("fetchUri")


def main():
    chiave = os.environ.get("MERCHANT_SA_JSON", "").strip()
    if not chiave:
        print("ℹ️  Chiave Merchant non configurata: nessun avviso, resta la lettura delle 00:00")
        return 0

    try:
        tok = token_accesso(chiave)
    except Exception as e:
        print(f"❌ MERCHANT NON AVVISATO: chiave non valida ({type(e).__name__})")
        return 1

    letto = indirizzo_letto_da_merchant(tok)
    if letto is None:
        print("❌ MERCHANT NON AVVISATO: impossibile leggere l'origine dati in Merchant")
        return 1
    if letto.rstrip("/").lower() != FEED_URL.rstrip("/").lower():
        print("ℹ️  Merchant legge un altro indirizzo, non questo archivio: nessun avviso")
        return 0

    with open(FEED_LOCALE, "rb") as f:
        atteso = impronta(f.read())

    if not aspetta_feed_pubblico(atteso):
        print(f"❌ MERCHANT NON AVVISATO: dopo {ATTESA_MAX} s il feed pubblico non è ancora quello nuovo")
        return 1

    # La cache di GitHub Pages dura fino a 600 s e Google può leggere da
    # un'altra copia: aspetto che scada anche quella.
    time.sleep(ATTESA_CACHE)

    # Il token dura un'ora: lo rinnovo dopo le attese
    try:
        tok = token_accesso(chiave)
    except Exception as e:
        print(f"❌ MERCHANT NON AVVISATO: chiave non valida ({type(e).__name__})")
        return 1

    try:
        r = requests.post(FETCH_URL, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    except requests.RequestException as e:
        print(f"❌ MERCHANT NON AVVISATO: errore di rete ({type(e).__name__})")
        return 1
    if r.status_code == 200:
        print("✅ Merchant avvisato: legge il feed adesso")
        return 0
    motivo = ""
    try:
        js = r.json()
        if isinstance(js, dict) and isinstance(js.get("error"), dict):
            motivo = str(js["error"].get("status", ""))
    except ValueError:
        pass
    print(f"❌ MERCHANT NON AVVISATO: risposta {r.status_code} {motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
