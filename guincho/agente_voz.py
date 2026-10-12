"""Funções que o agente de voz chama (Sprints 2+).

O agente de voz entende a fala; para AGIR, ele chama estas funções (function calling /
tool use). Elas usam o mesmo caminho do e-mail e da planilha (pipeline.processar).

- FERRAMENTAS: nome, descrição e parâmetros (JSON Schema) de cada função — o LLM lê isso para
  decidir quando chamar. É o formato usado por Ollama, OpenAI e similares (dentro de "function").
- executar_ferramenta(nome, argumentos): o "despachante" que o agente usa.
- As respostas trazem 'mensagem_para_falar', curta, pronta para virar áudio.

Governança (critérios de aceite da Motiva): registrar é ação crítica, então a função exige
'confirmado_pelo_usuario=True' — o agente precisa repetir os dados e ouvir um "sim" antes.
"""
from __future__ import annotations

from . import pipeline, registro

FERRAMENTAS = [
    {
        "name": "registrar_solicitacao_guincho",
        "description": (
            "Registra uma solicitação de guincho relatada por um agente em campo e a encaminha "
            "automaticamente à base responsável. ANTES de chamar, repita para o usuário o local "
            "(rodovia, km, sentido) e o tipo de veículo e peça confirmação. Só chame com "
            "confirmado_pelo_usuario=true depois de um 'sim' explícito."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relato": {"type": "string",
                           "description": "O relato completo do usuário, com as palavras dele."},
                "solicitante": {"type": "string", "description": "Nome ou matrícula de quem fala."},
                "confirmado_pelo_usuario": {"type": "boolean"},
                "latitude": {"type": "number", "description": "GPS do dispositivo, se houver."},
                "longitude": {"type": "number"},
            },
            "required": ["relato", "confirmado_pelo_usuario"],
        },
    },
    {
        "name": "consultar_solicitacao",
        "description": "Consulta status, prioridade e responsável de uma solicitação pelo protocolo "
                       "(ex.: GUI-20261012-0003).",
        "parameters": {
            "type": "object",
            "properties": {"protocolo": {"type": "string"}},
            "required": ["protocolo"],
        },
    },
]

_STATUS_FALADO = {
    "encaminhada": "encaminhada",
    "em_triagem": "em validação na mesa do CCO",
    "erro_encaminhamento": "registrada, mas o encaminhamento falhou; o CCO foi avisado pelo log",
}


def _protocolo_falado(p: str) -> str:
    return "final " + " ".join(p[-4:])  # "final 0 0 0 3" — fácil de ouvir e repetir


def registrar_solicitacao_guincho(relato: str, confirmado_pelo_usuario: bool, solicitante: str = "",
                                  latitude: float | None = None, longitude: float | None = None) -> dict:
    if not confirmado_pelo_usuario:
        return {"ok": False, "erro": "confirmacao_pendente",
                "mensagem_para_falar": "Antes de registrar, confirme: os dados estão corretos?"}
    r = pipeline.processar(relato, "voz", solicitante or "agente_de_voz", None, latitude, longitude)
    local = f"{r['rodovia']} quilômetro {r['km']:g}" if r["km"] is not None else "local a confirmar"
    if r["status"] == "em_triagem":
        fala = (f"Registrei o protocolo {_protocolo_falado(r['protocolo'])}, em {local}. "
                f"Ele foi para validação do CCO: {r['motivo_destino']}")
    else:
        fala = (f"Registrado. Protocolo {_protocolo_falado(r['protocolo'])}, prioridade {r['prioridade']}, "
                f"em {local}. Encaminhei para {r['responsavel']}.")
    return {"ok": True, **r, "mensagem_para_falar": fala}


def consultar_solicitacao(protocolo: str) -> dict:
    r = registro.obter(protocolo.strip())
    if not r:
        return {"ok": False, "erro": "nao_encontrado",
                "mensagem_para_falar": "Não encontrei esse protocolo. Pode repetir?"}
    fala = (f"O protocolo {_protocolo_falado(r['protocolo'])} está {_STATUS_FALADO.get(r['status'], r['status'])}, "
            f"prioridade {r['prioridade']}, com {r['responsavel']}.")
    return {"ok": True, "protocolo": r["protocolo"], "status": r["status"],
            "prioridade": r["prioridade"], "responsavel": r["responsavel"],
            "linha_do_tempo": r["eventos"], "mensagem_para_falar": fala}


_FUNCOES = {"registrar_solicitacao_guincho": registrar_solicitacao_guincho,
            "consultar_solicitacao": consultar_solicitacao}


def executar_ferramenta(nome: str, argumentos: dict) -> dict:
    if nome not in _FUNCOES:
        return {"ok": False, "erro": f"ferramenta desconhecida: {nome}"}
    try:
        return _FUNCOES[nome](**argumentos)
    except Exception as e:
        return {"ok": False, "erro": str(e),
                "mensagem_para_falar": "Não consegui concluir agora. Tente de novo ou fale com o CCO."}
