# ADR-001: a IA interpreta, a regra decide o destino

**Data:** 12/10/2026 · **Status:** aceito

## Contexto
Precisamos transformar relatos livres ("carreta quebrada no 98 da Bandeirantes") em registros
estruturados e encaminhá-los à base certa. Poderíamos pedir à IA que também escolhesse o
responsável.

## Decisão
1. A IA (modelo local Qwen 2.5 via Ollama, em modo JSON) só **interpreta**: classifica, extrai campos, sugere prioridade,
   lista o que falta e informa a própria confiança. A saída segue um esquema JSON fixo.
2. O **destino** é decidido por uma regra determinística sobre a tabela `dados/responsaveis.csv`
   (rodovia + trecho de km + guincho leve/pesado).
3. Casos duvidosos (sem rodovia/km, confiança abaixo de 60%, fora dos trechos, não é guincho)
   vão para a **Mesa de Triagem do CCO**, com validação humana.
4. Regras de segurança fixas sobrepõem a IA: vítima, carga perigosa ou faixa obstruída = prioridade ALTA.
5. Se a IA estiver indisponível, um **plano B por regras** assume e o registro guarda o método usado.

## Consequências
- O encaminhamento é previsível, auditável e alterável pela operação sem mexer no código.
- Um erro da IA pode errar um campo, mas não inventa destino; baixa confiança cai na triagem.
- A operação não para se a IA cair (plano B), com qualidade menor e mais casos na triagem.
- Custo zero: o modelo roda no próprio computador, sem cota e sem enviar relatos para fora.
  Em troca, é mais lento e menos preciso que modelos pagos; por isso a triagem humana importa.
- O modo com esquema obrigatório (`format` = JSON Schema) foi testado e descartado: em
  computador sem placa de vídeo, a resposta não chegava em minutos. O modo JSON simples,
  com os campos descritos nas instruções e conferidos pelo código, respondeu normalmente.
