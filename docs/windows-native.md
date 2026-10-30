# SupoClip no Windows, sem Docker e sem WSL

Fork independente de compatibilidade do [SupoClip original](https://github.com/FujiwaraChoki/supoclip),
de FujiwaraChoki e colaboradores. A licença **AGPL-3.0** e os créditos originais são preservados.
Redis, FFmpeg, Tesseract e os demais componentes mantêm suas próprias licenças.

## Instalação nesta máquina

Requisitos: Windows 11 x64, Git, Node.js, uv, FFmpeg completo com libass e binários PostgreSQL.
Foram encontrados Python 3.12, FFmpeg 8.1.2, PostgreSQL 18.6 e 9Router 0.5.104.
O instalador escolhe Python 3.12 explicitamente, sem trocar o Python global.
As dependências Python e JavaScript usam os lockfiles do projeto.
Tesseract é instalado pelo pacote `UB-Mannheim.TesseractOCR` do WinGet quando ausente.

```powershell
git clone https://github.com/guiedup/supoclip.git
cd supoclip
git switch codex/windows-native-9router
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\Install.ps1 -UseLocalWhisper
```

`-UseLocalWhisper` é uma escolha explícita: usa Whisper tiny na CPU para transcrever,
com os tempos por palavra produzidos pelo modelo. A análise e a seleção dos cortes
continuam no **MyCombo do 9Router**. Este perfil reduz a memória e o número de trabalhos
simultâneos, mas tiny tem precisão menor que modelos maiores, especialmente em áudio difícil.

O instalador cria o atalho **SupoClip** na Área de Trabalho e compila a interface.
Para iniciar e parar manualmente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\Start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\Stop.ps1
```

Abra **http://localhost:3107**. Crie uma conta apenas na sua instalação local.
A conta de teste usada durante a validação não é uma conta no serviço hospedado.
As senhas, configurações e os vídeos não são publicados no fork.

O encerramento recusa interromper tarefas de usuário enfileiradas ou em processamento.
O processo de parada verifica os PIDs e a data de criação dos processos iniciados
por esta instalação. Não encerra o 9Router compartilhado nem o PostgreSQL de outros aplicativos.
Não pare durante um render manual externo ao worker.

## Uso pessoal sem tela de login

A instalação pessoal pode abrir diretamente na conta local que já possui os
vídeos. Em `frontend/.env.local`, configure explicitamente:

```dotenv
SELF_HOST=true
NEXT_PUBLIC_SELF_HOST=true
NEXT_PUBLIC_LOCAL_AUTO_LOGIN=true
LOCAL_AUTO_LOGIN_USER_ID=ID_DA_CONTA_EXISTENTE
BETTER_AUTH_URL=http://localhost:3107
NEXT_PUBLIC_APP_URL=http://localhost:3107
```

O ID é o `user_id` das tarefas dessa conta. Não é criada outra conta nem movida
a biblioteca. Depois de alterar o modo, compile novamente o frontend e reinicie
a instalação quando não houver processamento ativo. A opção fica desativada
por padrão no código compartilhado; a configuração privada desta máquina a ativa.

O navegador recebe uma sessão local renovável sem pedir senha nem depender de
cookies de login. Uma janela anônima ou um navegador novo usa a mesma conta
selecionada. As páginas de entrar/cadastrar/recuperar senha redirecionam para o
aplicativo; sair e excluir a conta ficam ocultos nesse modo. Endpoints de gestão
de autenticação também são recusados, evitando perder o proprietário da biblioteca.

A entrada automática exige instalação self-host, URLs e requisições de loopback
(`localhost`/`127.0.0.1`, na porta configurada). Requisições de origem externa,
hosts encaminhados externos e acesso cross-site são recusados. A identificação
da conta para a API continua assinada pelo frontend; a API não aceita um ID de
usuário sem assinatura. Para voltar ao login normal, configure
`NEXT_PUBLIC_LOCAL_AUTO_LOGIN=false` e recompile/reinicie o frontend.

Esse modo trata o login do **SupoClip**. A sessão do YouTube usada para importar
vídeos continua sendo configurada separadamente, conforme a seção abaixo.

## Serviços e dados isolados

| Componente | Endereço nesta instalação | Observação |
| --- | --- | --- |
| Frontend | `http://localhost:3107` | Next.js, acesso somente local |
| API | `http://127.0.0.1:8000` | FastAPI; `/health/db` testa o banco |
| PostgreSQL | `127.0.0.1:55432` | Cluster exclusivo em `.local/postgres` |
| Redis | `127.0.0.1:56379` | Instância exclusiva, AOF, 128 MB, sem evicção |
| 9Router existente | `http://127.0.0.1:20128/v1` | Porta encontrada no processo local ativo |

O instalador reutiliza somente os **executáveis** do PostgreSQL instalado.
Cria outro cluster com credencial aleatória e autenticação SCRAM; o banco existente
na porta 5433 não é usado nem alterado. `init.sql` inicializa o banco dedicado,
e as migrações aditivas do backend são aplicadas no início da API.
Não aplique as migrações iniciais do Prisma sobre esse banco já inicializado.

O Redis usado é o [port comunitário redis-windows 8.10.3](https://github.com/redis-windows/redis-windows/releases/tag/8.10.3),
distribuição x64 MSYS2 portátil. Seu SHA256 é fixado e verificado antes da extração.
O executável inclui uma DLL MSYS2 de compatibilidade: **não é uma compilação Win32 pura**.
Não usa Linux, WSL, contêiner, instalação de shell MSYS2 ou serviço remoto.
Mantém a arquitetura Redis + ARQ original. É um port comunitário, sem a garantia
de suporte do Redis oficial para Linux; não foi homologado aqui para produção pública.
O limite de memória usa `noeviction`, para falhar explicitamente ao encher em vez de perder a fila.

Arquivos privados:

- `backend/.env`: credenciais e configurações do backend.
- `frontend/.env.local`: configuração e segredos de autenticação do frontend.
- `.local/windows.json`: portas e credencial do banco dedicado.
- `.local/uploads`: fontes, cortes, caches e transcrições.
- `.local/logs`: logs por serviço.
- `.local/validation`: vídeo sintético, resultados e evidências locais dos testes.

Esses caminhos são ignorados pelo Git. O instalador preserva configurações existentes
ao ser executado novamente. Um conflito de porta provoca erro em vez de reutilizar
um processo desconhecido. As portas padrão podem ser revistas nos arquivos privados
antes de iniciar; URLs e portas de ambos os ambientes devem continuar correspondentes.

## Integração com o 9Router

O instalador identifica o processo `9router/app/custom-server.js` e consulta sua porta
TCP local. Se a identificação não for única, use `-RouterUrl http://127.0.0.1:PORTA/v1`.
Leia a base **SQLite ativa** em `%APPDATA%\9router\db\data.sqlite`; o `db.json`
antigo pode conter modelos desatualizados após a migração. A leitura é feita em modo
somente leitura. Nenhum combo, provedor, chave, conexão ou outra integração é alterado.
Uma chave existente ativa e sem restrição é copiada somente para o `.env` privado.
Não é impressa nos logs de instalação ou incluída em comandos de teste publicados.

Configuração de chat:

```dotenv
LLM=openai:MyCombo
RERANK_LLM=openai:MyCombo
OPENAI_BASE_URL=http://127.0.0.1:20128/v1
OPENAI_API_KEY=<chave existente salva somente no arquivo privado>
```

O adaptador usa `OpenAIChatModel` explicitamente, inclusive para a reavaliação
dos candidatos. Não deduz suporte a áudio a partir do suporte a chat.
O 9Router é compartilhado com seus outros aplicativos; mantenha-o iniciado.

### STT pelo 9Router: contrato independente

Para usar um modelo STT **já habilitado e com credenciais** no 9Router:

```powershell
# Em uma instalação nova, forneça o identificador exato do modelo STT:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\Install.ps1 -SttModel 'groq/whisper-large-v3'
```

Em uma instalação existente, pare após concluir os trabalhos e ajuste somente
o `.env` privado do SupoClip:

```dotenv
TRANSCRIPTION_PROVIDER=openai_compatible
STT_BASE_URL=http://127.0.0.1:20128/v1
STT_API_KEY=<chave privada do 9Router>
STT_MODEL=<identificador de um modelo STT habilitado>
STT_TIMEOUT_SECONDS=300
```

O SupoClip envia áudio mono de 16 kHz por multipart para
`POST /v1/audio/transcriptions`, solicita `verbose_json` e granularidade por palavra,
e verifica a presença de tempos numéricos, finitos, ordenados e com duração positiva.
Aceita palavras no campo `words` ou dentro dos segmentos. Converte segundos para
milissegundos no cache que o gerador de legendas original já usa.
Não interpola tempos a partir do texto e não troca de provedor silenciosamente.
Áudio remoto acima de 24 MiB é recusado; use um vídeo menor neste perfil.

Na implementação instalada do 9Router 0.5.104, o adaptador de STT em formato OpenAI
encaminha `response_format`, mas sua lista de campos encaminhados não inclui
`timestamp_granularities[]`. Habilitar credenciais, por si só, não comprova o contrato:
é necessário testar se o modelo devolve `words` por padrão ou corrigir esse
encaminhamento no 9Router em trabalho separado. O SupoClip detecta a ausência dos
tempos e recusa o resultado. O 9Router compartilhado não recebeu esse patch.

**Resultado da inspeção em 28/10/2026:** MyCombo estava disponível. Os provedores
ativos encontrados eram de chat; a conexão Groq estava desabilitada. Uma solicitação
real para `groq/whisper-large-v3` recebeu HTTP 400, `No credentials for provider: groq`.
Portanto, timestamps STT vindos do 9Router **não foram confirmados neste ambiente**.
Não reativei nem reconfigurei essa conexão compartilhada. O caminho alternativo
testado separadamente usa o Whisper tiny local, preservando MyCombo para os cortes.
O TTS `edge-tts/edge-tts` também foi testado separadamente e seu serviço externo
respondeu HTTP 401, propagado pelo 9Router como 502. TTS não é necessário para cortar vídeos.

## Adaptações de compatibilidade

- Bloqueios compartilhados/exclusivos de arquivo usam `portalocker` (LockFileEx no
  Windows), preservando proteção entre processos; `fcntl` não existe no Windows.
- A escrita durável de manifestos usa `MoveFileExW` com substituição e write-through
  no Windows. Unix conserva `fsync` do arquivo e diretório. NTFS e Unix não oferecem
  garantias idênticas de persistência de diretório diante de perda de energia.
- O render fecha o log antes de apagá-lo, exigência do Windows.
- A combinação de clipes compartilha diretamente os arquivos de progresso e
  cancelamento, sem criar symlinks que exigiriam elevação ou Developer Mode.
- O worker mantém o loop Proactor e evita registro de sinais Unix. Não se usa
  `handle_signals=False`, pois o encerramento do ARQ 0.28 usa `SIGUSR1` nesse caminho.
- Whisper/PyTorch são carregados apenas quando a transcrição local é usada,
  evitando carregar o modelo na API e nos workers remotos.
- Um trabalho por vez, duas threads de Whisper e FFmpeg e dois cortes por geração
  são o perfil inicial para 16 GB. O consumo total depende dos demais programas abertos.
- O Next.js limita a busca de arquivos à pasta do projeto e a compilação a uma CPU.
- O yt-dlp pode reutilizar Node.js quando Deno não está instalado.
- Início e fim das tarefas são gravados com UTC explícito. No Windows com
  fuso de São Paulo, datetimes UTC sem timezone eram interpretados pelo asyncpg
  como horário local e ficavam três horas adiantados no banco.
- Caminhos de legenda passam pelo escape de filtros FFmpeg original, que já cobre
  letra de unidade, barras, espaços, apóstrofos e colchetes; há teste real no Windows.

## Limitações e fronteiras de validação

O teste curto usa fala sintética e padrão visual do FFmpeg: verifica a execução
das etapas e os arquivos produzidos, não a qualidade editorial em podcasts reais,
diarização de múltiplas pessoas ou rastreamento de rosto. Revise legendas antes de publicar.
Grandes lotes e suspensão/retomada do PC exigem validação adicional. O teste
de um vídeo real longo do YouTube está descrito no registro de validação.

O assistente de edição por conversa do upstream usa outro worker e uma configuração
própria de provedor; não é iniciado por padrão. O worker principal atende os cortes,
edição manual e exportação. B-roll depende de Pexels; publicação social, e-mail,
armazenamento S3 e integrações de pagamento precisam de configuração separada.
Não foram configurados para esta instalação local.
O download do YouTube depende também das restrições e desafios do serviço.
A importação por link aceita uma sessão local do YouTube configurada explicitamente.
Nenhuma publicação externa é feita pelo teste.

### YouTube pede login ou verificação no download

Se o serviço responder `Sign in to confirm you're not a bot`, a importação para
antes da transcrição. Abrir a página no navegador não comprova que o download
automático esteja autorizado. Trocar `/live/` por `/watch` mantém o mesmo ID e
não remove essa exigência.

O backend preserva o erro `youtube_access_required`, sem expor URLs assinadas ou
detalhes de autenticação. Não repete automaticamente a tentativa nem troca de
provedor depois dessa resposta. A tarefa orienta concluir o login ou verificação
no navegador, atualizar a sessão local e usar **Retomar**.

### Conectar a sessão do YouTube no Firefox

1. Abra o vídeo no Firefox, entre na sua conta e conclua pessoalmente qualquer
   verificação solicitada pelo YouTube.
2. Em `about:profiles`, identifique o **Diretório raiz** desse perfil. O script
   não escolhe nem varre os perfis por conta própria.
3. Na raiz do projeto instalado, execute no PowerShell, substituindo o exemplo:

```powershell
backend\.venv\Scripts\python.exe scripts\windows\youtube_session.py --profile "$env:APPDATA\Mozilla\Firefox\Profiles\SEU_PERFIL" --remember
```

O script consulta o SQLite do perfil em modo somente leitura e seleciona apenas
cookies de `youtube.com` e seus subdomínios, sem cookies de outros sites,
senhas ou sessões em contêineres do Firefox. Grava um arquivo Netscape privado em
`.local/youtube/cookies.txt`, com ACL restrita ao usuário do Windows, e configura
`YOUTUBE_COOKIE_FILE` no `.env` local. Não envie esse arquivo por chat ou ao Git.
Se o SQLite estiver bloqueado, feche o Firefox e execute o comando novamente.

Na primeira conexão, reinicie o SupoClip quando não houver trabalhos ativos,
usando `Stop.ps1` e o atalho **SupoClip**. Depois disso, atualizar o mesmo arquivo
de sessão não exige reiniciar API/worker. O backend carrega os cookies em memória
para consultas e downloads diretos, sem reescrever o arquivo de sessão ou o
perfil do navegador. Na ausência de configuração, o comportamento continua anônimo.
A conexão autenticada mantém a verificação dos certificados TLS habilitada,
mesmo que as opções originais de download do upstream a desabilitem.

O argumento opcional `--remember` salva o perfil escolhido em
`.local/youtube/profile.json`. Ao abrir pelo atalho, o launcher atualiza somente
os cookies do YouTube desse perfil. Sem esse argumento não há atualização
automática. Para desativá-la, remova esse arquivo de configuração privado.
Cookies podem expirar ou ser renovados pelo YouTube; após um novo login, abra o
atalho novamente para atualizar a sessão antes de retomar a tarefa.

Uma sessão indisponível, malformada ou com cookies de outro site é recusada com
`youtube_session_invalid`, sem expor caminhos/valores nem tentar provedores
alternativos. Arquivos completos já importados no cache podem continuar sendo
processados sem consultar o YouTube novamente; o limite de duração é conferido
com FFprobe sobre o arquivo local. A criação de uma nova tarefa por link ainda
consulta os metadados do YouTube.

Se o serviço continuar recusando o acesso após a verificação, a importação para
nesse ponto. A alternativa de upload local continua disponível. Quem administra
o canal também pode usar a
[opção oficial de download no YouTube Studio](https://support.google.com/youtube/answer/56100?hl=pt-BR).
O download offline do YouTube não deve ser tratado como um MP4 disponível para importação.

Para este teste de pregação em português, o perfil local foi ajustado para
`WHISPER_MODEL_SIZE=base`, `TRANSCRIPTION_LANGUAGE=pt` e `YOUTUBE_MAX_HEIGHT=720`.
O instalador mantém `tiny` e detecção automática como padrões iniciais. O modelo
base foi baixado pelo próprio Whisper; tem maior custo de CPU e memória.
Uma tarefa por vez e duas threads foram mantidas. Para vídeos em outros idiomas,
limpe `TRANSCRIPTION_LANGUAGE` ou configure o idioma correto antes de reiniciar.

Veja [o registro de validação](windows-validation.md) para os resultados observados.

## Testes

No PowerShell, dentro de `backend`, para executar os testes de regressão do port
sem herdar a seleção de Whisper do `.env` particular:

```powershell
$env:TRANSCRIPTION_PROVIDER = 'assemblyai'
$env:YOUTUBE_COOKIE_FILE = ''
$env:YOUTUBE_MAX_HEIGHT = '1080'
$env:MAX_CLIPS = '10'
$env:FAST_MODE_MAX_CLIPS = '10'
.venv\Scripts\python.exe -m pytest tests/test_native_windows.py tests/unit/test_media_storage.py tests/unit/test_media_replication.py tests/unit/test_source_limits.py tests/unit/test_ffmpeg_filter_escaping.py tests/unit/test_editor_document.py tests/unit/test_ai_models.py tests/unit/test_ai_prompt.py tests/unit/test_ai_retry.py tests/unit/test_config_ollama.py tests/unit/test_clip_editor_captions.py tests/test_video_utils_diarization.py --no-cov -q
```

Testes adicionais da sessão local e do tratamento de acesso:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_youtube_session.py tests/unit/test_youtube_utils.py tests/unit/test_youtube_access_required.py --no-cov -q
```

Esses testes não autorizam uma implantação pública nem substituem o teste completo
de integração. Logs operacionais podem conter caminhos e conteúdo de vídeos;
revise-os antes de compartilhar. A licença AGPL-3.0 continua aplicável ao código derivado.
