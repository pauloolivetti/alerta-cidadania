# Alerta Cidadania

Consulta automaticamente o seu processo de cidadania no **Giustizia Civile** (o mesmo
servidor do app oficial) 3 vezes por dia e avisa por **e-mail**, **Telegram** e/ou
**ntfy** quando o status, o histórico ou a data da audiência mudam.

Custo: **R$ 0**. Roda no GitHub Actions (grátis num repositório privado, usa uns 100 de
2.000 minutos/mês), o estado fica salvo no próprio repositório, e-mail sai pelo Gmail.

Baseado no endpoint documentado pela
[GiustiziaCivileAPI](https://github.com/lucasprates/GiustiziaCivileAPI), reescrito em
Python sem dependências.

---

## Passo 1: dados do processo

| Secret         | O que é                                           | Exemplo       |
|----------------|---------------------------------------------------|---------------|
| `GC_NUMERO`    | Número do ruolo (RG)                              | `12345`       |
| `GC_ANNO`      | Ano do ruolo                                      | `2024`        |
| `GC_IDUFFICIO` | Código do tribunal (opcional, padrão Roma)        | `0580910098`  |
| `GC_REGISTRO`  | Registro (opcional, padrão `CC`)                  | `CC`          |

Se o processo **não** é em Roma (desde 2023 muitos foram para tribunais regionais como
Veneza, Bolonha etc.), o código do tribunal aparece na captura do Passo 2 (parâmetro
`idufficio`).

## Passo 2: credenciais do app (a parte chata, feita uma vez)

O servidor só responde com o `uuid` e o `token` gerados pelo app no seu celular. Para
pegá-los:

1. Instale o [mitmproxy](https://mitmproxy.org) no computador e rode `mitmweb`.
2. No celular (mesma rede Wi-Fi), configure o proxy HTTP manual para o IP do computador,
   porta `8080`, abra `http://mitm.it` e instale/confie no certificado.
3. Abra o app **Giustizia Civile** e consulte o seu processo.
4. No `mitmweb`, clique na requisição para `mob.processotelematico.giustizia.it` e copie
   os parâmetros: `uuid`, `token`, `devicename`, `devicewidth`, `deviceheight`,
   `version`, `platform` (e `idufficio`, se não for Roma).
5. Tire o proxy do celular depois.

Secrets: `GC_UUID`, `GC_TOKEN`, `GC_DEVICENAME`, `GC_DEVICEWIDTH`, `GC_DEVICEHEIGHT`,
`GC_APP_VERSION`, `GC_PLATFORM`.

## Passo 3: como receber o aviso (escolha um ou mais)

**E-mail (Gmail)**: ative a verificação em 2 etapas e crie uma
[senha de app](https://myaccount.google.com/apppasswords).
Secrets: `SMTP_USER` (seu gmail), `SMTP_PASSWORD` (a senha de app), `EMAIL_TO`
(pode ser o mesmo e-mail; aceita vários separados por vírgula).

**Telegram (recomendado, chega como notificação no celular, igual SMS)**:
fale com o [@BotFather](https://t.me/BotFather), `/newbot`, copie o token. Mande um "oi"
para o seu bot e abra `https://api.telegram.org/bot<TOKEN>/getUpdates` para ver o seu
`chat.id`. Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

**ntfy**: instale o app ntfy, assine um tópico com nome difícil de adivinhar.
Secret: `NTFY_TOPIC`.

> SMS de verdade não tem opção gratuita confiável (Twilio e afins cobram por mensagem).
> Telegram ou ntfy fazem o mesmo papel de graça.

## Passo 4: ligar

1. Crie um repositório **privado** com estes arquivos.
2. Em *Settings → Secrets and variables → Actions*, cadastre os secrets acima.
3. Em *Actions → Verificar processo → Run workflow*, marque "teste" para checar as
   notificações. Depois rode sem marcar para a primeira consulta.

A partir daí roda sozinho às 06h17, 12h17 e 18h17 (Brasília). Para mudar, edite o `cron`
em `.github/workflows/verificar.yml`. Não diminua muito o intervalo: o servidor
bloqueia quem consulta demais.

## Problemas comuns

- **"falha na consulta" logo de cara**: token/uuid errado ou expirado. Refaça o Passo 2.
  Você só recebe um aviso por sequência de falhas, para não lotar o e-mail.
- **Funciona no seu PC mas não no GitHub**: o servidor do Ministério pode estar
  bloqueando IPs de fora da Itália/datacenter. Nesse caso rode no seu computador com o
  Agendador de Tarefas do Windows (ou cron), definindo as mesmas variáveis num `.env`:
  `python checker.py`.
- **Testar o parser offline**: salve a resposta do servidor em `resposta.html` e rode
  `python checker.py --parse resposta.html`.
