"""Encaminhamento ao responsável por e-mail.

Com SMTP configurado, envia de verdade. Sem SMTP, grava o e-mail pronto (.eml) em
saida/emails — dá para abrir no Outlook/Thunderbird e mostrar no vídeo.
Em modo demonstração (EMAIL_DEMO_PARA), tudo vai para a sua caixa de teste, porque os
responsáveis da tabela são fictícios; o corpo informa quem seria o destinatário real.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import config
from .roteamento import Destino

ROTULO_PRIORIDADE = {"alta": "ALTA", "media": "MÉDIA", "baixa": "BAIXA"}


def montar(protocolo: str, dados: dict, destino: Destino, texto_original: str, canal: str) -> EmailMessage:
    local = f"{dados.get('rodovia') or 'rodovia?'} km {dados['km']:g}" if dados.get("km") is not None \
        else (dados.get("rodovia") or "local não informado")
    acao = "TRIAGEM" if destino.triagem else "ACIONAMENTO"
    assunto = f"[GUINCHO][{ROTULO_PRIORIDADE[dados['prioridade']]}][{acao}] {protocolo} · {local} · {dados['resumo'][:70]}"

    msg = EmailMessage()
    msg["Subject"] = assunto[:200]
    msg["From"] = config.EMAIL_REMETENTE
    para_real = destino.email
    msg["To"] = config.EMAIL_DEMO_PARA or para_real
    if destino.copias and not config.EMAIL_DEMO_PARA:
        msg["Cc"] = ", ".join(destino.copias)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="guincho.local")
    msg["X-Protocolo"] = protocolo

    sim_nao = lambda v: "SIM" if v else "não"  # noqa: E731
    linhas = []
    if config.EMAIL_DEMO_PARA:
        linhas += [f"[MODO DEMONSTRAÇÃO] Destinatário real: {para_real}"
                   + (f" | cópia: {', '.join(destino.copias)}" if destino.copias else ""), ""]
    if destino.triagem:
        linhas += ["ATENÇÃO: este pedido precisa de VALIDAÇÃO HUMANA antes do acionamento.",
                   f"Motivo: {destino.motivo}", ""]
    linhas += [
        f"Protocolo:        {protocolo}",
        f"Prioridade:       {ROTULO_PRIORIDADE[dados['prioridade']]}",
        f"Encaminhado para: {destino.responsavel} ({destino.base}) {destino.telefone}",
        f"Por quê:          {destino.motivo}",
        "",
        "LOCAL",
        f"  Rodovia: {dados.get('rodovia') or '—'}   Km: {format(dados['km'], 'g') if dados.get('km') is not None else '—'}"
        f"   Sentido: {dados.get('sentido') or '—'}",
        f"  Posição: {dados.get('posicao', '—').replace('_', ' ')}",
        "",
        "VEÍCULO E SITUAÇÃO",
        f"  Tipo: {dados.get('tipo_veiculo', '—').replace('_', ' ')}   Placa: {dados.get('placa') or '—'}",
        f"  Motivo: {dados.get('motivo', '—').replace('_', ' ')}",
        f"  Vítimas: {sim_nao(dados.get('vitimas'))}   Carga perigosa: {sim_nao(dados.get('carga_perigosa'))}",
        "",
        f"Campos faltantes: {', '.join(dados.get('campos_faltantes') or []) or 'nenhum'}",
        f"Interpretação: {dados.get('metodo')} · confiança {dados.get('confianca', 0):.0%}",
        f"Justificativa da IA: {dados.get('justificativa', '')}",
        "",
        f"RELATO ORIGINAL (canal: {canal})",
        "-" * 60,
        texto_original.strip(),
        "-" * 60,
        "",
        "A IA apenas interpreta o relato. O acionamento do recurso é decisão do responsável.",
    ]
    msg.set_content("\n".join(linhas))
    return msg


def enviar(msg: EmailMessage) -> dict:
    # Só usa o SMTP com servidor E usuário preenchidos; senão, grava o .eml.
    if config.SMTP_HOST and config.SMTP_USUARIO:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORTA, timeout=30) as s:
            s.starttls()
            if config.SMTP_USUARIO:
                s.login(config.SMTP_USUARIO, config.SMTP_SENHA)
            s.send_message(msg)
        return {"modo": "smtp", "para": msg["To"]}
    caminho = config.PASTA_SAIDA_EMAILS / f"{msg['X-Protocolo']}.eml"
    caminho.write_bytes(bytes(msg))
    return {"modo": "arquivo", "para": msg["To"], "arquivo": str(caminho)}
