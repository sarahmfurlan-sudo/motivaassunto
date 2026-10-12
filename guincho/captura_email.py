"""Captura por e-mail: lê os e-mails NÃO LIDOS da caixa configurada (IMAP).

- O texto da solicitação é o assunto + o corpo.
- Anexos CSV/XLSX são salvos na pasta entrada/ e seguem pela captura por arquivo.
- Depois de processado, o e-mail é marcado como lido. O Message-ID evita duplicar.
"""
from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header, make_header
from email.message import Message
from html import unescape

from . import config, pipeline
from .captura_arquivo import EXTENSOES
from .log import obter_logger

log = obter_logger()


def _decodificar(valor: str | None) -> str:
    return str(make_header(decode_header(valor))) if valor else ""


def _html_para_texto(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def extrair(msg: Message) -> tuple[str, list[tuple[str, bytes]]]:
    """Devolve (texto do corpo, anexos [(nome, conteúdo)])."""
    simples, html, anexos = [], [], []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        nome = parte.get_filename()
        if nome:
            anexos.append((_decodificar(nome), parte.get_payload(decode=True) or b""))
            continue
        conteudo = parte.get_payload(decode=True)
        if conteudo is None:
            continue
        texto = conteudo.decode(parte.get_content_charset() or "utf-8", errors="replace")
        if parte.get_content_type() == "text/plain":
            simples.append(texto)
        elif parte.get_content_type() == "text/html":
            html.append(_html_para_texto(texto))
    corpo = "\n".join(simples) if simples else "\n".join(html)
    # Corta o histórico de respostas ("Em ... escreveu:" / linhas citadas com ">").
    corpo = re.split(r"\n(?:Em .{5,120} escreveu:|On .{5,120} wrote:)", corpo)[0]
    corpo = "\n".join(l for l in corpo.splitlines() if not l.startswith(">"))
    return re.sub(r"\n{3,}", "\n\n", corpo).strip(), anexos


def processar_mensagem(msg: Message) -> dict | None:
    assunto = _decodificar(msg.get("Subject"))
    remetente = _decodificar(msg.get("From"))
    origem = f"email:{msg.get('Message-ID') or assunto + remetente}"
    corpo, anexos = extrair(msg)

    for nome, conteudo in anexos:
        if any(nome.lower().endswith(ext) for ext in EXTENSOES):
            destino = config.PASTA_ENTRADA / nome
            destino.write_bytes(conteudo)
            log.info("Anexo %s de %s salvo na pasta de entrada.", nome, remetente)

    texto = f"Assunto: {assunto}\n\n{corpo}".strip()
    if not corpo and anexos:
        return None  # e-mail só com planilha: a captura por arquivo cuida
    return pipeline.processar(texto, "email", remetente, origem)


def recolher() -> list[dict]:
    if not (config.IMAP_HOST and config.IMAP_USUARIO and config.IMAP_SENHA):
        log.info("Captura por e-mail desligada (IMAP não configurado no .env).")
        return []
    resultados = []
    with imaplib.IMAP4_SSL(config.IMAP_HOST) as imap:
        imap.login(config.IMAP_USUARIO, config.IMAP_SENHA)
        imap.select(config.IMAP_PASTA)
        _, ids = imap.search(None, "UNSEEN")
        for num in ids[0].split():
            _, partes = imap.fetch(num, "(BODY.PEEK[])")  # PEEK: só marca como lido se der certo
            msg = email.message_from_bytes(partes[0][1])
            try:
                r = processar_mensagem(msg)
                if r:
                    resultados.append(r)
                imap.store(num, "+FLAGS", "\\Seen")
            except Exception as e:
                log.error("E-mail '%s' não processado (fica como não lido): %s",
                          _decodificar(msg.get("Subject")), e)
    return resultados
