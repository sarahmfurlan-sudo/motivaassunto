"""Cliente mínimo do Ollama: IA rodando no próprio computador, gratuita e sem limite de uso.

Instalação: https://ollama.com/download  →  depois, no terminal: ollama pull qwen2.5:3b
O Ollama fica ouvindo em http://localhost:11434 enquanto estiver aberto.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import config


class ErroOllama(RuntimeError):
    pass


def chat_completo(mensagens: list[dict], formato: dict | str | None = None,
                  ferramentas: list[dict] | None = None, timeout: int | None = None) -> dict:
    """Chama /api/chat e devolve a resposta completa do Ollama (com tempos e contagens).

    formato: um JSON Schema (obriga a resposta a seguir o esquema) ou "json" (só JSON válido).
    ferramentas: funções que o modelo pode pedir para chamar (function calling).
    """
    corpo = {"model": config.MODELO_IA, "messages": mensagens, "stream": False,
             # num_predict limita o tamanho da resposta: se o modelo entrar em loop, para logo.
             "options": {"temperature": 0, "num_predict": config.IA_MAX_TOKENS}}
    if formato:
        corpo["format"] = formato
    if ferramentas:
        corpo["tools"] = ferramentas
    req = urllib.request.Request(f"{config.OLLAMA_URL.rstrip('/')}/api/chat",
                                 data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout or config.IA_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")[:300]
        if e.code == 404:
            raise ErroOllama(f"modelo '{config.MODELO_IA}' não baixado. Rode: ollama pull {config.MODELO_IA}") from e
        raise ErroOllama(f"HTTP {e.code}: {detalhe}") from e
    except urllib.error.URLError as e:
        raise ErroOllama(f"Ollama não está rodando em {config.OLLAMA_URL} ({e.reason})") from e
    except TimeoutError as e:
        raise ErroOllama(f"sem resposta em {timeout or config.IA_TIMEOUT}s") from e


def chat(mensagens: list[dict], formato: dict | str | None = None, ferramentas: list[dict] | None = None,
         timeout: int | None = None) -> dict:
    """Igual a chat_completo, mas devolve só a mensagem do modelo."""
    return chat_completo(mensagens, formato, ferramentas, timeout)["message"]
