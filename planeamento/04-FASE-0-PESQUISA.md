# 04 — FASE 0: PESQUISA E SETUP

> Duração estimada: 1 dia
> Objetivo: Ambiente preparado, contas criadas, API keys funcionais, estrutura montada

---

## 4.1 Tarefas

### 4.1.1 Criar Contas API

| Serviço | URL | Conta | Limites Grátis | Chaves |
|---|---|---|---|---|
| **Censys** | https://censys.io/register | ✅ Grátis | 250 resultados/mês pagos, search ilimitada | `CENSYS_API_ID` + `CENSYS_SECRET` |
| **ipinfo.io** | https://ipinfo.io/signup | ✅ Grátis | 50k req/mês | `IPINFO_TOKEN` |
| **(Opcional) Shodan** | https://account.shodan.io/register | ✅ Grátis | 1 página (~100 resultados) | `SHODAN_API_KEY` |
| **(Opcional) MaxMind** | https://www.maxmind.com/en/geolite2/signup | ✅ Grátis | GeoLite2 DB | Ficheiro `.mmdb` |

### 4.1.2 Setup do Ambiente

```powershell
# 1. Criar estrutura de pastas
cd C:\Users\rodri\Desktop\PROCURADOR DE CAMERA
mkdir procurador, procurador/sources, procurador/core, procurador/ui, procurador/ui/web
mkdir procurador/ui/web/templates, procurador/ui/web/static, procurador/export
mkdir procurador/utils, data, data/screenshots, data/reports, wordlists, tests
mkdir tests/fixtures

# 2. Criar ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Verificar instalação
python -c "import censys; import requests; import rich; print('✅ All good')"
```

### 4.1.3 Configurar Variáveis de Ambiente

```powershell
# PowerShell profile ($PROFILE)
$env:CENSYS_API_ID = "seu-id-aqui"
$env:CENSYS_SECRET = "seu-secret-aqui"
$env:IPINFO_TOKEN = "seu-token-aqui"
$env:SHODAN_API_KEY = "sua-key-aqui"  # opcional

# Ou criar .env na raiz do projeto
# .env file (não commitado!)
CENSYS_API_ID=xxx
CENSYS_SECRET=xxx
IPINFO_TOKEN=xxx
SHODAN_API_KEY=xxx
```

### 4.1.4 Testar APIs

```python
# test_apis.py — Verificar se as APIs funcionam
import os
from censys.search import CensysHosts

# Test Censys
try:
    c = CensysHosts()
    results = c.search("services.service_name: RTSP", per_page=5)
    count = sum(1 for _ in results)
    print(f"✅ Censys OK — {count} resultados RTSP encontrados")
except Exception as e:
    print(f"❌ Censys error: {e}")

# Test ipinfo
try:
    import requests
    r = requests.get(f"https://ipinfo.io/8.8.8.8?token={os.environ['IPINFO_TOKEN']}")
    data = r.json()
    print(f"✅ ipinfo OK — {data.get('city')}, {data.get('country')}")
except Exception as e:
    print(f"❌ ipinfo error: {e}")
```

---

## 4.2 Estrutura Final da Fase 0

```
C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\
│
├── venv/                        # Ambiente virtual
├── procurador/                  # Pacote principal
│   ├── __init__.py
│   ├── __main__.py              # (vazio por agora)
│   ├── config.py
│   │
│   ├── sources/
│   │   ├── __init__.py
│   │   └── censys.py            # (stub)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── models.py            # Dataclasses
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   └── tui.py               # (stub)
│   │
│   ├── export/
│   │   └── __init__.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py
│
├── .env                         # API keys (NÃO COMMITAR)
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 4.3 Dicas e Boas Práticas

### Git
```bash
git init
git add .
git commit -m "feat: initial project scaffold"

# .gitignore essencial
cat > .gitignore << EOF
venv/
.env
__pycache__/
*.pyc
data/screenshots/
data/reports/
*.egg-info/
dist/
build/
.DS_Store
EOF
```

### Linter e Formatter
```powershell
# Ruff — tudo num comando
pip install ruff
ruff check procurador/ --fix
ruff format procurador/
```

### Type Checking
```powershell
pip install mypy
mypy procurador/ --strict
```

---

## 4.4 Troubleshooting Comum

### "censys module not found"
```powershell
pip install censys
# Se falhar: python -m pip install censys
```

### "API key invalid"
```powershell
# Verificar se as env vars estão carregadas
echo $env:CENSYS_API_ID
echo $env:CENSYS_SECRET
# Se estiverem vazias, carregar o .env:
Get-Content .env | ForEach-Object {
    $k, $v = $_ -split '=', 2
    Set-Item "env:$k" $v
}
```

### "sockets não funcionam no Windows"
```powershell
# Verificar firewall
New-NetFirewallRule -DisplayName "Procurador RTSP" -Direction Outbound -Protocol TCP -LocalPort 554 -Action Allow
```

### "OpenCV não abre stream RTSP"
```powershell
# Verificar se ffmpeg está instalado (OpenCV usa como backend)
ffmpeg -version
# Se não tiver: https://ffmpeg.org/download.html
# Adicionar ao PATH
```

---

## 4.5 Checklist da Fase 0

- [ ] Conta Censys criada
- [ ] Conta ipinfo.io criada
- [ ] (opcional) Conta Shodan criada
- [ ] API keys em variáveis de ambiente
- [ ] Ambiente virtual criado e ativado
- [ ] `pip install -r requirements.txt` sem erros
- [ ] `import censys, rich, requests` funciona
- [ ] Censys search retorna resultados
- [ ] ipinfo.io resolve IPs
- [ ] Estrutura de pastas montada
- [ ] `.gitignore` configurado
- [ ] `ruff lint` limpo
- [ ] `mypy` sem erros
- [ ] Primeiro commit feito

---

## 4.6 Próximos Passos

Após completar a Fase 0, avançar para:

➡️ **FASE 1: CORE ENGINE**
- Implementar modelos de dados
- Módulo Censys (queries + parse)
- Motor de scan RTSP (probe com socket)
- Motor de brute force (default creds)
- Resolvedor GeoIP
- Guardar resultados em JSON

---

> Seguir para o documento 05 — FASE 1: CORE ENGINE
