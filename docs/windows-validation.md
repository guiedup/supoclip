# Registro de validação no Windows

Data: **28/10/2026**, Windows 11 Home x64, computador com 16 GB de RAM.
O teste foi executado diretamente no Windows. Nenhum Docker, WSL, Gateway ou VPS foi usado.

## Ambiente verificado

- 9Router instalado: **0.5.104**, porta local **20128**; combo **MyCombo** anunciado pela API.
- Python do ambiente virtual: **3.12.11**, separado do Python global 3.14.
- FFmpeg **8.1.2**, incluindo H.264, AAC e libass.
- PostgreSQL **18.6**: executáveis existentes, cluster SupoClip independente na porta 55432.
- Redis **8.10.3**, port Windows MSYS2: SHA256 conferido, PING e heartbeat ARQ observados.
- Tesseract **5.4.0.20240606**, pacote WinGet com hash verificado; dados `eng.traineddata` presentes.
- API `/health/db` respondeu 200; worker processou geração e exportação reais.

## Transcrição e serviços de áudio

Uma requisição multipart real ao STT do 9Router para `groq/whisper-large-v3`
retornou **HTTP 400: No credentials for provider: groq**. A conexão Groq encontrada
estava desabilitada. O teste não demonstrou timestamps por palavra pelo 9Router.
Nenhum provedor ou combo compartilhado foi reconfigurado.
A inspeção do adaptador OpenAI STT dessa versão também mostrou que ele não encaminha
`timestamp_granularities[]`. Essa limitação adicional está descrita no guia de instalação;
o suporte real a palavras precisará ser confirmado quando houver um provedor habilitado.

O caminho alternativo autorizado usa **Whisper tiny local, CPU**. A análise e seleção
dos cortes permanecem no MyCombo. O TTS Edge/Bing do 9Router recebeu erro 401 do serviço
externo, propagado como 502; esse recurso não é necessário no fluxo de cortes.

## Fluxo real pela interface

O navegador abriu a instância local, criou uma conta de teste, enviou os arquivos,
iniciou as gerações e acompanhou sua conclusão. Nenhum endpoint de IA ou render foi simulado.

1. **Primeiro vídeo sintético curto:** confirmou upload, transcrição, renderização
   e cache com 76 palavras temporizadas. MyCombo devolveu zero candidatos e o projeto
   usou sua janela de reserva. Esse resultado não foi contado como seleção pela IA.
2. **Segundo vídeo sintético: 85,974 segundos**, padrão visual FFmpeg 640×360 e
   narração SAPI sobre compatibilidade com Windows. Whisper gerou **203 palavras
   com timestamps** no cache utilizado pelas legendas.
3. MyCombo efetivamente selecionou **dois trechos**. O modelo identificado na
   resposta foi `gpt-6.1-sol`:

| Intervalo selecionado | Título produzido pela IA | Pontuação do modelo |
| --- | --- | --- |
| 00:00–00:35 | Removing the Lock Can Corrupt Your Files | 87 |
| 00:53–01:25 | Successful Imports Don't Prove Video Exports Work | 80 |

4. Ambos os cortes apareceram como concluídos na interface, com títulos, legendas,
   miniaturas e pontuações. A prévia do primeiro clipe abriu e carregou o vídeo
   em **1080×1920**, `readyState=4`, com avanço do tempo observado.
5. A captura visual confirmou título e legendas queimados no vídeo, incluindo
   o destaque da palavra falada.
6. O botão de download baixou o clipe original. Depois foi selecionada a predefinição
   **Reels** e o botão iniciou um trabalho `export_clip_preset` real no ARQ.
   O worker concluiu a exportação e a interface baixou o arquivo.

## Arquivos exportados

| Arquivo local de evidência | Duração | Vídeo | Áudio | Decodificação completa |
| --- | --- | --- | --- | --- |
| `original-clip.mp4` | 36,400 s | H.264, 1080×1920 | AAC | Passou |
| `reels-export.mp4` | 36,411 s | H.264, 1080×1920 | AAC | Passou |

Os dois downloads foram inspecionados com FFprobe e decodificados integralmente
com FFmpeg sem erro. As imagens `clip-preview.jpg`, `task-completed.jpg` e
`burned-captions.png`, os vídeos e `validation.json` estão em `.local/validation`,
fora do versionamento. As credenciais da conta de teste ficam somente no arquivo
privado `test-account.json` dessa pasta.

## Testes de regressão

**207 testes passaram** no conjunto documentado em [windows-native.md](windows-native.md#testes).
Outros **43 testes passaram** para seleção com janelas/reavaliação e download por
proxy do YouTube, totalizando **250** testes nesses conjuntos sem sobreposição.
Foram incluídos testes reais de bloqueio compartilhado/exclusivo entre processos,
conversão de segundos para milissegundos, recusa de timestamps ausentes/inválidos,
proteção de conteúdo de erros de provedores, roteamento de chat para a URL correta,
importação da API sem carregar PyTorch e filtros FFmpeg com caminhos difíceis no Windows.
Os testes originais de armazenamento, replicação, edição, legendas, modelos e
limites de fonte também foram executados nesse conjunto.
Após remover a necessidade de symlink na combinação, **37 testes de edição e
combinação passaram novamente**, incluindo renderizações reais com áudio e
controle de progresso em outro diretório; esse conjunto se sobrepõe parcialmente ao anterior.

O build de produção do frontend passou pela compilação, lint e TypeScript.
O script de parada foi exercitado com os serviços ociosos e preservou o 9Router
e o banco de outros aplicativos. O relatório não equivale a homologação de toda
a suíte original ou a testes de carga.

O `Install.ps1 -UseLocalWhisper` completo terminou com código zero, preservou os
arquivos privados existentes e criou `SupoClip.lnk` na Área de Trabalho.
O atalho foi efetivamente executado: PostgreSQL, Redis, API, worker e frontend
voltaram a funcionar. Foram confirmados novamente PING, heartbeat ARQ novo,
`/health/db` HTTP 200 e frontend HTTP 200. O build final usa o servidor Next.js
normal no Windows, sem o modo standalone de contêiner; a opção Linux original é preservada.

## Limites observados

- O STT do 9Router continua sem credenciais habilitadas para o provedor testado.
- Tiny cometeu erros de reconhecimento em termos técnicos; revisar legendas é necessário.
- O vídeo sintético não valida enquadramento de rosto, múltiplos falantes ou conteúdo real longo.
- YouTube, B-roll, publicação social, e-mail, S3 e edição por conversa não fizeram parte
  do fluxo sintético inicial. A importação real do YouTube foi testada depois,
  conforme a seção seguinte. Armazenamento e edição manual tiveram testes de regressão.
- O port Redis inclui runtime MSYS2; não é Win32 puro nem uma distribuição oficial Linux.
- A memória livre inicial estava baixa por outros aplicativos abertos. O perfil usa
  um trabalho por vez e o modelo apenas no worker que transcreve.

## Correção inicial de diagnóstico do YouTube (antes de conectar a sessão)

Um uso posterior encontrou a resposta de verificação humana do YouTube antes de
qualquer transcrição. O erro genérico de download ocultava essa causa e a página
oferecia retomar a mesma tentativa. Isso não representou uma validação bem-sucedida
de importação do YouTube.

A correção preserva `youtube_access_required` no campo de erro já existente,
interrompe novas tentativas/provedores depois dessa resposta e mostra a orientação
de usar o arquivo original. Falhas recuperáveis continuam com a opção de retomar.
Não foram extraídos cookies nem contornada a verificação.

Os **101 testes** de URLs, download, limpeza e classificação de acesso passaram.
Eles verificam o tratamento de respostas registradas/simuladas; não demonstram
que um vídeo bloqueado possa ser baixado. Os testes de interface dessa situação
podem ser executados contra a instalação já iniciada com:

```powershell
cd frontend
npm exec --offline -- playwright test --config playwright.native.config.ts
```

Essa configuração usa Edge já instalado no Windows, simula as respostas de tarefa
no navegador e não inicializa nem modifica o banco da instalação.
Os **dois testes de interface passaram**: o bloqueio mostra uma orientação segura
sem retomar automaticamente, enquanto falhas comuns preservam a retomada.
O build de produção, lint e TypeScript passaram. A instância local foi reiniciada
e a tarefa afetada foi conferida visualmente com o erro específico. A importação
desse vídeo permaneceu bloqueada; nenhum resultado de cortes foi declarado para ele.

## Importação autenticada do vídeo real do YouTube

Após o usuário concluir o login/reprodução no Firefox, uma exportação local
restrita a cookies do YouTube permitiu consultar e baixar o vídeo
`ftnNVxAQ8C4`: **Culto Noturno | Guiados pelo Senhor no desconhecido - Josue 3-4 -
Rev. Vitor Paulo | 18/10/2026**. Não houve alteração do 9Router, proxy ou envio
de cookies a outro serviço.

- Duração medida: **4690,014 s** (1h18min10s).
- Vídeo: H.264, **1280×720**; áudio: Opus no contêiner MP4.
- Tamanho do arquivo completo: **266.703.366 bytes**; download/adoção no cache:
  **51,7 s** neste teste.
- Tarefa criada pela interface real a partir do link `/live/`, persistido como
  URL canônica `/watch?v=`: `724f0883-4dd9-4cdb-9322-f0350b1adc80`.
- Perfil do teste: Whisper **base**, idioma **pt**, CPU com duas threads;
  análise/seleção pelo **MyCombo** do 9Router local, uma tarefa por vez.

A decodificação completa de áudio e vídeo do arquivo baixado passou com
`ffmpeg -xerror`, sem mensagens de erro. Whisper base concluiu a transcrição
em aproximadamente **16 minutos** na CPU i5-12450H com duas threads:
**8.947 palavras**, idioma `pt`, de **134,659 s** a **4689,330 s**. A inspeção
dos tempos não encontrou intervalos invertidos, ordem regressiva nem palavras
fora da duração da fonte. **309 palavras têm duração zero** no alinhamento
produzido pelo Whisper; os tempos foram preservados, sem interpolação artificial.
Isso e eventuais erros de reconhecimento exigem revisão editorial das legendas.

O pico observado do working set do processo do worker foi aproximadamente
**2,75 GiB** até o fim da transcrição. Não é a memória total do aplicativo ou do PC.
A interface mantém 30% durante toda a etapa de reconhecimento e avança ao final;
não há checkpoint persistente por janela do Whisper. Se essa etapa for
interrompida antes de gravar o resultado, o áudio precisa ser reconhecido novamente.
O arquivo original e a transcrição concluída ficam no cache para as etapas seguintes.

**97 testes de backend** passaram no conjunto de sessão local, acesso ao YouTube,
download, duração e limpeza. O subconjunto de **11 testes** da sessão passou
novamente após forçar verificação TLS e proteger os avisos do parser contra
vazamento de conteúdo. Lint e TypeScript também passaram. A atualização da sessão
pelo launcher foi exercitada durante a transcrição sem interromper o trabalho.

MyCombo analisou **oito janelas sobrepostas**, reuniu e reavaliou **21 candidatos**
e produziu os dois clipes finais. O modelo retornado pelo 9Router foi
`gpt-6.1-sol`, usando a configuração `openai:MyCombo` já existente.

| Título do clipe | Duração do MP4 |
| --- | ---: |
| Você lembra das dores, mas esquece dos livramentos | 52,6 s |
| O maior feito não foi uma casa | 45,9 s |

Ambos os arquivos renderizados passaram pela decodificação integral com
`ffmpeg -xerror`, com vídeo **H.264 1080×1920** e áudio **AAC**. A tarefa chegou
a `completed`/100%. A verificação pela interface real incluiu abertura do player,
reprodução efetiva, download do original e exportação do primeiro clipe pelo
preset **YouTube Shorts**. O MP4 exportado tem **52,6 s**, **16.618.813 bytes**,
áudio presente e RMS medido de aproximadamente **0,182**; passou novamente pela
decodificação integral. O layout móvel de 390×844 não apresentou rolagem horizontal.

A inspeção visual confirmou pregador enquadrado em 9:16, legendas incorporadas
e destaque de palavras. A fonte THEBOLDFONT não contém todos os acentos usados;
o render utilizou o fallback existente **TikTokSans-Bold**. Há erros de ASR,
incluindo formas como `resgator` e uma passagem do Salmo 103 reconhecida
incorretamente. **Os clipes exigem revisão das legendas antes de publicação.**
Pontuações atribuídas pelo modelo não são previsão de desempenho no YouTube.

Os MP4s foram copiados para `%USERPROFILE%\Videos\SupoClip\ftnNVxAQ8C4-724f0883\`.
O primeiro arquivo usa a exportação Shorts testada; o segundo usa o MP4 original
renderizado, também compatível com 1080×1920/H.264/AAC.
As evidências técnicas, capturas e arquivos de teste permanecem em
`.local/validation/`, fora do Git, assim como a sessão do YouTube.

Depois de concluir todos os trabalhos, a compilação final de produção passou,
incluindo lint e TypeScript. A orientação de autenticação agora permite retomar
explicitamente depois de atualizar a sessão; o backend continua interrompendo
tentativas automáticas diante de exigência de verificação.
Os **dois testes de navegador** passaram contra esse build: orientação de sessão
com retomada explícita e recuperação de falhas comuns. Após a reinicialização,
foram confirmados novamente frontend/API HTTP 200, Redis PING e heartbeat ARQ novo.
A página dos dois clipes e a reprodução foram conferidas após esse reinício;
o editor também abriu a lista de palavras/tempos para revisão das legendas.

Na conferência final foi detectado um desvio de **+10.800 s** ao enviar um
`datetime` UTC sem timezone ao PostgreSQL pelo asyncpg no fuso local. O início
e o fim das tarefas passaram a usar UTC explícito. Os **32 testes do serviço
de tarefas** passaram, incluindo a proteção do contrato de timezone, e o
roundtrip de um datetime UTC consciente preservou o instante exato no banco real.
Os horários da tarefa de validação foram corrigidos com condição sobre os
valores anteriores; os demais registros foram preservados. O fluxo dessa
tarefa, do início do worker à conclusão, levou aproximadamente **23 minutos**.

## Modo pessoal com entrada automática (30/10/2026)

A configuração privada desta instalação habilita `NEXT_PUBLIC_LOCAL_AUTO_LOGIN`
e vincula `LOCAL_AUTO_LOGIN_USER_ID` ao proprietário que já tinha as três tarefas
da biblioteca. A conta não foi recriada nem substituída. A identificação de
proprietário e a assinatura HMAC entre frontend e API foram preservadas.

**29 testes unitários/de integração** passaram para a sessão local, o mecanismo
real do Better Auth, origens e o fluxo normal de autenticação com o modo desligado.
A compilação de produção passou com lint e TypeScript. **Quatro testes de
navegador** passaram contra o aplicativo instalado, sem semear o banco:

- Um contexto novo abre a criação e acessa preferências/biblioteca sem login.
- Limpar cookies e abrir outro contexto continua usando o mesmo proprietário.
- Entrar/cadastrar/recuperar senha redirecionam ao aplicativo; sair e excluir a
  conta ficam ocultos. A tela de configurações foi aguardada antes dessa verificação.
- Origem/host externos são recusados; a API direta continua recusando requisição
  sem autenticação assinada (HTTP 401).

Uma solicitação HTTP sem cookies confirmou a conta existente, ausência de cookie
de sessão novo e `Cache-Control: private, no-store`. O modo é ativado somente
para esta instalação local, conforme as opções em [windows-native.md](windows-native.md#uso-pessoal-sem-tela-de-login).

Um navegador novo, sem senha nem `storageState`, também abriu a tarefa real do
YouTube, preservou os dois clipes, reproduziu o vídeo e abriu o editor de legendas
com os tempos por palavra. A captura e o resultado dessa conferência ficam em
`.local/validation/personal-local-library.png` e `personal-local-validation.json`.
