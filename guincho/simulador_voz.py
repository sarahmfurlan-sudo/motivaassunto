"""Simulador do agente de voz, em texto, para demonstrar o function calling.

Você digita como se estivesse falando; o modelo local (Ollama) conversa, pede confirmação e
chama as funções de agente_voz.py. Nas próximas sprints, a fala real (speech-to-text) entra
no lugar do teclado e a resposta vira áudio (text-to-speech).
"""
from __future__ import annotations

import json

from . import config, ollama
from .agente_voz import FERRAMENTAS, executar_ferramenta

SISTEMA = """Você é o agente de voz que apoia agentes de inspeção de tráfego de uma concessionária
de rodovias. Respostas curtas, faladas, sem listas nem formatação, em português do Brasil.
Para registrar um pedido de guincho: se faltar rodovia, km ou sentido, pergunte só o que falta.
Depois repita os dados essenciais em uma frase e peça confirmação. Só registre após um 'sim',
chamando registrar_solicitacao_guincho com confirmado_pelo_usuario=true.
Ao receber o resultado de uma ferramenta, fale o campo 'mensagem_para_falar'."""

FERRAMENTAS_OLLAMA = [{"type": "function", "function": f} for f in FERRAMENTAS]


def conversar() -> None:
    if not config.USAR_IA:
        print("A IA está desligada (USAR_IA=nao no .env). Ligue para usar o simulador.")
        return
    historico: list[dict] = [{"role": "system", "content": SISTEMA}]
    print(f"Agente de voz (simulado, modelo {config.MODELO_IA}). Digite 'sair' para encerrar.\n")
    while True:
        fala = input("Você: ").strip()
        if fala.lower() in ("sair", "exit", "quit"):
            break
        if not fala:
            continue
        historico.append({"role": "user", "content": fala})
        for _ in range(5):  # limite de rodadas de ferramenta por fala
            try:
                msg = ollama.chat(historico, ferramentas=FERRAMENTAS_OLLAMA)
            except ollama.ErroOllama as e:
                print(f"[erro: {e}]\n")
                historico.pop()
                break
            historico.append(msg)
            chamadas = msg.get("tool_calls") or []
            if not chamadas:
                print(f"Agente: {msg.get('content', '').strip()}\n")
                break
            for c in chamadas:
                nome = c["function"]["name"]
                args = c["function"].get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args or "{}")
                print(f"  [chamando {nome}({json.dumps(args, ensure_ascii=False)})]")
                saida = executar_ferramenta(nome, args)
                historico.append({"role": "tool", "tool_name": nome,
                                  "content": json.dumps(saida, ensure_ascii=False, default=str)})
