"""Cada teste roda com pastas e banco próprios, sem IA (plano B) e sem enviar e-mail."""
import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    for nome, sub in [("PASTA_ENTRADA", "entrada"), ("PASTA_PROCESSADOS", "processados"),
                      ("PASTA_ERROS", "erros"), ("PASTA_SAIDA_EMAILS", "saida"),
                      ("PASTA_LOGS", "logs")]:
        monkeypatch.setenv(nome, str(tmp_path / sub))
    monkeypatch.setenv("BANCO", str(tmp_path / "teste.db"))
    monkeypatch.setenv("USAR_IA", "nao")
    for nome in ("SMTP_HOST", "IMAP_HOST", "EMAIL_DEMO_PARA"):
        monkeypatch.setenv(nome, "")
    # Recarrega os módulos para lerem as variáveis acima.
    for nome in sorted([m for m in sys.modules if m.startswith("guincho")]):
        del sys.modules[nome]
    importlib.import_module("guincho.config")
    yield tmp_path
