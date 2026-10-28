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
  deste fluxo completo. O código de armazenamento e edição manual teve testes de regressão.
- O port Redis inclui runtime MSYS2; não é Win32 puro nem uma distribuição oficial Linux.
- A memória livre inicial estava baixa por outros aplicativos abertos. O perfil usa
  um trabalho por vez e o modelo apenas no worker que transcreve.
