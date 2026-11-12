# Capturar o token do app Giustizia Civile (iPhone + Windows)

Tempo: uns 20 minutos, e só precisa fazer uma vez. Você vai colocar o PC "no meio do caminho"
entre o iPhone e o servidor para ler o que o app envia.

## 1. No PC (Windows)

1. Baixe e instale o **mitmproxy** em <https://mitmproxy.org> (botão "Download Windows Installer").
2. Abra o **Prompt de Comando** e rode:
   ```
   ipconfig
   ```
   Anote o **Endereço IPv4** da sua rede Wi-Fi ou Ethernet (ex.: `192.168.0.15`).
3. No mesmo prompt, rode:
   ```
   mitmweb
   ```
   O navegador vai abrir uma página do mitmweb. Deixe ela aberta.
   Se o Windows perguntar sobre o **Firewall**, clique em **Permitir** (rede privada).

## 2. No iPhone: apontar para o PC

O iPhone precisa estar no **mesmo Wi-Fi** que o PC.

1. Abra **Ajustes → Wi-Fi** e toque no **(i)** da sua rede.
2. Desça até **Configurar Proxy → Manual**:
   - Servidor: o IP do PC (ex.: `192.168.0.15`)
   - Porta: `8080`
   - Salvar.

## 3. No iPhone: instalar o certificado

1. Abra o **Safari** (precisa ser o Safari) e acesse `http://mitm.it`.
2. Toque em **iOS** → **Get mitmproxy-ca-cert.pem** e confirme **Permitir**.
3. Abra **Ajustes → Geral → VPN e Gerenciamento de Dispositivo**, toque em **mitmproxy** e depois em **Instalar** (pede o código do iPhone).
4. Abra **Ajustes → Geral → Sobre → Ajustes de Confiança de Certificados** e **ative** o mitmproxy.

## 4. Capturar

1. Feche o app Giustizia Civile por completo (deslize para cima) e abra de novo.
2. Consulte o seu processo (Venezia, 12623/2025).
3. No mitmweb do PC, procure uma linha com **`mob.processotelematico.giustizia.it`** e clique nela.
4. Na aba **Request**, copie estes valores da URL (ou tire um print da tela):

| Parâmetro na URL | Secret no GitHub  |
|------------------|-------------------|
| `uuid`           | `GC_UUID`         |
| `token`          | `GC_TOKEN`        |
| `devicename`     | `GC_DEVICENAME`   |
| `devicewidth`    | `GC_DEVICEWIDTH`  |
| `deviceheight`   | `GC_DEVICEHEIGHT` |
| `version`        | `GC_APP_VERSION`  |
| `platform`       | `GC_PLATFORM`     |

Anote também o `azione`, o `registro` e o `idufficio` que aparecerem, porque ajudam a conferir.

## 5. Desfazer (importante)

1. **Ajustes → Wi-Fi → (i) → Configurar Proxy → Desativado.** Sem isso, a internet do iPhone para quando o PC desligar.
2. Opcional: **Ajustes → Geral → VPN e Gerenciamento de Dispositivo → mitmproxy → Remover Perfil**.
3. No PC, feche o mitmweb com `Ctrl+C`.

## Se não aparecer nada

- **O app dá erro de conexão:** o app pode estar bloqueando certificados de terceiros ("pinning"). Me mande um print, porque existe plano B.
- **Nenhuma linha aparece no mitmweb:** confira o IP, se a porta é a `8080` e se o Firewall do Windows liberou o acesso.
- **O token muda?** Normalmente ele fica fixo por aparelho e instalação. Se você reinstalar o app, talvez precise capturar de novo.
