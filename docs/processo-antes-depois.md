# Processo: solicitação de guincho — antes e depois da automação

Escopo da Sprint 1: do **relato de campo** até o **registro estruturado e o encaminhamento
ao responsável**. O acionamento do recurso e o atendimento (etapas 3 a 6 do material da
Motiva) continuam com as pessoas; a automação prepara e entrega a informação.

## Antes (AS-IS)

Baseado no fluxo "Contexto – Atual" apresentado pela Motiva (CFTV, 0800, Waze e inspetor →
validação e criação da ocorrência → CCO aciona o recurso).

```mermaid
flowchart LR
    A[Inspetor vê veículo parado] --> B[Para a viatura e<br/>liga/manda mensagem ao CCO]
    B --> C[Operador do CCO ouve ou lê<br/>e digita a ocorrência no sistema]
    C --> D{Faltou dado?<br/>km, sentido, tipo}
    D -- sim --> B2[Liga de volta para o inspetor] --> C
    D -- não --> E[Operador decide qual base<br/>atende o trecho e o tipo de guincho]
    E --> F[Liga/manda mensagem para a base]
    F --> G[Base aciona o guincho]
    H[Planilhas de turno e e-mails] -.-> C
```

**Dores**

| Dor | Efeito |
|---|---|
| O inspetor manuseia o celular/rádio para relatar | perde atenção no ambiente rodoviário (risco) |
| O operador redigita o que ouviu | erro de km/sentido, retrabalho, demora |
| Dados incompletos só são percebidos depois | ligações de volta, atraso no acionamento |
| A escolha da base depende da memória do operador | inconsistência entre turnos |
| E-mails e planilhas de turno entram fora do fluxo | pedidos esquecidos ou duplicados |
| Pouco registro de quem decidiu o quê e quando | baixa rastreabilidade |

## Depois (TO-BE)

```mermaid
flowchart LR
    subgraph Entrada
      E1[E-mail na caixa de solicitações]
      E2[Planilha CSV/Excel na pasta de entrada]
      E3[Agente de voz<br/>função registrar_solicitacao_guincho]
    end
    E1 --> P
    E2 --> P
    E3 --> P
    P[Caminho único<br/>pipeline.processar] --> IA[IA interpreta o texto<br/>classifica, extrai e prioriza]
    IA --> R{Regra de encaminhamento<br/>tabela responsaveis.csv}
    R -- dados completos e<br/>confiança suficiente --> B[Base do trecho<br/>guincho leve ou pesado]
    R -- falta dado, baixa confiança<br/>ou fora dos trechos --> T[Mesa de Triagem do CCO<br/>validação humana]
    R -- há vítima --> APH[Cópia para<br/>Supervisão de APH]
    B --> REG[(Registro + linha do tempo<br/>SQLite)]
    T --> REG
    REG --> M[E-mail ao responsável<br/>com protocolo]
```

**O que muda**

| Antes | Depois |
|---|---|
| Relato digitado por outra pessoa | O texto do inspetor é interpretado automaticamente |
| Falta de dado percebida tarde | A IA lista os campos faltantes e o pedido vai para a triagem |
| Base escolhida de memória | Regra fixa por rodovia, km e tipo de veículo, editável numa planilha |
| Prioridade subjetiva | Prioridade sugerida pela IA + regra fixa de segurança (vítima, carga perigosa ou faixa obstruída = ALTA) |
| Três canais separados | Um caminho único para e-mail, planilha e voz |
| Pouca rastreabilidade | Protocolo + eventos: recebida, interpretada, destino decidido, encaminhada |

## Onde está a decisão humana

A IA **não aciona** guincho. Ela interpreta; a regra escolhe o destino; o responsável decide
o acionamento. Casos duvidosos vão para a Mesa de Triagem do CCO. Isso atende aos critérios
transversais da Motiva: confirmação, rastreabilidade e governança.
