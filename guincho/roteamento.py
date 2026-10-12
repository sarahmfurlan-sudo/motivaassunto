"""Regra de encaminhamento: decide QUEM recebe a solicitação.

Não usa IA. Lê a tabela dados/responsaveis.csv (rodovia + trecho de km + tipo de guincho
=> base responsável). Assim a decisão é previsível, auditável e editável por quem opera,
sem mexer no código.

- Veículo pesado (caminhão, ônibus) => guincho pesado; os demais => guincho leve.
- Pedido que não é guincho, com dado essencial faltando, com baixa confiança da IA ou fora
  dos trechos cadastrados => Mesa de Triagem do CCO (validação humana).
- Havendo vítima => a Supervisão de APH recebe cópia.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field

from . import config

PESADOS = {"caminhao", "onibus"}


@dataclass
class Destino:
    base: str
    responsavel: str
    email: str
    telefone: str = ""
    copias: list[str] = field(default_factory=list)
    motivo: str = ""          # por que foi para esse destino (vai para o registro)
    triagem: bool = False     # True = precisa de validação humana antes do acionamento


def carregar_tabela() -> list[dict]:
    with open(config.TABELA_RESPONSAVEIS, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tipo_guincho(tipo_veiculo: str) -> str:
    return "pesado" if tipo_veiculo in PESADOS else "leve"


def _especial(tabela: list[dict], tipo: str) -> dict:
    for linha in tabela:
        if linha["rodovia"] == "*" and linha["tipo_guincho"] == tipo:
            return linha
    raise RuntimeError(f"A tabela de responsáveis não tem a linha especial '{tipo}'.")


def decidir(dados: dict) -> Destino:
    tabela = carregar_tabela()
    triagem = _especial(tabela, "triagem")
    aph = _especial(tabela, "aph")
    copias = [aph["email"]] if dados.get("vitimas") else []

    def para_triagem(motivo: str) -> Destino:
        return Destino(triagem["base"], triagem["responsavel"], triagem["email"],
                       triagem.get("telefone", ""), copias, motivo, triagem=True)

    if dados.get("categoria") != "guincho":
        return para_triagem("Não foi identificado como pedido de guincho.")
    essenciais = [c for c in ("rodovia", "km") if dados.get(c) in (None, "")]
    if essenciais:
        return para_triagem(f"Falta informação essencial: {', '.join(essenciais)}.")
    if dados.get("confianca", 0) < config.CONFIANCA_MINIMA:
        return para_triagem(f"Confiança da interpretação abaixo de {config.CONFIANCA_MINIMA:.0%}.")

    tipo = tipo_guincho(dados.get("tipo_veiculo", ""))
    km = float(dados["km"])
    for linha in tabela:
        if linha["rodovia"] != dados["rodovia"] or linha["tipo_guincho"] != tipo:
            continue
        if float(linha["km_inicio"]) <= km < float(linha["km_fim"]):
            return Destino(linha["base"], linha["responsavel"], linha["email"],
                           linha.get("telefone", ""), copias,
                           f"{dados['rodovia']} km {km:g} está no trecho {linha['km_inicio']}–"
                           f"{linha['km_fim']} da {linha['base']} (guincho {tipo}).")
    return para_triagem(f"{dados['rodovia']} km {km:g} não está em nenhum trecho cadastrado.")
