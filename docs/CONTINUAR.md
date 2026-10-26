# Ponto de continuação — Nexus ME 0.1.0

## Objetivo do usuário

Assistente pessoal híbrido no Windows e no ChatGPT. Modelo local conversa e apresenta dados; GPT analisa quando necessário. Memória deve funcionar na nuvem quando o PC estiver desligado. Reutilizar Routine/Condution, OrionXT e o plugin ME Nexus sem afirmar conexões inexistentes.

## Entregue

Desktop PySide6, SQLite, projetos, notas com fonte, tarefas, histórico de conversas, busca textual, importação explícita, resumo determinístico, backup, adaptador Ollama, adaptador Responses API com prévia e permissões. Voz de saída via mecanismo do sistema, ainda pendente de teste no Windows real.

Sem servidor, conta autenticada, sync, microfone, monitor de pastas ou agendador. Nenhuma chave foi inserida. Nenhum serviço foi publicado. O pacote contém fontes e instaladores BAT, não EXE compilado.

## Primeira retomada

1. Rodar `INSTALAR.bat` e `INICIAR_NEXUS.bat` no Windows.
2. Conferir consulta local, memória persistida após reabrir e importação.
3. Selecionar modelo instalado no Ollama e medir conversa em PT-BR.
4. Verificar TTS do sistema e limites de interface na resolução usada.
5. Depois construir Auth + Supabase + fila de sincronização, seguindo `ARQUITETURA.md`.

O Gemma 4 E4B permanece candidato, não escolha definitiva. A camada de modelo é configurável. Não implementar 128K de contexto por padrão; o MVP usa contexto menor e recuperação seletiva.

Não usar a assinatura do ChatGPT como se fosse uma chave de API. Não importar automaticamente credenciais dos plugins. Não repetir importação de todos os dados a cada consulta. Não promover respostas da IA a fatos verificados.

## Critério de conclusão da fase seguinte

Registrar uma nota local, sincronizar com autenticação, desligar o PC e consultar essa nota pelo plugin com fonte e data corretas. Testar isolamento de usuários, duplicatas, conflitos e revogação antes de ampliar o escopo.
