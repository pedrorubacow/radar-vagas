"""Radar de vagas.

Le feeds RSS de vagas, filtra pelos termos configurados em config.yml
e envia no Telegram apenas o que ainda nao foi enviado.
"""

import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import feedparser
import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.yml"
VISTOS = RAIZ / "vistos.json"
LIMITE_HISTORICO = 800


def normalizar(texto):
    """Minusculas, sem acento e sem tag HTML, para o filtro nao depender disso."""
    texto = html.unescape(texto or "")
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).lower()


def carregar_config():
    with open(CONFIG, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def carregar_vistos():
    if VISTOS.exists():
        return set(json.loads(VISTOS.read_text(encoding="utf-8")))
    return set()


def salvar_vistos(vistos):
    VISTOS.write_text(
        json.dumps(sorted(vistos)[-LIMITE_HISTORICO:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def identificador(entrada):
    base = (entrada.get("link") or "") + (entrada.get("title") or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def limpar_link(link):
    """O Google Alerts embrulha o link real em um redirecionamento."""
    achado = re.search(r"[?&]url=([^&]+)", link or "")
    if achado:
        return requests.utils.unquote(achado.group(1))
    return link or ""


def passa_no_filtro(texto, incluir, excluir):
    texto = normalizar(texto)
    if any(normalizar(termo) in texto for termo in excluir):
        return False
    return any(normalizar(termo) in texto for termo in incluir)


def enviar(mensagem, token, chat_id):
    resposta = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    resposta.raise_for_status()


def main():
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    config = carregar_config()
    vistos = carregar_vistos()
    incluir = config["incluir"]
    excluir = config["excluir"]
    limite = config.get("limite_por_mensagem", 15)

    novos = []
    lidas = 0

    for url in config["feeds"]:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"aviso: falha ao ler {url}", file=sys.stderr)
            continue

        for entrada in feed.entries:
            lidas += 1
            chave = identificador(entrada)
            if chave in vistos:
                continue

            vistos.add(chave)
            titulo = html.unescape(re.sub(r"<[^>]+>", "", entrada.get("title", "")))
            conteudo = f"{entrada.get('title', '')} {entrada.get('summary', '')}"

            if passa_no_filtro(conteudo, incluir, excluir):
                novos.append((titulo.strip(), limpar_link(entrada.get("link", ""))))

    if novos:
        linhas = ["<b>Vagas novas no radar</b>", ""]
        for titulo, link in novos[:limite]:
            linhas.append(f'• <a href="{html.escape(link)}">{html.escape(titulo)}</a>')
        if len(novos) > limite:
            linhas.append(f"\n... e mais {len(novos) - limite} nao exibidas.")
        enviar("\n".join(linhas), token, chat_id)
        print(f"{lidas} entrada(s) lida(s), {len(novos)} enviada(s)")
    else:
        print(f"{lidas} entrada(s) lida(s), nada novo dentro do filtro")

    salvar_vistos(vistos)


if __name__ == "__main__":
    main()
