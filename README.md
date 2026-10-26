# Nexus ME · 0.1.0

Primeiro aplicativo desktop do Nexus ME, criado para Marcos Eduardo.
Esta entrega implementa o núcleo local: memória verificável por projeto,
conversa com modelo local e consulta opcional à API da OpenAI.

## Abrir no Windows

1. Instale **Python 3.12 ou superior, 64 bits**, pelo [site oficial](https://www.python.org/downloads/windows/), com `pip`.
2. Extraia o ZIP inteiro para uma pasta sua, por exemplo `Documentos\NexusME`. Não execute de dentro do ZIP.
3. Abra **INSTALAR.bat**. Ele cria um ambiente isolado `.venv` e baixa a dependência PySide6.
4. Depois abra **INICIAR_NEXUS.bat**.

O aplicativo pode ser usado sem Ollama, sem API key e sem conta na nuvem.
Instalar a dependência requer internet; o modo de consulta aos registros funciona offline.
O pacote entregue é **código-fonte executável com Python**, não um instalador `.exe` pronto.

## Primeiro uso, em poucos passos

1. O projeto **Nexus ME** já contém duas notas sobre as decisões e o escopo desta entrega. São registros de planejamento, não integrações ativas.
2. Em **Conversa**, mantenha `Consultar registros · sem IA` e pergunte “Como está o Nexus ME?”. Você verá registros, fontes e datas.
3. Use **+ Projeto** para cadastrar Build a Bot ou outro projeto. A memória começa vazia.
4. Em **Memória**, salve uma decisão ou importe um `.md`, `.txt` ou JSON compatível da Condution. Revise a prévia antes da importação.
5. Cadastre tarefas e exporte um resumo quando precisar levar o contexto a outro ambiente.

Os exemplos em `examples/` são explicitamente fictícios. Eles não são importados automaticamente.

## Conversa local com Gemma ou outro modelo

1. Instale o [Ollama para Windows](https://ollama.com/download/windows).
2. Baixe o modelo desejado. Para testar o candidato discutido, a tag `gemma4:e4b` estava disponível no catálogo oficial consultado em 19/10/2026 UTC:

   ```powershell
   ollama pull gemma4:e4b
   ```

3. Mantenha o Ollama em execução. Em **Conexões**, clique em **Buscar modelos instalados**.
4. Escolha o nome exato retornado e clique em **Salvar configurações**.
5. Em **Conversa**, selecione `Conversa local · Ollama`.

O modelo pode ser trocado; o aplicativo não depende especificamente de Gemma.
O desempenho e o consumo na RTX 5070 de 12 GB ainda precisam ser medidos no seu PC.
Esta versão envia **texto** ao modelo. Não oferece entrada por microfone, imagem ou áudio nativo do Gemma.
O botão **Ouvir resposta** usa as vozes do sistema disponíveis via Qt; a voz e o suporte a português dependem da instalação do Windows.

Para desabilitar os recursos de nuvem do próprio Ollama, siga sua [documentação oficial](https://docs.ollama.com/faq): `OLLAMA_NO_CLOUD=1` no processo que executa o Ollama ou `disable_ollama_cloud: true` em sua configuração. Reinicie o Ollama após a mudança. Definir a variável somente no Nexus não modifica um Ollama que já esteja aberto.

O Nexus aceita apenas um endpoint HTTP de loopback numérico, inicialmente `http://127.0.0.1:11434`. Bloqueia redirecionamentos e modelos identificados como remotos. Isso não substitui a configuração e a confiança no servidor local escolhido.

## GPT sob demanda

1. Em **Conexões**, informe o ID de um modelo acessível na sua conta de API da OpenAI e a chave de API.
2. Salve as configurações. **A chave fica só na memória da sessão**; as demais preferências ficam no disco.
3. Em **Memória**, selecione quais registros podem ser incluídos em consultas ao GPT e salve a permissão.
4. Em **Conversa**, escolha `Análise sob demanda · GPT`.
5. Revise o conteúdo exato mostrado antes de enviar.

A API tem cobrança e autenticação próprias. Esta versão não entra automaticamente na sua conta do ChatGPT nem herda seus plugins. A consulta inclui sua pergunta, o nome do projeto e os trechos permitidos; **não inclui o histórico da conversa nem as tarefas locais**. Para enviar uma tarefa ao GPT, descreva-a na pergunta ou registre uma memória permitida.

O envio usa `POST https://api.openai.com/v1/responses`, limite de saída configurável e `store=false`. Esse parâmetro não é garantia de ausência de toda retenção; continuam aplicáveis as políticas do provedor. Nenhuma chamada paga foi realizada durante a construção e os testes desta entrega.

O campo também aceita uma chave fornecida pela variável de ambiente `OPENAI_API_KEY`, se ela já existir. O Nexus não cria nem altera essa variável. Não coloque credenciais em memórias ou arquivos de projeto.

## Memória e importação

- Banco SQLite com projetos, memórias, tarefas, histórico de conversa e auditoria.
- Cada memória preserva fonte, data da fonte, data de registro, tipo e identificador.
- Busca textual sem distinção de acentos; seleção por relevância simples, sem embeddings.
- Respostas geradas ficam no histórico. Não viram fatos da memória automaticamente.
- Conteúdo e fonte são preservados: para registrar uma correção, crie uma nova nota citando a anterior. Registros contraditórios não são fundidos automaticamente.
- `.md` e `.txt`: UTF-8, até 40.000 caracteres. A data usada é a modificação do arquivo; pode não representar a data dos fatos.
- JSON Condution: exige `sessoes_estudo`, entre 1 e 500 sessões e até 10 MB. Somente os campos de estudo reconhecidos são importados.
- Dados de sono, treinos, alimentação e uso bruto do computador ficam de fora deste importador.
- A prévia não grava; confirmar faz uma transação. Registros idênticos são deduplicados por projeto. Uma mudança de conteúdo cria outra versão histórica.
- Documento importado ganha referência ao nome do arquivo e SHA-256. Sessões da Condution usam `id_origem`, permitindo deduplicar entre exports diferentes.
- Não há monitoramento de pastas. O aplicativo só lê o arquivo selecionado.

**Resumo local** é uma compilação determinística: até 30 memórias, trechos de até 2.000 caracteres, com avisos de truncamento. Não é um relatório analítico do GPT. A nova data do relatório não atualiza a data das fontes.

## Dados, backup e restauração

Por padrão, no Windows:

```text
%LOCALAPPDATA%\NexusME\nexus.sqlite3
%LOCALAPPDATA%\NexusME\settings.json
```

As conversas também são persistidas no SQLite. O banco não tem criptografia própria nesta versão. Proteja a conta e o disco; trate os backups como dados pessoais.

Use **Atividade → Criar backup do banco**. O backup usa a API do SQLite para incluir dados ainda no WAL. Não copie só o arquivo principal enquanto o aplicativo estiver aberto.

Para restaurar:

1. Feche o Nexus e preserve uma cópia da pasta de dados atual.
2. Coloque o backup, renomeado para `nexus.sqlite3`, em uma **nova pasta vazia**.
3. Teste a restauração com `python run_nexus.py --data-dir "C:\caminho\pasta-restaurada"` usando o Python do ambiente `.venv`.
4. Verifique os projetos e registros antes de adotar a pasta restaurada. Não misture arquivos `-wal` ou `-shm` de outro banco.

`NEXUS_DATA_DIR` ou `--data-dir` permitem uma pasta alternativa. O arquivo de bloqueio evita abrir duas janelas para a mesma pasta.

## Testes e diagnóstico

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m nexus_me --doctor
.venv\Scripts\python.exe -m nexus_me --brief --project "Nexus ME"
```

Também há `TESTAR.bat`. Os testes usam bancos temporários, servidor HTTP de teste e respostas simuladas; não chamam serviços pagos. Resultados e limites estão em `docs/VALIDACAO.md`.

Opcionalmente, `GERAR_EXE.bat` compila no próprio Windows com PyInstaller e cria `dist\NexusME\NexusME.exe`. Copie a pasta gerada inteira para distribuir. Esse processo e o executável Windows ainda precisam de validação no Windows; não foram compilados neste ambiente Linux.

## O que vem depois

Supabase autenticado e sincronização; ferramentas MCP para o plugin existente; voz de entrada; adaptadores dos projetos atuais; supervisão de pastas autorizadas; resumos agendados somente de dados alterados.

Nenhuma dessas conexões futuras é simulada como ativa na interface. Consulte `docs/ARQUITETURA.md`, `docs/AUDITORIA_INICIAL.md` e `docs/CONTINUAR.md`.
