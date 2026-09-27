"""Leitura dos alertas de vaga no Gmail via IMAP.

Le apenas os e-mails nao lidos de uma etiqueta especifica, extrai os links
de vaga do corpo HTML e marca as mensagens como lidas ao final.
"""

import email
import html
import imaplib
import re
from email.header import decode_header, mak"""Leitura dos alertas de vaga no Gmail via IMAP.

Le apenas os e-mails nao lidos de uma etiqueta especifica, extrai os links
de vaga do corpo HTML e marca as mensagens como lidas ao final.
"""

import email
import html
import imaplib
import re
import socket
import sys
from email.header import decode_header, make_header

# Dominios cujos links valem a pena aproveitar de dentro do e-mail
DOMINIOS_DE_VAGA = (
    "linkedin.com/jobs",
    "linkedin.com/comm/jobs",
    "indeed.com",
    "glassdoor.com",
    "gupy.io",
    "coodesh.com",
    "geekhunter.com.br",
    "/vaga",
    "/vagas",
    "/job",
)

# Links de rodape que aparecem em todo alerta e nunca sao vaga
RUIDO = (
    "unsubscribe",
    "descadastrar",
    "cancelar-inscricao",
    "preferencias",
    "preferences",
    "settings",
    "privacy",
    "privacidade",
    "help",
    "ajuda",
    "/legal",
    "play.google.com",
    "apps.apple.com",
)

ANCORA = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")


def _texto(bruto):
    texto = html.unescape(TAG.sub(" ", bruto or ""))
    return re.sub(r"\s+", " ", texto).strip()


def _e_vaga(url, titulo):
    url_baixa = url.lower()
    if any(r in url_baixa for r in RUIDO):
        return False
    if not any(d in url_baixa for d in DOMINIOS_DE_VAGA):
        return False
    # titulo curto demais costuma ser botao ("ver", "aqui", logo da empresa)
    return len(titulo) >= 12


def _corpo_html(mensagem):
    partes = []
    if mensagem.is_multipart():
        for parte in mensagem.walk():
            if parte.get_content_type() == "text/html":
                partes.append(parte)
    elif mensagem.get_content_type() == "text/html":
        partes.append(mensagem)

    corpo = ""
    for parte in partes:
        carga = parte.get_payload(decode=True)
        if carga:
            corpo += carga.decode(parte.get_content_charset() or "utf-8", errors="replace")
    return corpo


def extrair_vagas(corpo_html):
    """Devolve pares (titulo, url) que parecem vaga dentro do HTML do alerta."""
    achados = []
    vistos_na_mensagem = set()

    for url, miolo in ANCORA.findall(corpo_html):
        titulo = _texto(miolo)
        url = html.unescape(url).strip()

        if not _e_vaga(url, titulo):
            continue
        if url in vistos_na_mensagem:
            continue

        vistos_na_mensagem.add(url)
        achados.append((titulo, url))

    return achados


def coletar(
    usuario,
    senha_de_app,
    etiqueta="Vagas",
    servidor="imap.gmail.com",
    limite=40,
    timeout=30,
):
    """Le os e-mails nao lidos da etiqueta e devolve (titulo, url, remetente).

    O timeout evita que uma conexao pendurada trave o job inteiro, e o limite
    impede que um acumulo grande de e-mails estoure o tempo de execucao.
    """
    print(f"gmail: conectando em {servidor}...", flush=True)
    conexao = imaplib.IMAP4_SSL(servidor, timeout=timeout)
    resultados = []

    try:
        conexao.login(usuario, senha_de_app)
        print("gmail: autenticado", flush=True)
        status, _ = conexao.select(f'"{etiqueta}"')
        if status != "OK":
            raise RuntimeError(f'etiqueta "{etiqueta}" nao encontrada no Gmail')

        status, dados = conexao.search(None, "UNSEEN")
        if status != "OK" or not dados or not dados[0]:
            print("gmail: nenhum e-mail nao lido na etiqueta", flush=True)
            return resultados

        ids = dados[0].split()
        total = len(ids)
        if total > limite:
            # os mais recentes primeiro: o acumulo antigo fica para a proxima rodada
            ids = ids[-limite:]
            print(f"gmail: {total} nao lidos, processando os {limite} mais recentes", flush=True)
        else:
            print(f"gmail: {total} e-mail(s) nao lido(s)", flush=True)

        processados = []

        for posicao, identificador in enumerate(ids, start=1):
            try:
                status, bruto = conexao.fetch(identificador, "(BODY.PEEK[])")
            except (socket.timeout, OSError) as erro:
                print(f"gmail: falha ao ler e-mail {posicao}: {erro}", file=sys.stderr, flush=True)
                break

            if status != "OK" or not bruto or not bruto[0]:
                continue

            if posicao % 10 == 0:
                print(f"gmail: {posicao}/{len(ids)} lidos", flush=True)

            mensagem = email.message_from_bytes(bruto[0][1])
            remetente = str(make_header(decode_header(mensagem.get("From", ""))))
            for titulo, url in extrair_vagas(_corpo_html(mensagem)):
                resultados.append((titulo, url, remetente))

            processados.append(identificador)

        # so marca como lido o que foi processado sem erro
        if processados:
            conexao.store(b",".join(processados), "+FLAGS", "\\Seen")
            print(f"gmail: {len(processados)} marcado(s) como lido", flush=True)

    finally:
        try:
            conexao.close()
        except Exception:
            pass
        conexao.logout()

    return resultados
e_header

# Dominios cujos links valem a pena aproveitar de dentro do e-mail
DOMINIOS_DE_VAGA = (
    "linkedin.com/jobs",
    "linkedin.com/comm/jobs",
    "indeed.com",
    "glassdoor.com",
    "gupy.io",
    "coodesh.com",
    "geekhunter.com.br",
    "/vaga",
    "/vagas",
    "/job",
)

# Links de rodape que aparecem em todo alerta e nunca sao vaga
RUIDO = (
    "unsubscribe",
    "descadastrar",
    "cancelar-inscricao",
    "preferencias",
    "preferences",
    "settings",
    "privacy",
    "privacidade",
    "help",
    "ajuda",
    "/legal",
    "play.google.com",
    "apps.apple.com",
)

ANCORA = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")


def _texto(bruto):
    texto = html.unescape(TAG.sub(" ", bruto or ""))
    return re.sub(r"\s+", " ", texto).strip()


def _e_vaga(url, titulo):
    url_baixa = url.lower()
    if any(r in url_baixa for r in RUIDO):
        return False
    if not any(d in url_baixa for d in DOMINIOS_DE_VAGA):
        return False
    # titulo curto demais costuma ser botao ("ver", "aqui", logo da empresa)
    return len(titulo) >= 12


def _corpo_html(mensagem):
    partes = []
    if mensagem.is_multipart():
        for parte in mensagem.walk():
            if parte.get_content_type() == "text/html":
                partes.append(parte)
    elif mensagem.get_content_type() == "text/html":
        partes.append(mensagem)

    corpo = ""
    for parte in partes:
        carga = parte.get_payload(decode=True)
        if carga:
            corpo += carga.decode(parte.get_content_charset() or "utf-8", errors="replace")
    return corpo


def extrair_vagas(corpo_html):
    """Devolve pares (titulo, url) que parecem vaga dentro do HTML do alerta."""
    achados = []
    vistos_na_mensagem = set()

    for url, miolo in ANCORA.findall(corpo_html):
        titulo = _texto(miolo)
        url = html.unescape(url).strip()

        if not _e_vaga(url, titulo):
            continue
        if url in vistos_na_mensagem:
            continue

        vistos_na_mensagem.add(url)
        achados.append((titulo, url))

    return achados


def coletar(usuario, senha_de_app, etiqueta="Vagas", servidor="imap.gmail.com"):
    """Le os e-mails nao lidos da etiqueta e devolve (titulo, url, remetente)."""
    conexao = imaplib.IMAP4_SSL(servidor)
    resultados = []

    try:
        conexao.login(usuario, senha_de_app)
        status, _ = conexao.select(f'"{etiqueta}"')
        if status != "OK":
            raise RuntimeError(f'etiqueta "{etiqueta}" nao encontrada no Gmail')

        status, dados = conexao.search(None, "UNSEEN")
        if status != "OK" or not dados or not dados[0]:
            return resultados

        ids = dados[0].split()
        processados = []

        for identificador in ids:
            status, bruto = conexao.fetch(identificador, "(BODY.PEEK[])")
            if status != "OK" or not bruto or not bruto[0]:
                continue

            mensagem = email.message_from_bytes(bruto[0][1])
            remetente = str(make_header(decode_header(mensagem.get("From", ""))))
            for titulo, url in extrair_vagas(_corpo_html(mensagem)):
                resultados.append((titulo, url, remetente))

            processados.append(identificador)

        # so marca como lido o que foi processado sem erro
        for identificador in processados:
            conexao.store(identificador, "+FLAGS", "\\Seen")

    finally:
        try:
            conexao.close()
        except Exception:
            pass
        conexao.logout()

    return resultados
