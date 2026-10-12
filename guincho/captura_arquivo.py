"""Captura por arquivo: recolhe planilhas (CSV ou Excel) deixadas na pasta entrada/.

Cada linha é uma solicitação. A coluna com o texto pode se chamar relato, texto,
descricao ou ocorrencia; solicitante e data_hora são opcionais.
Depois de processado, o arquivo vai para processados/ (ou erros/, se não puder ser lido).
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config, pipeline
from .log import obter_logger

log = obter_logger()
EXTENSOES = {".csv", ".xlsx", ".xls"}
COLUNAS_TEXTO = ["relato", "texto", "descricao", "descrição", "ocorrencia", "ocorrência", "mensagem"]


def ler_planilha(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() == ".csv":
        for codificacao in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(caminho, sep=None, engine="python", encoding=codificacao, dtype=str)
                break
            except UnicodeDecodeError:
                continue
    else:
        df = pd.read_excel(caminho, dtype=str)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df.fillna("")


def coluna_texto(df: pd.DataFrame) -> str:
    for c in COLUNAS_TEXTO:
        if c in df.columns:
            return c
    raise ValueError(f"Nenhuma coluna de texto encontrada. Use uma destas: {', '.join(COLUNAS_TEXTO[:5])}.")


def processar_arquivo(caminho: Path) -> list[dict]:
    df = ler_planilha(caminho)
    col = coluna_texto(df)
    conteudo_hash = hashlib.sha1(caminho.read_bytes()).hexdigest()[:12]
    resultados = []
    for i, linha in df.iterrows():
        texto = linha[col].strip()
        if not texto:
            continue
        if linha.get("data_hora"):
            texto = f"[{linha['data_hora']}] {texto}"
        origem = f"arquivo:{caminho.name}:{conteudo_hash}:linha{i + 2}"  # +2 = linha no Excel
        resultados.append(pipeline.processar(texto, "arquivo", linha.get("solicitante", ""), origem))
    return resultados


def recolher() -> list[dict]:
    """Processa todos os arquivos da pasta de entrada. Devolve os resultados."""
    todos = []
    for caminho in sorted(config.PASTA_ENTRADA.iterdir()):
        if caminho.suffix.lower() not in EXTENSOES or caminho.name.startswith(("~$", ".")):
            continue
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            resultados = processar_arquivo(caminho)
            shutil.move(caminho, config.PASTA_PROCESSADOS / f"{carimbo}_{caminho.name}")
            log.info("Arquivo %s: %d solicitação(ões).", caminho.name, len(resultados))
            todos += resultados
        except Exception as e:
            log.error("Arquivo %s não pôde ser processado: %s", caminho.name, e)
            shutil.move(caminho, config.PASTA_ERROS / f"{carimbo}_{caminho.name}")
    return todos
