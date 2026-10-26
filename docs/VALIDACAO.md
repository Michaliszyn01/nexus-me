# Validação da entrega 0.1.0

Executada em 19/10/2026 UTC, em ambiente Linux com Python 3.12.14 e PySide6 6.12.0.

## Resultados observados

| Verificação | Resultado |
|---|---|
| Testes automatizados | 31 passaram, sem falhas |
| Persistência ao reabrir o banco | Registros preservados |
| Isolamento entre projetos e sessões | Contexto de outro projeto/sessão não enviado |
| Duplicatas e versões modificadas | Conteúdo idêntico reutilizado; alteração preservada separadamente |
| Importação inválida | Nenhum registro parcial inserido |
| Export real da Condution | 10 sessões lidas e inseridas em banco temporário |
| Reimportação do mesmo export real | 0 novas inserções |
| Arquivo original da Condution | SHA-256 igual antes e depois da validação |
| Permissão inicial de dados importados | 0 registros permitidos para GPT |
| Prévia GPT | Exclui notas privadas, tarefas e histórico local |
| Cancelamento de envio na interface | Nenhuma chamada nem gravação da conversa |
| Revogação e hash de aprovação | Impedem chamada quando a autorização não corresponde |
| Endpoint local e redirecionamento | Destinos externos inválidos e redirects bloqueados |
| Modelo Ollama com metadados remotos | Bloqueado antes de enviar contexto de conversa |
| Limite de contexto | Respeitado mesmo com várias tarefas extensas |
| Resposta de API incompleta | Não é apresentada como sucesso |
| API key nas configurações | Não escrita em settings.json |
| Backup SQLite | Conteúdo equivalente e integrity_check = ok |
| Interface | Seis telas renderizadas; consulta local, tarefa, importação e configuração exercitadas |
| Janela reduzida | Layout renderizado em 1020 × 720; áreas longas rolam |
| Diagnóstico CLI | Banco ok; nuvem identificada como não implementada |

Testes de provedores usam um servidor HTTP temporário no loopback e respostas simuladas. Testes de interface usam o backend Qt offscreen e bancos temporários. A prévia visual entregue foi capturada do aplicativo real, não é um mockup.

## Limites da validação

- Não houve acesso ao Windows, à GPU ou ao Ollama do usuário.
- Não houve geração por um modelo real nesta sessão; o protocolo e a lógica foram testados.
- Não foi usada chave nem saldo da API OpenAI.
- O microfone não está implementado. A voz do sistema depende do Windows e não foi validada com áudio real aqui.
- Os scripts BAT foram revisados, mas não executados no Windows. O EXE não foi compilado.
- Não há Supabase, Notion, GitHub, MCP ou automação externa conectados ao aplicativo.
- O detector de segredos é heurístico e não garante detectar qualquer dado sensível.
- Um modelo ainda pode interpretar mal fontes ou ignorar instruções. A interface exibe as fontes recuperadas e não promove respostas automaticamente à memória.

Próximo teste necessário: rodar o pacote no Windows real e avaliar uma conversa com o modelo local escolhido, antes de iniciar a sincronização.
