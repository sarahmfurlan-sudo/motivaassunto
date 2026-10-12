# Roteiro do vídeo (3 a 4 minutos)

Antes de gravar: `.env` preenchido (chave da IA, Gmail com senha de app, `EMAIL_DEMO_PARA`),
banco limpo (apague `dados/guincho.db`), dois terminais e a caixa de entrada abertos.

| Tempo | Mostrar | Falar |
|---|---|---|
| 0:00–0:30 | Desenho "antes" (`docs/processo-antes-depois.md`) | O problema: inspetor relata por telefone, CCO redigita, escolhe a base de memória. |
| 0:30–0:50 | Desenho "depois" | Um caminho único para e-mail, planilha e voz. A IA interpreta, a regra decide, o humano aciona. |
| 0:50–1:00 | Terminal: `python -m guincho iniciar` | A automação fica vigiando a caixa e a pasta. |
| 1:00–1:40 | Do celular, mandar e-mail informal para a caixa: "Onix parado no acostamento da Bandeirantes, km 23 sentido capital, motor apagou, ninguém ferido" | Linguagem de campo, sem formulário. |
| 1:40–2:10 | Terminal registra o protocolo; abrir o e-mail que chegou | A IA converteu "Bandeirantes" em SP-348, viu que é carro leve, km 23 → Base Jundiaí. Mostrar a justificativa e a confiança. |
| 2:10–2:40 | Arrastar `exemplos/ocorrencias_turno.csv` para `entrada/` | Planilha de turno com 5 relatos. Destacar: a carreta na faixa = ALTA; a colisão com vítima = cópia para o APH; a moto sem km = Mesa de Triagem. |
| 2:40–3:00 | `python -m guincho ver <protocolo>` | Registro estruturado e linha do tempo: rastreabilidade. |
| 3:00–3:40 | `python -m guincho voz`: "tem uma carreta quebrada na Bandeirantes km 98 sentido interior" → agente confirma → "sim" | O agente pede confirmação antes de registrar e chama a mesma função. É o que a Sprint 2 vai usar com voz real. |
| 3:40–4:00 | README | Próximos passos. |
