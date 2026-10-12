import email
import shutil
from pathlib import Path

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"


def test_regra_encaminha_pela_rodovia_km_e_tipo():
    from guincho import roteamento
    base = {"categoria": "guincho", "rodovia": "SP-348", "confianca": 0.9, "vitimas": False}
    assert roteamento.decidir({**base, "km": 42, "tipo_veiculo": "leve"}).base == "Base Operacional Jundiaí"
    d = roteamento.decidir({**base, "km": 98, "tipo_veiculo": "caminhao"})
    assert d.responsavel == "Equipe Guincho Pesado Campinas" and not d.triagem


def test_sem_km_ou_baixa_confianca_vai_para_triagem():
    from guincho import roteamento
    d = roteamento.decidir({"categoria": "guincho", "rodovia": "SP-348", "km": None, "confianca": 0.9})
    assert d.triagem and "km" in d.motivo
    d = roteamento.decidir({"categoria": "guincho", "rodovia": "SP-348", "km": 10,
                            "tipo_veiculo": "leve", "confianca": 0.3})
    assert d.triagem


def test_vitima_copia_aph_e_prioridade_alta():
    from guincho import ia, roteamento
    dados = ia.interpretar("Colisão na Raposo Tavares km 112 sentido capital, uma pessoa ferida, carro sem rodar")
    assert dados["vitimas"] and dados["prioridade"] == "alta"
    assert "supervisao.aph@exemplo.com.br" in roteamento.decidir(dados).copias


def test_planilha_csv_e_excel_sao_recolhidas_e_movidas(ambiente_isolado):
    from guincho import captura_arquivo, config, registro
    for nome in ("ocorrencias_turno.csv", "ocorrencias_planilha.xlsx"):
        shutil.copy(EXEMPLOS / nome, config.PASTA_ENTRADA / nome)
    resultados = captura_arquivo.recolher()
    assert len(resultados) == 7
    assert not any(config.PASTA_ENTRADA.glob("ocorrencias_*"))
    assert len(list(config.PASTA_PROCESSADOS.iterdir())) == 2
    assert len(list(config.PASTA_SAIDA_EMAILS.glob("*.eml"))) == 7
    assert len(registro.listar()) == 7


def test_mesma_origem_nao_duplica():
    from guincho import pipeline, registro
    a = pipeline.processar("Carro quebrado SP-348 km 30 sentido capital", "email", "x", "email:<1@x>")
    b = pipeline.processar("Carro quebrado SP-348 km 30 sentido capital", "email", "x", "email:<1@x>")
    assert a["protocolo"] == b["protocolo"] and b["duplicado"]
    assert len(registro.listar()) == 1


def test_email_exemplo_vira_solicitacao_encaminhada():
    from guincho import captura_email
    msg = email.message_from_bytes((EXEMPLOS / "email_exemplo.eml").read_bytes())
    r = captura_email.processar_mensagem(msg)
    assert r["rodovia"] == "SP-348" and r["km"] == 23
    assert r["base"] == "Base Operacional Jundiaí" and r["status"] == "encaminhada"


def test_funcao_do_agente_de_voz_exige_confirmacao_e_registra():
    from guincho import agente_voz
    recusa = agente_voz.executar_ferramenta("registrar_solicitacao_guincho",
                                            {"relato": "carro parado", "confirmado_pelo_usuario": False})
    assert not recusa["ok"] and recusa["erro"] == "confirmacao_pendente"
    r = agente_voz.executar_ferramenta("registrar_solicitacao_guincho", {
        "relato": "Carreta com pane na faixa da direita, SP-348 km 98 sentido interior",
        "confirmado_pelo_usuario": True, "solicitante": "Insp. Marina"})
    assert r["ok"] and r["prioridade"] == "alta" and "Pesado Campinas" in r["mensagem_para_falar"]
    c = agente_voz.executar_ferramenta("consultar_solicitacao", {"protocolo": r["protocolo"]})
    assert c["ok"] and [e["evento"] for e in c["linha_do_tempo"]] == [
        "recebida", "interpretada", "destino_decidido", "encaminhada"]


def test_falha_no_envio_e_reenviada_na_rodada_seguinte(monkeypatch):
    from guincho import encaminhamento, pipeline, registro
    original = encaminhamento.enviar

    def fora_do_ar(msg):
        raise ConnectionError("servidor de e-mail fora do ar")

    monkeypatch.setattr(encaminhamento, "enviar", fora_do_ar)
    r = pipeline.processar("Carro quebrado SP-348 km 30 sentido capital", "email", "x", "email:<2@x>")
    assert r["status"] == "erro_encaminhamento"
    assert pipeline.reenviar_pendentes() == []          # ainda fora do ar: continua pendente

    monkeypatch.setattr(encaminhamento, "enviar", original)
    reenviados = pipeline.reenviar_pendentes()
    assert [x["protocolo"] for x in reenviados] == [r["protocolo"]]
    assert registro.obter(r["protocolo"])["status"] == "encaminhada"
    assert registro.pendentes_de_envio() == []


def test_smtp_sem_usuario_grava_arquivo_em_vez_de_tentar_enviar(monkeypatch):
    from guincho import config, pipeline
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(config, "SMTP_USUARIO", "")
    r = pipeline.processar("Carro quebrado SP-348 km 30 sentido capital", "teste", "x")
    assert r["status"] == "encaminhada"
    assert list(config.PASTA_SAIDA_EMAILS.glob("*.eml"))


def test_ia_local_e_usada_quando_ligada(monkeypatch):
    import json
    from guincho import config, ia, ollama
    monkeypatch.setattr(config, "USAR_IA", True)
    pedido = {}

    def falso_chat(mensagens, formato=None, ferramentas=None, timeout=180):
        pedido["formato"] = formato
        return {"role": "assistant", "content": json.dumps({
            "categoria": "guincho", "tipo_veiculo": "caminhao", "rodovia": "sp 348", "km": 98,
            "sentido": "interior", "posicao": "faixa_de_rolamento", "motivo": "pane_mecanica",
            "vitimas": False, "carga_perigosa": False, "placa": None, "prioridade": "media",
            "resumo": "Carreta com pane na faixa", "campos_faltantes": [], "confianca": 0.9,
            "justificativa": "Faixa obstruída"})}

    monkeypatch.setattr(ollama, "chat", falso_chat)
    d = ia.interpretar("carreta quebrada no 98 da bandeirantes sentido interior")
    assert d["metodo"] == f"ia:{config.MODELO_IA}" and d["rodovia"] == "SP-348"
    assert d["prioridade"] == "alta"          # regra de segurança sobrepõe a IA (faixa obstruída)
    assert pedido["formato"] == "json"        # JSON garantido pelo Ollama


def test_ia_fora_do_ar_cai_no_plano_b(monkeypatch):
    from guincho import config, ia, ollama
    monkeypatch.setattr(config, "USAR_IA", True)

    def fora(*a, **k):
        raise ollama.ErroOllama("Ollama não está rodando")

    monkeypatch.setattr(ollama, "chat", fora)
    d = ia.interpretar("Carro quebrado SP-348 km 30 sentido capital")
    assert d["metodo"] == "regras" and d["km"] == 30


def test_valores_com_acento_ou_espaco_sao_aceitos():
    from guincho import ia
    d = ia._normalizar({"categoria": "Guincho", "tipo_veiculo": "caminhão", "posicao": "faixa de rolamento",
                        "motivo": "pane mecânica", "prioridade": "média", "km": 98, "rodovia": "SP-348",
                        "confianca": 0.9})
    assert d["tipo_veiculo"] == "caminhao" and d["posicao"] == "faixa_de_rolamento"
    assert d["motivo"] == "pane_mecanica" and d["categoria"] == "guincho"
    assert d["prioridade"] == "alta"          # faixa obstruída => alta
    assert ia._normalizar({"tipo_veiculo": "carreta"})["tipo_veiculo"] == "caminhao"


def test_placa_inventada_pela_ia_e_descartada():
    from guincho import ia
    assert ia._normalizar({"placa": "ONIXBRANCO"})["placa"] is None
    assert ia._normalizar({"placa": "fkr-3c21"})["placa"] == "FKR3C21"
    assert ia._normalizar({"placa": "ABC 1234"})["placa"] == "ABC1234"
