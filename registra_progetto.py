# =============================================================================
# REGISTRA PROGETTO — Auto Occasioni Milano (da lanciare UNA volta, a mano)
# =============================================================================
# La Merchant API risponde solo ai progetti Google Cloud registrati
# sull'account Merchant Center (operazione unica, metodo registerGcp).
# La chiamata la fa il robot (account di servizio) con la sua chiave, che
# per questo deve essere utente ADMIN in Merchant Center. Dopo la
# registrazione il robot si può abbassare a STANDARD.
#
# Lancio: GitHub → Actions → "Registra progetto Merchant (una volta)" → Run.
# Chiave: segreto GitHub MERCHANT_SA_JSON. Nei registri solo esiti.
# =============================================================================

import json
import os
import sys

import requests

ACCOUNT_ID      = "5347086491"
DEVELOPER_EMAIL = "amministrazione@autoccasionimilano.it"   # referente tecnico (non può essere un robot)
URL = (f"https://merchantapi.googleapis.com/accounts/v1/"
       f"accounts/{ACCOUNT_ID}/developerRegistration:registerGcp")
SCOPE = "https://www.googleapis.com/auth/content"


def main():
    chiave = os.environ.get("MERCHANT_SA_JSON", "").strip()
    if not chiave:
        print("❌ Chiave Merchant non configurata (segreto MERCHANT_SA_JSON)")
        return 1
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        cred = service_account.Credentials.from_service_account_info(json.loads(chiave), scopes=[SCOPE])
        cred.refresh(Request())
    except Exception as e:
        print(f"❌ Chiave non valida ({type(e).__name__})")
        return 1
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {cred.token}"},
                          json={"developerEmail": DEVELOPER_EMAIL}, timeout=60)
    except requests.RequestException as e:
        print(f"❌ Errore di rete ({type(e).__name__})")
        return 1
    if r.status_code == 200:
        print("✅ Progetto registrato su Merchant Center. Aspettare 5 minuti prima di usare l'API.")
        print("   Se amministrazione@autoccasionimilano.it non era già utente di Merchant Center,")
        print("   aprire la mail di invito di Google e accettarla entro 14 giorni: la registrazione")
        print("   si completa solo dopo.")
        return 0
    motivo = ""
    try:
        js = r.json()
        if isinstance(js, dict) and isinstance(js.get("error"), dict):
            motivo = str(js["error"].get("status", ""))
    except ValueError:
        pass
    print(f"❌ Registrazione non riuscita: risposta {r.status_code} {motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
