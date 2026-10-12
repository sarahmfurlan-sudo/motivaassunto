"""Interpretação da solicitação.

A IA (um modelo local, via Ollama, gratuito) lê o texto livre — e-mail, linha de planilha ou
fala transcrita — e devolve os dados organizados, sempre no mesmo formato (saída estruturada:
a resposta é obrigada a seguir um esquema JSON). Se a IA estiver indisponível, um plano B por regras simples assume, para a
operação não parar; o registro guarda qual dos dois métodos foi usado.

Importante: a IA só INTERPRETA. Quem decide para quem vai é a regra de encaminhamento
(roteamento.py), que qualquer pessoa consegue conferir.
"""
from __future__ import annotations

import re
import unicodedata

from . import config
from .log import obter_logger

log = obter_logger()

TIPOS_VEICULO = ["moto", "leve", "utilitario", "caminhao", "onibus", "nao_informado"]
POSICOES = ["acostamento", "faixa_de_rolamento", "canteiro", "area_de_escape", "nao_informado"]
MOTIVOS = ["pane_mecanica", "pane_eletrica", "pneu", "pane_seca", "colisao", "superaquecimento",
           "outro", "nao_informado"]

ESQUEMA = {
    "type": "object",
    "properties": {
        "categoria": {
            "type": "string", "enum": ["guincho", "outro"],
            "description": "'guincho' se o pedido envolve remoção/reboque/assistência a veículo "
                           "parado ou avariado; 'outro' para qualquer outro assunto.",
        },
        "tipo_veiculo": {"type": "string", "enum": TIPOS_VEICULO},
        "rodovia": {"type": ["string", "null"],
                    "description": "Sigla normalizada, ex.: 'SP-348', 'SP-270', 'RJ-124'. "
                                   "Converta nomes: Bandeirantes=SP-348, Anhanguera=SP-330, "
                                   "Raposo Tavares=SP-270, Rodovia dos Lagos=RJ-124, "
                                   "Rodoanel Mário Covas=SP-021. null se não informada."},
        "km": {"type": ["number", "null"], "description": "Quilômetro (número). null se ausente."},
        "sentido": {"type": ["string", "null"],
                    "description": "Ex.: 'capital', 'interior', 'norte', 'sul', 'leste', 'oeste'."},
        "posicao": {"type": "string", "enum": POSICOES},
        "motivo": {"type": "string", "enum": MOTIVOS},
        "vitimas": {"type": "boolean", "description": "true se houver ferido ou relato de vítima."},
        "carga_perigosa": {"type": "boolean"},
        "placa": {"type": ["string", "null"]},
        "prioridade": {
            "type": "string", "enum": ["alta", "media", "baixa"],
            "description": "alta: vítima, faixa de rolamento obstruída, carga perigosa ou risco "
                           "imediato; media: veículo no acostamento sem vítima; baixa: demais.",
        },
        "resumo": {"type": "string", "description": "Uma linha, até 120 caracteres, para o título."},
        "campos_faltantes": {
            "type": "array", "items": {"type": "string"},
            "description": "Informações essenciais ausentes (rodovia, km, sentido, tipo_veiculo).",
        },
        "confianca": {"type": "number",
                      "description": "Sua confiança na interpretação, de 0 a 1."},
        "justificativa": {"type": "string",
                          "description": "Em uma frase, por que classificou e priorizou assim."},
    },
    "required": ["categoria", "tipo_veiculo", "rodovia", "km", "sentido", "posicao", "motivo",
                 "vitimas", "carga_perigosa", "placa", "prioridade", "resumo",
                 "campos_faltantes", "confianca", "justificativa"],
}

INSTRUCOES = """Você apoia o Centro de Controle Operacional (CCO) de uma concessionária de rodovias.
Recebe relatos de campo (e-mails, planilhas de turno ou fala transcrita de agentes de inspeção
de tráfego) e extrai os dados para abrir o registro de uma solicitação de guincho.
Regras:
- Use somente o que está no texto. Nunca invente km, rodovia, placa ou vítimas.
- Se algo essencial faltar, deixe null e liste em campos_faltantes.
- Textos de campo são curtos e informais ("kombi quebrada no 98 da bandeirantes sentido sp").
- Rodovias: Bandeirantes=SP-348, Anhanguera=SP-330, Raposo Tavares=SP-270,
  Rodovia dos Lagos=RJ-124, Rodoanel Mário Covas=SP-021.
- Caminhão, carreta, bitrem => caminhao. Ônibus => onibus. Van, pick-up, kombi => utilitario.
  Carro de passeio => leve.
- Prioridade: alta se há vítima, faixa de rolamento obstruída, carga perigosa ou risco imediato;
  media se o veículo está no acostamento sem vítima; baixa nos demais casos.
- Responda somente com o JSON pedido."""


def interpretar(texto: str) -> dict:
    """Interpreta o texto. Usa a IA local; se ela falhar ou estiver desligada, usa o plano B."""
    if config.USAR_IA:
        try:
            dados = _interpretar_com_ia(texto)
            dados["metodo"] = f"ia:{config.MODELO_IA}"
            return _normalizar(dados)
        except Exception as e:  # Ollama fechado, modelo não baixado, resposta inválida...
            log.warning("IA indisponível (%s). Usando o plano B por regras.", e)
    dados = interpretar_por_regras(texto)
    dados["metodo"] = "regras"
    return _normalizar(dados)


def _guia_dos_campos() -> str:
    """Descreve os campos do ESQUEMA em texto, para o modelo saber o que devolver."""
    linhas = []
    for nome, prop in ESQUEMA["properties"].items():
        tipo = prop.get("type")
        tipo = " ou ".join(tipo) if isinstance(tipo, list) else tipo
        valores = f" — um destes: {', '.join(prop['enum'])}" if "enum" in prop else ""
        linhas.append(f'- "{nome}" ({tipo}){valores}')
    return "\n".join(linhas)


EXEMPLO_SAIDA = {
    "categoria": "guincho", "tipo_veiculo": "leve", "rodovia": "SP-348", "km": 42,
    "sentido": "capital", "posicao": "acostamento", "motivo": "pneu", "vitimas": False,
    "carga_perigosa": False, "placa": None, "prioridade": "media",
    "resumo": "Gol parado no acostamento com pneu estourado", "campos_faltantes": [],
    "confianca": 0.9, "justificativa": "Carro leve no acostamento, sem vítimas: prioridade média.",
}


def montar_mensagens(texto: str) -> list[dict]:
    import json

    instrucoes = (f"{INSTRUCOES}\n\nDevolva um objeto JSON com exatamente estes campos:\n"
                  f"{_guia_dos_campos()}\n\nExemplo de resposta para "
                  f"\"Gol no acostamento km 42 da Bandeirantes sentido capital, pneu estourado\":\n"
                  f"{json.dumps(EXEMPLO_SAIDA, ensure_ascii=False)}")
    return [{"role": "system", "content": instrucoes},
            {"role": "user", "content": f"Relato recebido:\n\"\"\"\n{texto}\n\"\"\""}]


def _interpretar_com_ia(texto: str) -> dict:
    """Chama o modelo local pedindo um JSON com os campos de ESQUEMA.

    Usa o modo "json" do Ollama (garante JSON válido) com os campos descritos no texto.
    O modo com esquema obrigatório ficou lento demais em computadores sem placa de vídeo.
    O resultado é conferido e corrigido em _normalizar.
    """
    import json

    from . import ollama

    resposta = ollama.chat(montar_mensagens(texto), formato="json")
    try:
        dados = json.loads(resposta.get("content", ""))
    except json.JSONDecodeError as e:
        raise RuntimeError("a IA não devolveu um JSON válido") from e
    if not isinstance(dados, dict) or "categoria" not in dados:
        raise RuntimeError("a IA não devolveu os campos esperados")
    # Campos secundários ausentes recebem valores seguros (confiança baixa => triagem humana).
    dados.setdefault("resumo", _resumo(texto))
    dados.setdefault("confianca", 0.5)
    dados.setdefault("justificativa", "")
    for campo in ("rodovia", "km", "sentido", "placa"):
        dados.setdefault(campo, None)
    return dados


# ---------------------------------------------------------------- plano B (sem IA)

_RODOVIAS = {
    "bandeirantes": "SP-348", "anhanguera": "SP-330", "raposo": "SP-270",
    "rodovia dos lagos": "RJ-124", "via lagos": "RJ-124", "rodoanel": "SP-021",
}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def interpretar_por_regras(texto: str) -> dict:
    t = _sem_acento(texto)

    rodovia = None
    m = re.search(r"\b(sp|br|rj|pr|ms|mg|sc|rs)\s*-?\s*(\d{2,3})\b", t)
    if m:
        rodovia = f"{m.group(1).upper()}-{int(m.group(2)):03d}"
    else:
        for nome, sigla in _RODOVIAS.items():
            if nome in t:
                rodovia = sigla
                break

    km = None
    m = re.search(r"\bkm\s*(\d+(?:[.,]\d+)?)", t) or re.search(r"\bno\s+(\d{1,3})\b", t)
    if m:
        km = float(m.group(1).replace(",", "."))

    sentido = None
    m = re.search(r"sentido\s+(capital|interior|norte|sul|leste|oeste|sao paulo|sp)", t)
    if m:
        sentido = "capital" if m.group(1) in ("sao paulo", "sp") else m.group(1)

    if re.search(r"caminh|carreta|bitrem|onibus|treminhao", t):
        tipo = "onibus" if "onibus" in t else "caminhao"
    elif re.search(r"\bmotos?\b|motocicl", t):
        tipo = "moto"
    elif re.search(r"\bvan\b|pick-?up|kombi|utilitario|furgao", t):
        tipo = "utilitario"
    elif re.search(r"carro|veiculo|automovel|sedan|hatch|gol|palio|onix|ka\b|uno", t):
        tipo = "leve"
    else:
        tipo = "nao_informado"

    if "acostamento" in t:
        posicao = "acostamento"
    elif re.search(r"faixa|pista|bloque|obstru", t):
        posicao = "faixa_de_rolamento"
    elif "canteiro" in t:
        posicao = "canteiro"
    else:
        posicao = "nao_informado"

    motivos = [("colisao", r"colis|batida|bateu|acidente|engavet"), ("pneu", r"pneu"),
               ("pane_seca", r"pane seca|sem combust|gasolina acabou"),
               ("superaquecimento", r"superaquec|ferveu|fervendo"),
               ("pane_eletrica", r"eletric|bateria"), ("pane_mecanica", r"pane|quebr|motor|cambio")]
    motivo = next((nome for nome, rx in motivos if re.search(rx, t)), "nao_informado")

    vitimas = bool(re.search(r"vitima|ferid|machucad|socorro medico|\baph\b|dor n|desacordad|inconscient|presa? nas? ferragens", t)) and not re.search(
        r"(sem|nenhuma?|ninguem)\s+(vitimas?|ferid|machucad)|nao ha (vitimas?|ferid)", t)
    carga_perigosa = bool(re.search(r"carga perigosa|produto perigoso|inflamavel|vazamento de (combustivel|oleo|produto)|caminhao-?tanque|quimic", t))

    placa = None
    m = re.search(r"\b([a-z]{3})-?(\d[a-z0-9]\d{2})\b", t)
    if m:
        placa = f"{m.group(1)}{m.group(2)}".upper()

    if vitimas or carga_perigosa or posicao == "faixa_de_rolamento":
        prioridade = "alta"
    elif posicao == "acostamento" or motivo == "colisao":
        prioridade = "media"
    else:
        prioridade = "baixa"

    eh_guincho = bool(re.search(r"guinch|reboq|remoc|pane|quebr|parad|avari|colis|pneu|batid|acidente|tomb|superaquec|nao liga|apagou", t))
    faltantes = [n for n, v in (("rodovia", rodovia), ("km", km), ("sentido", sentido)) if v is None]
    if tipo == "nao_informado":
        faltantes.append("tipo_veiculo")

    return {
        "categoria": "guincho" if eh_guincho else "outro",
        "tipo_veiculo": tipo, "rodovia": rodovia, "km": km, "sentido": sentido,
        "posicao": posicao, "motivo": motivo, "vitimas": vitimas,
        "carga_perigosa": carga_perigosa, "placa": placa, "prioridade": prioridade,
        "resumo": _resumo(texto),
        "campos_faltantes": faltantes,
        # Regras simples merecem pouca confiança: com dados faltando, vai para triagem humana.
        "confianca": 0.7 if eh_guincho and rodovia and km is not None else 0.4,
        "justificativa": "Interpretação por regras (plano B, sem IA).",
    }


def _resumo(texto: str) -> str:
    t = re.sub(r"^\[[^\]]*\]\s*", "", texto.strip())          # tira "[data hora]"
    t = re.sub(r"(?i)^assunto:[^\n]*\n+", "", t).strip() or t  # tira a linha de assunto
    t = re.sub(r"(?i)^(bom dia|boa tarde|boa noite|ol[aá])[^\n]*\n+", "", t).strip() or t
    t = " ".join(t.split())
    return t if len(t) <= 100 else t[:97].rsplit(" ", 1)[0] + "..."


def _normalizar(d: dict) -> dict:
    """Garante tipos e valores válidos, venha a resposta da IA ou das regras."""
    d.setdefault("campos_faltantes", [])
    # A IA às vezes escreve com acento ou espaço ("caminhão", "faixa de rolamento"):
    # padroniza antes de conferir com a lista de valores permitidos.
    for campo in ("categoria", "tipo_veiculo", "posicao", "motivo", "prioridade"):
        if isinstance(d.get(campo), str):
            d[campo] = _sem_acento(d[campo]).strip().replace(" ", "_").replace("-", "_")
    sinonimos = {"carreta": "caminhao", "bitrem": "caminhao", "carro": "leve", "automovel": "leve",
                 "van": "utilitario", "pick_up": "utilitario", "pickup": "utilitario", "motocicleta": "moto"}
    d["tipo_veiculo"] = sinonimos.get(d.get("tipo_veiculo"), d.get("tipo_veiculo"))
    d["tipo_veiculo"] = d.get("tipo_veiculo") if d.get("tipo_veiculo") in TIPOS_VEICULO else "nao_informado"
    d["posicao"] = d.get("posicao") if d.get("posicao") in POSICOES else "nao_informado"
    d["motivo"] = d.get("motivo") if d.get("motivo") in MOTIVOS else "outro"
    if d.get("prioridade") not in ("alta", "media", "baixa"):
        d["prioridade"] = "media"
    if d.get("categoria") not in ("guincho", "outro"):
        d["categoria"] = "outro"
    try:
        d["km"] = float(d["km"]) if d.get("km") not in (None, "") else None
    except (TypeError, ValueError):
        d["km"] = None
    if d.get("rodovia"):
        m = re.match(r"([A-Za-z]{2})\s*-?\s*(\d{1,3})$", str(d["rodovia"]).strip())
        d["rodovia"] = f"{m.group(1).upper()}-{int(m.group(2)):03d}" if m else str(d["rodovia"]).upper()
    if d.get("placa"):
        d["placa"] = re.sub(r"[^A-Z0-9]", "", str(d["placa"]).upper())
        # Só aceita formato de placa brasileira (ABC1234 ou Mercosul ABC1D23).
        # A IA já transformou "Onix branco" em placa "ONIXBRANCO": isso é descartado.
        if not re.fullmatch(r"[A-Z]{3}\d[A-Z0-9]\d{2}", d["placa"]):
            d["placa"] = None
    d["vitimas"] = bool(d.get("vitimas"))
    d["carga_perigosa"] = bool(d.get("carga_perigosa"))
    try:
        d["confianca"] = max(0.0, min(1.0, float(d.get("confianca", 0))))
    except (TypeError, ValueError):
        d["confianca"] = 0.0
    # Segurança: vítima, carga perigosa ou faixa obstruída é sempre prioridade alta,
    # diga a IA o que disser (regra fixa, não depende do modelo).
    if d["vitimas"] or d["carga_perigosa"] or d["posicao"] == "faixa_de_rolamento":
        d["prioridade"] = "alta"
    return d
