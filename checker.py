#!/usr/bin/env python3
"""
Alerta Cidadania: consulta o processo no Giustizia Civile e avisa quando algo muda.

Baseado no endpoint usado pela GiustiziaCivileAPI (lucasprates), mas reescrito em
Python sem dependencias externas (so biblioteca padrao).

Configuracao 100% por variaveis de ambiente (no GitHub ficam em Secrets):

  Obrigatorias (do processo):
    GC_NUMERO        numero do ruolo (ex: 12345)
    GC_ANNO          ano do ruolo   (ex: 2024)
    GC_IDUFFICIO     codigo do tribunal (Roma = 0580910098)  [padrao: Roma]
    GC_REGISTRO      registro (cittadinanza = CC)             [padrao: CC]

  Obrigatorias (do app, capturadas com mitmproxy - ver README):
    GC_UUID, GC_TOKEN, GC_DEVICENAME, GC_DEVICEWIDTH, GC_DEVICEHEIGHT

  Opcionais:
    GC_APP_VERSION   (padrao 1.1.13)   GC_PLATFORM (padrao "iOS 12.1")

  Notificacao (configure pelo menos uma):
    E-mail Gmail:  SMTP_USER, SMTP_PASSWORD (senha de app), EMAIL_TO
                   (opcional SMTP_HOST=smtp.gmail.com, SMTP_PORT=465)
    Telegram:      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    ntfy.sh:       NTFY_TOPIC

Uso:
    python checker.py            # consulta, compara e notifica se mudou
    python checker.py --test     # so envia uma notificacao de teste
    python checker.py --parse arquivo.html   # testa o parser num HTML salvo
"""

import hashlib
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from html.parser import HTMLParser
from pathlib import Path

ENDPOINT = "https://mob.processotelematico.giustizia.it/proxy/index_mobile.php"
STATE_FILE = Path(__file__).parent / "state" / "ultimo_estado.json"
DATE_LINE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s*-\s*(.+)$")


def _load_dotenv():
    """Le um arquivo .env ao lado do script (para rodar no seu PC)."""
    f = Path(__file__).parent / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_dotenv()


def env(name, default=None, required=False):
    value = os.environ.get(name, "").strip() or default
    if required and not value:
        sys.exit(f"ERRO: variavel {name} nao configurada.")
    return value


# --------------------------------------------------------------------- consulta
def fetch_case():
    params = {
        "version": env("GC_APP_VERSION", "1.1.13"),
        "platform": env("GC_PLATFORM", "iOS 12.1"),
        "uuid": env("GC_UUID", required=True),
        "devicename": env("GC_DEVICENAME", required=True),
        "devicewidth": env("GC_DEVICEWIDTH", required=True),
        "deviceheight": env("GC_DEVICEHEIGHT", required=True),
        "token": env("GC_TOKEN", required=True),
        "azione": "direttarg_sicid_mobile",
        "registro": env("GC_REGISTRO", "CC"),
        "idufficio": env("GC_IDUFFICIO", "0580910098"),
        "numproc": env("GC_NUMERO", required=True),
        "aaproc": env("GC_ANNO", required=True),
        "tipoufficio": "1",
        "_": str(int(time.time() * 1000)),
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_1 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/16B92",
        "Accept": "*/*",
        "Accept-Language": "it-IT,it;q=0.9",
        "X-Requested-With": "it.giustizia.civile",
    })
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # rede instavel: tenta de novo com espera
            last_err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Falha ao acessar o Giustizia Civile: {last_err}")


# ----------------------------------------------------------------------- parser
class _Collector(HTMLParser):
    """Guarda todos os textos visiveis, em ordem, e o conteudo de algumas tags."""
    TAGS = {"numeroruolo", "annoruolo", "registro", "descufficio", "idufficio",
            "nomegiudice", "dataudienza", "errore"}

    def __init__(self):
        super().__init__()
        self.texts, self.tags, self._stack = [], {}, []

    def handle_starttag(self, tag, attrs):
        self._stack.append(tag)

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text or text == "/":
            return
        self.texts.append(text)
        if self._stack and self._stack[-1] in self.TAGS:
            self.tags.setdefault(self._stack[-1], text)


def parse_case(raw):
    p = _Collector()
    p.feed(raw)
    if "errore" in p.tags or "<Errore>" in raw:
        raise RuntimeError("O servidor respondeu com erro: "
                           + p.tags.get("errore", raw[:300]))

    def after(label):
        for i, t in enumerate(p.texts):
            if label.lower() in t.lower():
                rest = t.split(":", 1)[1].strip() if ":" in t else ""
                if rest:
                    return rest
                if i + 1 < len(p.texts):
                    return p.texts[i + 1]
        return None

    historico = []
    for t in p.texts:
        m = DATE_LINE.match(t)
        if m and t not in historico:
            historico.append(t)
    historico.sort(key=lambda h: datetime.strptime(h[:10], "%d/%m/%Y"))

    info = {
        "numero": p.tags.get("numeroruolo"),
        "ano": p.tags.get("annoruolo"),
        "tribunal": p.tags.get("descufficio"),
        "juiz": p.tags.get("nomegiudice"),
        "proxima_audiencia": p.tags.get("dataudienza"),
        "status_atual": after("Stato fascicolo"),
        "secao": after("Sezione"),
        "historico": historico,
    }
    if not info["status_atual"] and historico:
        info["status_atual"] = historico[-1]
    # impressao digital de todo o texto, para pegar mudancas que o parser nao conhece
    info["hash_pagina"] = hashlib.sha256("\n".join(p.texts).encode()).hexdigest()[:16]
    if not (info["status_atual"] or historico):
        raise RuntimeError("Resposta sem dados do processo (credenciais ou numero "
                           "podem estar errados). Inicio da resposta: " + raw[:300])
    return info


# -------------------------------------------------------------------- comparacao
def diff(old, new):
    if not old:
        return ["Primeira consulta registrada."]
    changes = []
    labels = {"status_atual": "Status", "proxima_audiencia": "Proxima audiencia",
              "juiz": "Juiz", "secao": "Secao"}
    for key, label in labels.items():
        if old.get(key) != new.get(key):
            changes.append(f"{label}: '{old.get(key)}' -> '{new.get(key)}'")
    novos = [h for h in new.get("historico", []) if h not in old.get("historico", [])]
    for h in novos:
        changes.append(f"Novo andamento: {h}")
    if not changes and old.get("hash_pagina") != new.get("hash_pagina"):
        changes.append("Algo mudou na pagina do processo (detalhe nao identificado).")
    return changes


def format_message(info, changes):
    lines = [f"Processo {info.get('numero') or env('GC_NUMERO')}/"
             f"{info.get('ano') or env('GC_ANNO')} - {info.get('tribunal') or ''}", ""]
    lines += ["MUDANCAS:"] + [f"- {c}" for c in changes] + [""]
    lines.append(f"Status atual: {info.get('status_atual')}")
    if info.get("proxima_audiencia"):
        lines.append(f"Proxima audiencia: {info['proxima_audiencia']}")
    if info.get("juiz"):
        lines.append(f"Juiz: {info['juiz']}")
    if info.get("historico"):
        lines += ["", "Historico:"] + [f"  {h}" for h in info["historico"]]
    return "\n".join(lines)


# ------------------------------------------------------------------ notificacoes
def notify(subject, body):
    sent = []
    if env("SMTP_USER") and env("SMTP_PASSWORD") and env("EMAIL_TO"):
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = subject, env("SMTP_USER"), env("EMAIL_TO")
        host, port = env("SMTP_HOST", "smtp.gmail.com"), int(env("SMTP_PORT", "465"))
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
            s.login(env("SMTP_USER"), env("SMTP_PASSWORD"))
            s.sendmail(env("SMTP_USER"), [a.strip() for a in env("EMAIL_TO").split(",")],
                       msg.as_string())
        sent.append("e-mail")
    if env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"):
        data = urllib.parse.urlencode({"chat_id": env("TELEGRAM_CHAT_ID"),
                                       "text": f"{subject}\n\n{body}"[:4000]}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
                               "/sendMessage", data=data, timeout=30).read()
        sent.append("telegram")
    if env("NTFY_TOPIC"):
        req = urllib.request.Request(f"https://ntfy.sh/{env('NTFY_TOPIC')}",
                                     data=body.encode("utf-8"),
                                     headers={"Title": subject.encode("ascii", "ignore").decode()})
        urllib.request.urlopen(req, timeout=30).read()
        sent.append("ntfy")
    print("Notificacao enviada por: " + (", ".join(sent) or "NENHUM canal configurado!"))


# ------------------------------------------------------------------------- main
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if "--test" in sys.argv:
        notify("Alerta Cidadania: teste", "Se voce recebeu isto, as notificacoes funcionam.")
        return
    if "--parse" in sys.argv:
        raw = Path(sys.argv[sys.argv.index("--parse") + 1]).read_text(encoding="utf-8")
        print(json.dumps(parse_case(raw), ensure_ascii=False, indent=2))
        return

    state = load_state()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        info = parse_case(fetch_case())
    except Exception as e:
        print(f"ERRO: {e}")
        # avisa so na primeira falha seguida, para nao lotar sua caixa
        if not state.get("erro_desde"):
            state["erro_desde"] = now
            save_state(state)
            notify("Alerta Cidadania: falha na consulta",
                   f"Nao consegui consultar o processo.\n\n{e}\n\n"
                   "Se continuar, o token do app pode ter expirado (ver README).")
        sys.exit(1)

    old = state.get("processo")
    changes = diff(old, info)
    if changes:
        notify(f"Processo de cidadania: {info.get('status_atual') or 'atualizacao'}",
               format_message(info, changes))
    else:
        print("Sem mudancas. Status:", info.get("status_atual"))
    if state.get("erro_desde"):
        print("Consulta voltou a funcionar.")
    save_state({"processo": info})  # sem data, para so gerar commit quando mudar


if __name__ == "__main__":
    main()
