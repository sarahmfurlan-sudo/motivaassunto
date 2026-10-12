"""Linha de comando.

  python -m guincho iniciar          roda sem parar: verifica e-mail e pasta a cada INTERVALO_SEGUNDOS
  python -m guincho uma-vez          verifica e-mail e pasta uma vez e sai
  python -m guincho texto "relato"   processa um relato digitado (teste rápido)
  python -m guincho listar           mostra as últimas solicitações
  python -m guincho ver PROTOCOLO    mostra o registro completo e a linha do tempo
  python -m guincho voz              simulador do agente de voz (function calling)
"""
from __future__ import annotations

import json
import sys
import time

from . import captura_arquivo, captura_email, config, pipeline, registro
from .log import obter_logger

log = obter_logger()


def uma_rodada() -> list[dict]:
    resultados = []
    for nome, captura in (("reenvio", pipeline.reenviar_pendentes), ("e-mail", captura_email.recolher),
                          ("arquivo", captura_arquivo.recolher)):
        try:
            resultados += captura()
        except Exception as e:  # uma captura com problema não derruba a outra
            log.error("Captura por %s falhou: %s", nome, e)
    return resultados


def imprimir(r: dict) -> None:
    km = f"km {r['km']:g}" if r.get("km") is not None else "km ?"
    marca = " (já existia)" if r.get("duplicado") else ""
    print(f"{r['protocolo']}{marca} | {r['prioridade'].upper():5} | {r['status']:11} | "
          f"{r.get('rodovia') or '?'} {km} | {r['tipo_veiculo']} → {r['responsavel']}")


def diagnostico_ia() -> None:
    """Mede a IA local com o pedido real e mostra a resposta crua."""
    from . import ia, ollama
    relato = "carreta quebrada no 98 da bandeirantes sentido interior, ocupando a faixa"
    print(f"Modelo: {config.MODELO_IA} | limite: {config.IA_MAX_TOKENS} tokens | espera: {config.IA_TIMEOUT}s")
    print("Aguarde (a primeira chamada carrega o modelo)...\n", flush=True)
    inicio = time.time()
    try:
        r = ollama.chat_completo(ia.montar_mensagens(relato), formato="json")
    except Exception as e:
        print(f"Falhou em {time.time() - inicio:.0f}s: {e}")
        return
    conteudo = r["message"].get("content", "")
    print(f"Tempo: {time.time() - inicio:.0f}s | tokens gerados: {r.get('eval_count')} | fim: {r.get('done_reason')}")
    print(conteudo[:1200])
    try:
        d = ia._normalizar({**json.loads(conteudo), "metodo": "diagnostico"})
        print(f"\nJSON válido: sim → {d['rodovia']} km {d['km']} | {d['tipo_veiculo']} | prioridade {d['prioridade']}")
    except Exception as e:
        print(f"\nJSON válido: NÃO ({e})")


def main(args: list[str]) -> int:
    cmd = args[0] if args else "ajuda"
    if cmd == "iniciar":
        modo_ia = f"IA local {config.MODELO_IA} (Ollama)" if config.USAR_IA else "plano B por regras (IA desligada)"
        log.info("Automação iniciada. Interpretação: %s. Intervalo: %ss.", modo_ia, config.INTERVALO_SEGUNDOS)
        while True:
            for r in uma_rodada():
                imprimir(r)
            time.sleep(config.INTERVALO_SEGUNDOS)
    elif cmd == "uma-vez":
        resultados = uma_rodada()
        for r in resultados:
            imprimir(r)
        print(f"{len(resultados)} solicitação(ões) processada(s).")
    elif cmd == "texto" and len(args) > 1:
        imprimir(pipeline.processar(" ".join(args[1:]), "teste", "linha_de_comando"))
    elif cmd == "listar":
        for r in registro.listar():
            km = f"km {r['km']:g}" if r["km"] is not None else "km ?"
            print(f"{r['protocolo']} | {r['criado_em']} | {r['canal']:7} | {r['prioridade']:5} | "
                  f"{r['status']:11} | {r['rodovia'] or '?'} {km} | {r['base_responsavel']} | {r['resumo']}")
    elif cmd == "ver" and len(args) > 1:
        r = registro.obter(args[1])
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "Protocolo não encontrado.")
    elif cmd == "diagnostico-ia":
        diagnostico_ia()
    elif cmd == "voz":
        from .simulador_voz import conversar
        conversar()
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
