# Guincho: receber, entender e encaminhar

**Challenge Motiva × FIAP · Sprint 1 — Fundamentos da interação e da plataforma**

Automação do caminho de uma **solicitação de guincho** em rodovia: da chegada (e-mail ou
planilha) até o **registro estruturado** e o **encaminhamento automático** à base responsável,
usando IA para interpretar o relato livre do agente de campo. Inclui as funções que o
**agente de voz** vai chamar nas próximas sprints.

> User stories atendidas (persona *Agente de Inspeção de Tráfego*): **1 – Registrar ocorrência**,
> **3 – Informar localização e condições** e **6 – Solicitar apoio**; consulta de status
> prepara a **4 – Consultar recursos acionados**.

## O que funciona

| Requisito da sprint | Onde |
|---|---|
| Captura automática por **e-mail** (IMAP, não lidos; anexos CSV/XLSX também) | `guincho/captura_email.py` |
| Captura automática por **arquivo** (CSV ou Excel na pasta `entrada/`) | `guincho/captura_arquivo.py` |
| **IA classifica** e **extrai** os dados (modelo local via Ollama, com resposta em JSON) | `guincho/ia.py` + `guincho/ollama.py` |
| **Registro estruturado** com protocolo e linha do tempo | `guincho/registro.py` (SQLite) |
| **Encaminhamento automático** ao responsável por e-mail | `guincho/roteamento.py` + `guincho/encaminhamento.py` |
| **Função para o agente de voz** (function calling) | `guincho/agente_voz.py` + simulador em `guincho/simulador_voz.py` |

Desenho do processo antes e depois: [`docs/processo-antes-depois.md`](docs/processo-antes-depois.md).
Decisão de arquitetura: [`docs/adr/ADR-001-ia-interpreta-regra-decide.md`](docs/adr/ADR-001-ia-interpreta-regra-decide.md).

## Como funciona

```
E-mail ─┐
Planilha ┼─► pipeline.processar ─► IA interpreta ─► regra de encaminhamento ─► registro ─► e-mail ao responsável
Voz ────┘        (caminho único)    (classifica,      (tabela responsaveis.csv)   (protocolo +
                                     extrai, prioriza)                             eventos)
```

1. **Captura.** A cada 30 s, a automação lê os e-mails não lidos e os arquivos da pasta `entrada/`.
   Cada origem tem um identificador (Message-ID, arquivo + linha), então nada é registrado duas vezes.
2. **Interpretação (IA).** Um modelo de IA que roda no próprio computador (Qwen 2.5, via Ollama,
   gratuito e sem limite de uso) recebe o relato e responde em JSON, com os campos: categoria (guincho/outro), tipo de veículo,
   rodovia (normalizada: "Bandeirantes" → SP-348), km, sentido, posição na via, motivo, vítimas,
   carga perigosa, placa, prioridade, resumo, campos faltantes, confiança e justificativa.
3. **Encaminhamento (regra, sem IA).** A tabela `dados/responsaveis.csv` diz qual base atende cada
   trecho de cada rodovia, para guincho leve ou pesado (caminhão/ônibus). Vai para a
   **Mesa de Triagem do CCO** quando: não é guincho, falta rodovia ou km, a confiança é menor que 60%
   ou o trecho não está cadastrado. **Com vítima**, a Supervisão de APH recebe cópia.
4. **Registro.** Tabela `solicitacoes` (todos os campos + destino + método usado) e tabela `eventos`
   (recebida → interpretada → destino_decidido → encaminhada), para rastreabilidade.
5. **E-mail ao responsável** com protocolo, prioridade, local, situação, campos faltantes,
   justificativa da IA e o relato original.

### Uso da IA e governança

- **Saída estruturada:** o modo JSON do Ollama garante uma resposta em JSON válido; os campos e valores
  permitidos vão nas instruções, com um exemplo, e o código confere e corrige cada campo antes de usar.
- **Custo zero e dados locais:** o modelo roda na máquina; nenhum relato sai para serviços externos.
- **A IA não inventa e não decide destino:** instruída a usar só o texto; o destino é regra.
- **Confiança e campos faltantes** desviam casos duvidosos para validação humana.
- **Regras de segurança fixas:** vítima, carga perigosa ou faixa obstruída = prioridade ALTA, sempre.
- **Plano B:** com o Ollama fechado ou a IA desligada, regras simples interpretam; o registro guarda o método.
- **Agente de voz:** registrar exige `confirmado_pelo_usuario=true`, atendendo ao critério da Motiva
  de confirmação explícita antes de ações críticas.

> Os responsáveis, bases, telefones e e-mails da tabela são **fictícios**. A Motiva não definiu
> responsáveis no material do desafio (o processamento no CCO é outro projeto); a tabela representa
> a regra que a operação manteria.

## Instalação

Requer Python 3.10 ou mais novo.

```bash
git clone <url-do-repositorio>
cd guincho-motiva
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

**IA local (gratuita):** instale o Ollama (https://ollama.com/download) e baixe o modelo uma vez:

```bash
ollama pull qwen2.5:3b
```

O modelo tem cerca de 2 GB e roda em computadores com 8 GB de RAM. Com o Ollama fechado, a
automação continua funcionando pelo plano B por regras.

Preencha o `.env`:

| Variável | Para quê |
|---|---|
| `USAR_IA`, `MODELO_IA` | IA local ligada (`sim`) e o modelo do Ollama (`qwen2.5:3b`). |
| `IMAP_*` | Caixa que **recebe** os pedidos. No Gmail: verificação em 2 etapas + **Senha de app**. |
| `SMTP_*` | Conta que **envia** os encaminhamentos (pode ser a mesma do Gmail, mesma senha de app). Sem SMTP, os e-mails ficam em `saida/emails/*.eml`. |
| `EMAIL_DEMO_PARA` | Modo demonstração: recebe todos os encaminhamentos (os responsáveis são fictícios). |

## Uso

```bash
python -m guincho iniciar          # roda sem parar (e-mail + pasta a cada 30 s)
python -m guincho uma-vez          # uma verificação e sai
python -m guincho texto "Carreta quebrada na faixa da direita, SP-348 km 98 sentido interior"
python -m guincho listar           # últimas solicitações
python -m guincho ver GUI-20261012-0001   # registro completo + linha do tempo
python -m guincho voz              # simulador do agente de voz (precisa do Ollama aberto)
python -m guincho diagnostico-ia   # mede o tempo e mostra a resposta crua da IA local
python -m pytest                   # testes automáticos
```

Para testar a captura por arquivo, copie `exemplos/ocorrencias_turno.csv` ou
`exemplos/ocorrencias_planilha.xlsx` para `entrada/`. A coluna com o texto pode se chamar
`relato`, `texto`, `descricao`, `ocorrencia` ou `mensagem`; `solicitante` e `data_hora` são opcionais.

## Função para o agente de voz

```python
from guincho.agente_voz import FERRAMENTAS, executar_ferramenta

# FERRAMENTAS descreve as funções (nome, descrição, parâmetros) para o LLM.
# Quando o modelo pedir uma ferramenta:
executar_ferramenta("registrar_solicitacao_guincho", {
    "relato": "Carreta com pane na faixa da direita, SP-348 km 98 sentido interior",
    "solicitante": "Insp. Marina", "confirmado_pelo_usuario": True,
})
# {'ok': True, 'protocolo': 'GUI-20261012-0004', 'prioridade': 'alta', ...,
#  'mensagem_para_falar': 'Registrado. Protocolo final 0 0 0 4, prioridade alta, em SP-348
#   quilômetro 98. Encaminhei para Equipe Guincho Pesado Campinas.'}

executar_ferramenta("consultar_solicitacao", {"protocolo": "GUI-20261012-0004"})
```

`registrar_solicitacao_guincho` usa o **mesmo caminho** do e-mail e da planilha. As respostas
trazem `mensagem_para_falar`, curta e pronta para virar áudio na Sprint 2.

## Estrutura

```
guincho/            código
  __main__.py       linha de comando
  pipeline.py       caminho único: interpretar → decidir → registrar → encaminhar
  ia.py             interpretação pela IA (+ plano B)
  ollama.py         conexão com a IA local
  roteamento.py     regra de encaminhamento
  registro.py       banco SQLite e eventos
  encaminhamento.py e-mail ao responsável
  captura_email.py  captura IMAP
  captura_arquivo.py captura CSV/Excel
  agente_voz.py     funções para o agente de voz
  simulador_voz.py  demonstração de function calling
dados/responsaveis.csv   quem atende cada trecho (editável)
exemplos/                e-mail e planilhas de exemplo
docs/                    processo antes/depois e ADR
tests/                   testes automáticos (rodam sem IA e sem e-mail)
```

## Limitações e próximos passos

- Localização por **km informado**; o GPS (`latitude`/`longitude`) já é aceito e gravado, mas
  ainda não é convertido em trecho.
- Sem interface visual nesta sprint; a consulta é pela linha de comando e pela função de voz.
- Próximas sprints: voz real (speech-to-text e text-to-speech), status da missão pelo agente de
  guincho (confirmar recebimento, chegada, finalização) e painel do CCO.
