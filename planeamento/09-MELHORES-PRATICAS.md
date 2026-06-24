# 09 — MELHORES PRÁTICAS, DICAS E TROUBLESHOOTING

---

## 9.1 Performance Optimization

### RTSP Probe

```
Problema:   Escanear 1000 IPs sequencialmente demora horas.
Solução:   ThreadPoolExecutor com 200 workers simultâneos.
           Cada probe: TCP connect (3s timeout) + OPTIONS + DESCRIBE.
           Total para 1000 IPs: ~15 segundos.

Dica:      Ajusta rtsp_probe_concurrent conforme a tua largura de banda.
           200 é seguro para a maioria das redes domésticas.
           Em redes empresariais, usar 50-100 para evitar deteção.
```

### API Rate Limiting

```python
# Censys: ~10 req/min grátis
# ipinfo.io: 50k req/mês (~1.5 req/min)
# Shodan: 1 query/mês grátis (paga para mais)

# Estratégia:
# 1. Fazer batch de IPs do Censys (já vem tudo de uma vez)
# 2. GeoIP em lote com cache
# 3. Stream capture em paralelo com max 10 threads
```

### Memória

```python
# Para 1000 câmaras, o ScanResult ocupa ~50-100 MB em RAM
# Para 5000+, considerar:
# - Guardar em SQLite em vez de manter em memória
# - Processar em batches de 500
# - Descartar câmaras CLOSED se não forem necessárias
```

---

## 9.2 Censys Query Optimization

### Queries Mais Eficientes

```python
# ✅ Boas queries (específicas, resultados relevantes)
"services.service_name: RTSP"
"services.service_name: RTSP and location.country: Portugal"
"services.port: 554 and services.service_name: RTSP"
"services.service_name: RTSP and services.http.response.html_title: Hikvision"

# ❌ Queries ineficientes (muito amplas)
"RTSP"                          # Muito genérico
"cam"                           # Matching em campos errados
"port: 554"                     # Sem filtro de serviço → muitos falsos positivos

# Melhores filtros
"services.service_name: RTSP and services.port: 554 and location.country_code: PT"
"services.service_name: RTSP and services.port: 80"
"services.http.response.html_title: DVR"
```

### Dicas Censys

1. **Pagination**: Usa `per_page=100` e itera com o cursor
2. **Campos relevantes**: Só pedir `ip, location, services` para reduzir payload
3. **Cache local**: Guardar resultados de queries frequentes em JSON
4. **Fallback**: Se Censys falhar, tentar `ip-api.com` (grátis, 45 req/min)

---

## 9.3 RTSP Probe Tips

### Porque Alguns IPs Não Respondem

```
Causas comuns              Solução
──────────────────────────────────────────────────
Firewall bloqueia          Testar com timeout maior
Porta 554 fechada          Tentar portas alternativas (8554, 37777)
RTSP desativado            Não há o que fazer (config do dono)
Auth requerida            Normal — 401 não é erro, é esperado
Path errado               Tentar paths alternativos (lista completa)
Rate limiting              Reduzir concorrência
Câmara offline            Marcar como CLOSED, não retentar
```

### Porque o DESCRIBE Falha Mesmo com TCP OK

```python
# Algumas câmaras precisam de headers específicos
# Problema comum: falta de "Accept: application/sdp"

# ✅ Correto
describe = (
    f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\n"
    f"CSeq: 2\r\n"
    f"Accept: application/sdp\r\n"
    f"\r\n"
)

# ❌ Errado
describe = f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\n\r\n"
```

### Autenticação RTSP

```
Basic Auth:
  Header: Authorization: Basic base64(user:pass)
  URL:    rtsp://user:pass@ip:port/path

Digest Auth:
  Mais seguro, nonce, realm, etc.
  Algumas ferramentas (ex: Cameradar) têm bugs com Digest.
  OpenCV e VLC tratam Digest automaticamente.

  Dica: Se Basic não funcionar, tentar Digest.
  Se nenhum funcionar, usar VLC manualmente para testar.
```

---

## 9.4 OpenCV Stream Tips

### Stream Não Abre

```python
# 1. Verificar se o URL RTSP está correto
print(cam.rtsp_url)  # rtsp://user:pass@ip:port/path

# 2. Testar com VLC primeiro (abre o URL no VLC)
import subprocess
subprocess.run(["vlc", cam.rtsp_url])

# 3. Se VLC abre mas OpenCV não, tentar backend específico
cap = cv2.VideoCapture(cam.rtsp_url, cv2.CAP_FFMPEG)
# Em Windows, às vezes precisa de:
cap = cv2.VideoCapture(cam.rtsp_url, cv2.CAP_DSHOW)

# 4. Se mesmo assim não funciona, pode ser codec
# H.265 requer compilação especial do OpenCV
# Tentar forçar H.264 na câmara se possível
```

### Performance do Stream

```python
# Não manter streams abertos (consome largura de banda)
# Abrir, ler 1 frame, fechar
cap = cv2.VideoCapture(url)
ret, frame = cap.read()
cap.release()  # ← Fechar IMEDIATAMENTE

# Para streams múltiplos, usar batch com timeout
# Se uma câmara demora > 10s a abrir, provavelmente está offline
```

---

## 9.5 Windows-Specific Tips

### Scapy no Windows

```powershell
# Scapy no Windows precisa de Npcap (não WinPcap)
# Download: https://npcap.com/
# Durante instalação: marcar "Install in WinPcap API-compatible Mode"

# Verificar instalação
python -c "from scapy.all import ARP; print('✅ Scapy ready')"
```

### OpenCV no Windows

```powershell
# OpenCV com suporte RTSP completo
# Usar a versão oficial do pip (já inclui FFmpeg)
pip install opencv-python

# Se tiveres problemas com streams H.265
# Instalar K-Lite Codec Pack: https://codecguide.com/download_kl.htm
```

### Firewall

```powershell
# O Windows Defender pode bloquear sockets
# Criar regra de saída para RTSP
New-NetFirewallRule -DisplayName "Procurador RTSP" `
    -Direction Outbound -Protocol TCP -RemotePort 554 -Action Allow

# Verificar se a porta está acessível
Test-NetConnection -ComputerName 192.168.1.100 -Port 554
```

### Long Paths no Windows

```powershell
# Caminhos > 260 chars podem dar erro
# Ativar suporte a long paths (Windows 10+)
# Opção 1: Registo
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD

# Opção 2: Usar prefixo \\?\
# Exemplo: \\?\C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\...
```

---

## 9.6 Troubleshooting Comum

### "ModuleNotFoundError: No module named 'censys'"

```powershell
# Causa: pacote não instalado ou venv não ativado
.\venv\Scripts\Activate.ps1
pip install censys

# Se ainda falhar, verificar se o Python correto está a ser usado
where python
# Deve apontar para .\venv\Scripts\python.exe
```

### "censys.exceptions.CensysException: Authentication failed"

```powershell
# Causa: API keys inválidas ou não configuradas
# Verificar env vars:
echo $env:CENSYS_API_ID
echo $env:CENSYS_SECRET

# Se vazias, criar ficheiro .env ou definir manualmente:
$env:CENSYS_API_ID = "seu-id"
$env:CENSYS_SECRET = "seu-secret"

# Verificar se as credenciais estão corretas no site
# https://search.censys.io/account/api
```

### "OSError: [WinError 10051] A socket operation was caused by..."

```powershell
# Causa: Windows bloqueou o socket (firewall)
# Solução: Desativar firewall temporariamente para testar
# Ou criar regra como acima
```

### "cv2.error: OpenCV(4.8.0) ... Unknown/unsupported compression type"

```powershell
# Causa: OpenCV não suporta H.265 (HEVC)
# Solução 1: Forçar codec H.264 na câmara (se possível)
# Solução 2: Usar ffmpeg diretamente em vez de OpenCV
ffmpeg -rtsp_transport tcp -i "rtsp://..." -vframes 1 output.png

# Solução 3: Instalar OpenCV compilado com suporte HEVC
# (requer build manual, complicado)
```

### "json.decoder.JSONDecodeError: Expecting value"

```powershell
# Causa: Ficheiro JSON corrompido ou vazio
# Solução: Apagar e regenerar
Remove-Item data/found.json
```

### "rich.Live: Screen rendering flicker"

```powershell
# Causa: refresh muito rápido
# Solução: Aumentar refresh_per_second para 2-4
# Ou usar alternative screen (screen=True)
```

---

## 9.7 Dicas de Segurança

### API Keys

```python
# ❌ NUNCA fazer isto:
api_key = "1234567890abcdef"  # Hardcoded no código

# ✅ SEMPRE usar env vars:
import os
api_key = os.environ.get("CENSYS_API_ID")
if not api_key:
    raise ValueError("CENSYS_API_ID não configurada")

# Ou ficheiro .env (NÃO COMMITAR)
```

### Logs

```python
# ❌ NUNCA logar passwords ou tokens:
logger.info(f"Creds: {user}:{password}")  # ← PERIGO!

# ✅ Logar apenas métricas:
logger.info(f"Auth testado para {ip}")
```

### Redis / SQLite (se usar)

```python
# Se fores guardar dados sensíveis (screenshots, IPs), manter localmente
# Não enviar para serviços cloud sem permissão explícita
```

---

## 9.8 Dicas de Produtividade

### VS Code Tasks

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Run scan",
            "type": "shell",
            "command": "python -m procurador --country PT --tui",
            "problemMatcher": []
        },
        {
            "label": "Run lint",
            "type": "shell",
            "command": "ruff check procurador/ && ruff format procurador/",
            "problemMatcher": []
        },
        {
            "label": "Run tests",
            "type": "shell",
            "command": "python -m pytest tests/ -v",
            "problemMatcher": []
        }
    ]
}
```

### Aliases PowerShell

```powershell
# Adicionar ao $PROFILE
function proc-scan {
    python -m procurador --country $args[0] --tui
}
function proc-web {
    python -m procurador --country $args[0] --web
}
function proc-lint {
    ruff check .\procurador\ --fix
    ruff format .\procurador\
}
function proc-test {
    python -m pytest tests\ -v
}

# Uso:
# proc-scan PT
# proc-web PT
```

---

## 9.9 Referências e Leitura Adicional

### Protocolos
- [RTSP RFC 2326](https://datatracker.ietf.org/doc/html/rfc2326)
- [ONVIF Core Spec](https://www.onvif.org/specs/core/ONVIF-Core-Specification.pdf)
- [WS-Discovery](https://docs.oasis-open.org/ws-dd/discovery/1.1/os/wsdd-discovery-1.1-spec-os.html)

### Ferramentas
- [Censys Search](https://search.censys.io)
- [Shodan](https://shodan.io)
- [Cameradar](https://github.com/Ullaakut/cameradar)
- [RTSPBrute](https://gitlab.com/woolf/RTSPbrute)
- [onvif-python](https://github.com/nirsimetri/onvif-python)

### Leitura
- [Compromising CCTVs 101](https://gill-singh-a.github.io/p/compromising-cctvs-101)
- [IP Camera Security Research](https://agencyresearch.net/security-and-privacy-evaluation-of-ip-cameras-on-shodan/)
- [Shodan Cheat Sheet](https://infosecone.com/blog/shodan-cheat-sheet)
- [RTSP URL List](https://www.smartrtsp.com/guides/rtsp-url-list)

---

> Seguir para o documento 10 — CÓDIGO EXEMPLO
