"""O caminho único de toda solicitação: interpretar → decidir destino → registrar → encaminhar.

E-mail, planilha e agente de voz chamam a MESMA função. Não existe caminho paralelo.
"""
from __future__ import annotations

import json

from . import encaminhamento, ia, registro, roteamento
from .log import obter_logger

log = obter_logger()


def processar(texto: str, canal: str, solicitante: str = "", origem_id: str | None = None,
              latitude: float | None = None, longitude: float | None = None) -> dict:
    """Processa uma solicitação e devolve o resultado resumido.

    origem_id identifica a origem (Message-ID do e-mail, arquivo+linha da planilha...).
    Se a mesma origem chegar de novo, nada é duplicado: devolve o protocolo já existente.
    """
    if not texto or not texto.strip():
        raise ValueError("Solicitação vazia.")

    if origem_id:
        existente = registro.buscar_por_origem(origem_id)
        if existente:
            log.info("Origem %s já registrada como %s. Ignorando.", origem_id, existente["protocolo"])
            return _resultado(existente, duplicado=True)

    dados = ia.interpretar(texto)
    destino = roteamento.decidir(dados)
    status = "em_triagem" if destino.triagem else "encaminhada"

    protocolo = registro.inserir({
        "canal": canal, "origem_id": origem_id, "solicitante": solicitante,
        "texto_original": texto.strip(),
        "categoria": dados["categoria"], "tipo_veiculo": dados["tipo_veiculo"],
        "tipo_guincho": roteamento.tipo_guincho(dados["tipo_veiculo"]),
        "rodovia": dados.get("rodovia"), "km": dados.get("km"), "sentido": dados.get("sentido"),
        "posicao": dados["posicao"], "motivo": dados["motivo"],
        "vitimas": int(dados["vitimas"]), "carga_perigosa": int(dados["carga_perigosa"]),
        "placa": dados.get("placa"), "prioridade": dados["prioridade"], "resumo": dados["resumo"],
        "campos_faltantes": dados.get("campos_faltantes", []), "confianca": dados["confianca"],
        "justificativa_ia": dados.get("justificativa"), "metodo": dados["metodo"],
        "status": status, "base_responsavel": destino.base, "responsavel": destino.responsavel,
        "email_responsavel": destino.email, "motivo_destino": destino.motivo,
        "latitude": latitude, "longitude": longitude,
    })
    registro.registrar_evento(protocolo, "recebida", {"canal": canal, "solicitante": solicitante,
                                                      "origem_id": origem_id})
    registro.registrar_evento(protocolo, "interpretada", {
        "metodo": dados["metodo"], "categoria": dados["categoria"], "prioridade": dados["prioridade"],
        "confianca": dados["confianca"], "justificativa": dados.get("justificativa")})
    registro.registrar_evento(protocolo, "destino_decidido", {
        "responsavel": destino.responsavel, "email": destino.email, "copias": destino.copias,
        "motivo": destino.motivo, "triagem": destino.triagem})

    _encaminhar(protocolo, dados, destino, texto, canal)
    return _resultado(registro.obter(protocolo))


def _encaminhar(protocolo: str, dados: dict, destino, texto: str, canal: str) -> bool:
    try:
        envio = encaminhamento.enviar(encaminhamento.montar(protocolo, dados, destino, texto, canal))
    except Exception as e:
        registro.atualizar_status(protocolo, "erro_encaminhamento")
        registro.registrar_evento(protocolo, "erro_encaminhamento", str(e))
        log.error("%s | falha ao encaminhar (nova tentativa na próxima rodada): %s", protocolo, e)
        return False
    registro.atualizar_status(protocolo, "em_triagem" if destino.triagem else "encaminhada")
    registro.registrar_evento(protocolo, "encaminhada", envio)
    log.info("%s | %s | %s → %s (%s)", protocolo, canal, dados["prioridade"].upper(),
             destino.responsavel, envio["modo"])
    return True


def reenviar_pendentes() -> list[dict]:
    """Tenta de novo os encaminhamentos que falharam (ex.: e-mail fora do ar).

    Usa os dados já registrados: a IA não é chamada de novo. O destino é recalculado
    pela mesma regra, então o resultado é o mesmo da primeira vez.
    """
    resultados = []
    for r in registro.pendentes_de_envio():
        dados = {**r, "vitimas": bool(r["vitimas"]), "carga_perigosa": bool(r["carga_perigosa"]),
                 "campos_faltantes": json.loads(r["campos_faltantes"] or "[]"),
                 "justificativa": r["justificativa_ia"]}
        destino = roteamento.decidir(dados)
        if _encaminhar(r["protocolo"], dados, destino, r["texto_original"], r["canal"]):
            resultados.append(_resultado(registro.obter(r["protocolo"])))
    return resultados


def _resultado(r: dict, duplicado: bool = False) -> dict:
    return {
        "protocolo": r["protocolo"], "status": r["status"], "prioridade": r["prioridade"],
        "categoria": r["categoria"], "rodovia": r["rodovia"], "km": r["km"],
        "tipo_veiculo": r["tipo_veiculo"], "responsavel": r["responsavel"],
        "base": r["base_responsavel"], "motivo_destino": r["motivo_destino"],
        "resumo": r["resumo"], "duplicado": duplicado,
    }
