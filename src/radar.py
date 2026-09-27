"""Radar de vagas.

Le feeds RSS e alertas de vaga no Gmail, filtra pelos termos configurados
em config.yml e envia no Telegram apenas o que ainda nao foi enviado.
"""

import hashlib
import html
import json
import os
import re"""Radar de vagas.

Le feeds RSS e alertas de vaga no Gmail, filtra pelos termos configurados
em config.yml e envia no Telegram apenas o que ainda nao foi enviado.
"""

import hashlib
import html
import json
import os
import re
import socket
import sys
import unicodedata
from pathlib import Path

import feedparser
import requests
import yaml

import fonte_gmail

socket.setdefaulttimeout(30)

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


def identificador(titulo, link):
    base = (link or "") + (titulo or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def limpar_link(link):
    """O Google Alerts embrulha o link real em um redirecionamento."""
    achado = re.search(r"[?&]url=([^&]+)", link or "")
    if achado:
        return requests.utils.unquote(achado.group(1))
    return link or ""


def avaliar(texto, incluir, excluir):
    """Devolve (passou, motivo). O motivo diz qual termo decidiu."""
    texto = normalizar(texto)

    bloqueios = [t for t in excluir if normalizar(t) in texto]
    if bloqueios:
        return False, "excluido por: " + ", ".join(bloqueios)

    encontrados = [t for t in incluir if normalizar(t) in texto]
    if encontrados:
        return True, "casou com: " + ", ".join(encontrados)

    return False, "nenhum termo de inclusao encontrado"


def passa_no_filtro(texto, incluir, excluir):
    return avaliar(texto, incluir, excluir)[0]


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

    diagnostico = os.environ.get("MODO_DIAGNOSTICO", "").lower() in ("1", "true", "sim")
    novos = []
    relatorio = []
    lidas = 0

    # --- fonte 1: feeds RSS ---
    print(f"rss: lendo {len(config['feeds'])} feed(s)...", flush=True)
    for url in config["feeds"]:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"aviso: falha ao ler {url}", file=sys.stderr)
            continue

        for entrada in feed.entries:
            lidas += 1
            titulo = html.unescape(re.sub(r"<[^>]+>", "", entrada.get("title", ""))).strip()
            link = limpar_link(entrada.get("link", ""))
            chave = identificador(titulo, link)

            if chave in vistos:
                continue
            vistos.add(chave)

            conteudo = f"{entrada.get('title', '')} {entrada.get('summary', '')}"
            passou, motivo = avaliar(conteudo, incluir, excluir)
            relatorio.append((passou, motivo, titulo, link, "rss"))
            if passou:
                novos.append((titulo, link))

    # --- fonte 2: alertas no Gmail ---
    gmail = config.get("gmail", {})
    usuario = os.environ.get("GMAIL_USER")
    senha = os.environ.get("GMAIL_APP_PASSWORD")

    if gmail.get("ativo") and usuario and senha:
        try:
            achados = fonte_gmail.coletar(
                usuario,
                senha,
                etiqueta=gmail.get("etiqueta", "Vagas"),
                limite=gmail.get("max_emails", 40),
            )
        except Exception as erro:
            print(f"aviso: falha ao ler o Gmail: {erro}", file=sys.stderr)
            achados = []

        for titulo, link, _remetente in achados:
            lidas += 1
            chave = identificador(titulo, link)

            if chave in vistos:
                continue
            vistos.add(chave)

            passou, motivo = avaliar(titulo, incluir, excluir)
            relatorio.append((passou, motivo, titulo, link, "gmail"))
            if passou:
                novos.append((titulo, link))

    if diagnostico:
        aprovadas = [r for r in relatorio if r[0]]
        reprovadas = [r for r in relatorio if not r[0]]

        print("\n=== MODO DIAGNOSTICO: nada foi enviado nem gravado ===\n")
        print(f"APROVADAS ({len(aprovadas)})")
        for _, motivo, titulo, link, fonte in aprovadas:
            print(f"  [{fonte}] {titulo}")
            print(f"     {motivo}")
            print(f"     {link}\n")

        print(f"DESCARTADAS ({len(reprovadas)})")
        for _, motivo, titulo, link, fonte in reprovadas:
            print(f"  [{fonte}] {titulo}")
            print(f"     {motivo}\n")

        print(f"total lido: {lidas}")
        return

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

import sys
import unicodedata
from pathlib import Path

import feedparser
import requests
import yaml

import fonte_gmail

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


def identificador(titulo, link):
    base = (link or "") + (titulo or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def limpar_link(link):
    """O Google Alerts embrulha o link real em um redirecionamento."""
    achado = re.search(r"[?&]url=([^&]+)", link or "")
    if achado:
        return requests.utils.unquote(achado.group(1))
    return link or ""


def avaliar(texto, incluir, excluir):
    """Devolve (passou, motivo). O motivo diz qual termo decidiu."""
    texto = normalizar(texto)

    bloqueios = [t for t in excluir if normalizar(t) in texto]
    if bloqueios:
        return False, "excluido por: " + ", ".join(bloqueios)

    encontrados = [t for t in incluir if normalizar(t) in texto]
    if encontrados:
        return True, "casou com: " + ", ".join(encontrados)

    return False, "nenhum termo de inclusao encontrado"


def passa_no_filtro(texto, incluir, excluir):
    return avaliar(texto, incluir, excluir)[0]


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

    diagnostico = os.environ.get("MODO_DIAGNOSTICO", "").lower() in ("1", "true", "sim")
    novos = []
    relatorio = []
    lidas = 0

    # --- fonte 1: feeds RSS ---
    for url in config["feeds"]:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"aviso: falha ao ler {url}", file=sys.stderr)
            continue

        for entrada in feed.entries:
            lidas += 1
            titulo = html.unescape(re.sub(r"<[^>]+>", "", entrada.get("title", ""))).strip()
            link = limpar_link(entrada.get("link", ""))
            chave = identificador(titulo, link)

            if chave in vistos:
                continue
            vistos.add(chave)

            conteudo = f"{entrada.get('title', '')} {entrada.get('summary', '')}"
            passou, motivo = avaliar(conteudo, incluir, excluir)
            relatorio.append((passou, motivo, titulo, link, "rss"))
            if passou:
                novos.append((titulo, link))

    # --- fonte 2: alertas no Gmail ---
    gmail = config.get("gmail", {})
    usuario = os.environ.get("GMAIL_USER")
    senha = os.environ.get("GMAIL_APP_PASSWORD")

    if gmail.get("ativo") and usuario and senha:
        try:
            achados = fonte_gmail.coletar(
                usuario, senha, etiqueta=gmail.get("etiqueta", "Vagas")
            )
        except Exception as erro:
            print(f"aviso: falha ao ler o Gmail: {erro}", file=sys.stderr)
            achados = []

        for titulo, link, _remetente in achados:
            lidas += 1
            chave = identificador(titulo, link)

            if chave in vistos:
                continue
            vistos.add(chave)

            passou, motivo = avaliar(titulo, incluir, excluir)
            relatorio.append((passou, motivo, titulo, link, "gmail"))
            if passou:
                novos.append((titulo, link))

    if diagnostico:
        aprovadas = [r for r in relatorio if r[0]]
        reprovadas = [r for r in relatorio if not r[0]]

        print("\n=== MODO DIAGNOSTICO: nada foi enviado nem gravado ===\n")
        print(f"APROVADAS ({len(aprovadas)})")
        for _, motivo, titulo, link, fonte in aprovadas:
            print(f"  [{fonte}] {titulo}")
            print(f"     {motivo}")
            print(f"     {link}\n")

        print(f"DESCARTADAS ({len(reprovadas)})")
        for _, motivo, titulo, link, fonte in reprovadas:
            print(f"  [{fonte}] {titulo}")
            print(f"     {motivo}\n")

        print(f"total lido: {lidas}")
        return

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
