# Nexus ME — arquitetura implementada e evolução

Versão 0.1.0 · 19/10/2026 UTC

## Decisão desta entrega

Aplicativo nativo Python + PySide6. O núcleo de domínio, o SQLite e os adaptadores HTTP usam a biblioteca padrão do Python. O primeiro fluxo é utilizável sem conta externa. Não foi aberto um servidor local para o Nexus nem uma porta pública; somente o Ollama, se instalado e ligado pelo usuário, atende em loopback.

Não criamos outro plugin e não alteramos o ME Nexus existente. As regras de origem, evidência e acesso efetivo orientaram o domínio e o prompt de conversa. O código do desktop permanece separado do pacote de skills.

## Módulos reais

| Arquivo | Responsabilidade |
|---|---|
| `nexus_me/store.py` | SQLite, integridade referencial, projetos, deduplicação, tarefas, histórico, backup, auditoria |
| `nexus_me/service.py` | Recuperação de contexto, relatório local, preparação e revisão do envio GPT |
| `nexus_me/providers.py` | HTTP Ollama e Responses API, tempo limite, bloqueio de redirecionamento |
| `nexus_me/importers.py` | Leitura de notas e sessões da Condution com prévia |
| `nexus_me/security.py` | Validação de limites e detector heurístico de alguns segredos |
| `nexus_me/config.py` | Configurações não secretas e pasta de dados |
| `nexus_me/ui.py` | Interface desktop, consultas em thread, revisão, tarefas e TTS opcional |
| `nexus_me/__main__.py` | Inicialização, bloqueio de instância, diagnóstico e relatório CLI |

## Fluxos implementados

1. Arquivo selecionado → leitura limitada → validação → prévia → transação SQLite.
2. Pergunta + projeto → seleção de até oito memórias → contexto limitado → registro textual ou Ollama.
3. Pergunta GPT → filtro `cloud_allowed` → payload imutável com hash → prévia → confirmação → rechecagem da permissão → API.
4. Resposta → histórico separado; não há gravação automática em memórias.

Limite de contexto é em caracteres, não uma contagem exata de tokens. O Ollama recebe `num_ctx=8192` e o limite de saída configurado. Histórico local elegível: até oito mensagens de Ollama, limitado a 4.000 caracteres. O custo real da API depende do modelo e da tokenização. Uso retornado pelo provedor é registrado na auditoria.

Os exemplos de treinamento e a identidade visual não têm acesso a contas. O modelo não recebe ferramentas de shell, navegação ou escrita. Isso limita o impacto de instruções maliciosas dentro de arquivos.

## Banco e consistência

`projects`, `memories`, `tasks`, `messages`, `audit`. Identificadores UUID para entidades de domínio, timestamp UTC para operações, data original preservada nas fontes. SQLite WAL, chaves estrangeiras e transações por operação.

Memórias não são editadas no lugar: novas versões preservam a anterior. Permissão de uso no GPT é local e não significa que o registro já foi sincronizado. Exclusão é local; backups anteriores não são alterados. Auditoria contém metadados, nunca chaves nem corpos de memórias.

## Próxima etapa: memória compartilhada

Implementar primeiro um fluxo com apenas o projeto Nexus ME em um ambiente de teste:

1. Supabase Auth: login do usuário e tokens de curta duração; refresh token protegido pelo cofre do Windows.
2. PostgreSQL: tabelas com `owner_id`, políticas RLS para o usuário autenticado e isolamento entre proprietários. Chave administrativa nunca entra no cliente.
3. Schema local v2: `outbox`, revisões, estado de sincronização e tombstones. Uma transação grava a alteração e seu evento; o log de auditoria v1 não substitui uma fila.
4. Eventos com `event_id`, `entity_id`, `owner_id`, `project_id`, `revision`, `base_revision`, `device_id`, tipo, conteúdo permitido e data da fonte.
5. Servidor recebe eventos idempotentes, valida proprietário/projeto, usa revisão esperada e preserva conflito. Repetição de entrega não duplica dados.
6. Cliente recebe atualizações por cursor, confirma processamento e retoma após falhas. Não usar simplesmente o relógio mais recente como vencedor.
7. MCP autenticado expõe leitura da memória já sincronizada ao plugin ME Nexus. O desktop não aceita conexão pública de entrada.

Os registros locais começam privados. A futura permissão para sincronização deverá ser independente de `cloud_allowed`, pois permitir enviar a uma chamada GPT não equivale a autorizar cópia persistente em outro serviço.

Critérios para ativação: testes entre dois usuários, token expirado, revogação, replay, edição simultânea, exclusão offline, recuperação de backup e queda durante envio.

## Distribuição das fontes, mantida

| Sistema | Fonte principal planejada |
|---|---|
| GitHub | Código e versões |
| Windows | Arquivos brutos e execução local |
| Supabase | Memória operacional compartilhada |
| Obsidian | Conhecimento em notas |
| Notion | Tarefas e planejamento |
| Routine/Condution | Registros de rotina |

As tarefas locais desta v0.1 são um cadastro inicial. Antes de conectar Notion, definir migração, IDs externos e autoridade de edição para não criar duas fontes conflitantes.

## Etapas posteriores

- Medir Gemma no PC real: resposta inicial, latência total, uso de memória e acerto em perguntas com fontes.
- Recuperar e revisar código atual do OrionXT antes de reutilizar STT/TTS/wake word.
- Supervisor de pastas: seleção explícita de diretórios, limites de arquivo, exclusões de segredos, leitura incremental e evidências por hash.
- Resumos analíticos: executados quando houver eventos novos, com origem, alcance e revisão; resultado do modelo continua derivado.
- Agendador na nuvem: orçamento, limite de concorrência, observabilidade e recuperação de falhas; sem depender do PC para dados já sincronizados.
- Conectores: inventário de credenciais/escopos próprios. Skills disponíveis no ChatGPT não se transferem automaticamente ao desktop.

Esta documentação descreve o próximo trabalho. Não há infraestrutura de nuvem implantada nesta entrega.
