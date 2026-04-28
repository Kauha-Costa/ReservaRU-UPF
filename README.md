# 🍽️ Reserva RU UPF

Automação da reserva de refeições no Restaurante Universitário da Universidade de Passo Fundo (UPF) via Google Forms com Selenium. Empacotado como aplicativo desktop para Windows — sem precisar de Python instalado.

---

## 💡 Motivação

O RU da UPF exige que a reserva de refeições seja feita diariamente através de um Google Forms, antes das 10h. Preencher o formulário manualmente todos os dias é repetitivo e fácil de esquecer. Este projeto automatiza todo esse processo: basta abrir o app, clicar em "Fazer reserva" e o Chrome preenche e envia o formulário sozinho.

---

## ✨ Funcionalidades

- Preenche e envia o formulário do RU automaticamente via Selenium
- Suporte a múltiplos perfis (ex: você + outra pessoa)
- Interface web local para gerenciar perfis e acompanhar o status
- Log diário com horário e resultado de cada reserva
- Roda em modo headless (Chrome invisível em segundo plano)
- Empacotado em `.exe` para distribuição sem dependências externas

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|---|---|
| **Python 3.10+** | Linguagem principal |
| **Flask** | Servidor web local que serve a interface e a API REST |
| **Selenium** | Automação do Google Chrome para preencher o formulário |
| **PyInstaller** | Empacota tudo em um único `.exe` sem precisar de Python instalado |
| **HTML/CSS/JS** | Interface web servida pelo Flask (`app_ui/index.html`) |

---

## 🏗️ Como funciona

```
┌─────────────────────────────────────────────────────┐
│                   ReservaRU.exe                     │
│                                                     │
│  Flask (localhost:5757)                             │
│    ├── serve a interface web (app_ui/index.html)    │
│    ├── GET  /api/config   → perfis e configurações  │
│    ├── GET  /api/status   → reservas do dia         │
│    ├── GET  /api/log      → linhas do log diário    │
│    └── POST /api/reservar → dispara a automação     │
│                                  │                  │
│                         thread separada             │
│                                  │                  │
│                         reserva.py                  │
│                    (preencher_form)                  │
│                           │                         │
│                    Chrome via Selenium               │
│                           │                         │
│                  Google Forms do RU UPF             │
└─────────────────────────────────────────────────────┘
```

1. O `.exe` inicia um servidor Flask em `localhost:5757` e abre o navegador automaticamente
2. O usuário seleciona o perfil e clica em "Fazer reserva"
3. O Flask chama `preencher_form()` do `reserva.py` em uma thread separada
4. O Selenium abre o Chrome, navega até o formulário, preenche todos os campos via URL de pre-fill e clica em Enviar
5. O resultado é gravado no log diário e exibido na interface

---

## 📁 Estrutura do projeto

```
almoco_auto/
├── app.py                        # servidor Flask — rotas da API e lógica principal
├── reserva.py                    # automação Selenium — preenche e envia o formulário
├── build_exe.py                  # script que gera o ReservaRU.exe com PyInstaller
├── app_ui/
│   └── index.html                # interface web (frontend single-page)
├── config/
│   ├── config.json               # seus perfis e configurações (ignorado pelo git)
│   └── config.exemplo.json       # modelo sem dados pessoais
├── logs/                         # logs diários gerados em tempo de execução (ignorados pelo git)
└── README.md
```

---

## 🚀 Como usar

### Opção 1 — Executável (recomendado)

Baixe o `ReservaRU.exe e dê dois cliques.

- O navegador abre automaticamente em `http://localhost:5757`
- Não precisa de Python, Chrome Driver ou qualquer instalação adicional
- O Chrome deve estar instalado na máquina

### Opção 2 — Direto com Python (para desenvolvimento)

```bash
# Instalar dependências
pip install flask selenium

# Rodar
python app.py
```

O navegador abre automaticamente. Para encerrar, feche a aba do navegador.

---

## 🔨 Como compilar o `.exe`

Requisitos: Python 3.10+ e Google Chrome instalado.

```bash
# Instala as dependências e gera o ReservaRU.exe
python build_exe.py
```

O arquivo `ReservaRU.exe` será gerado na raiz do projeto. As pastas `build/` e `dist/` criadas pelo PyInstaller podem ser apagadas depois.

---

## ⚙️ Configuração de perfis

Na primeira abertura, clique em **"Configurações"** na interface e adicione um perfil com:

| Campo | Descrição |
|---|---|
| Nome | Apelido para identificar o perfil (ex: "Pessoa1", "Pessoa2") |
| E-mail | E-mail institucional UPF (ex: `000000@upf.br`) |
| Senha | Senha do portal UPF — usada apenas se o Forms redirecionar para login |
| Nome completo | Como aparece nos sistemas da UPF |
| Matrícula | Número de matrícula |
| Perfil do público | Ex: "Aluno graduação UPF" |
| Refeição | Almoço, Jantar ou Almoço e jantar |

As configurações ficam salvas em `config/config.json` ao lado do `.exe`.

---

## 📋 Logs

Cada execução gera um arquivo de log diário em `logs/reserva_YYYY-MM-DD.log` com o resultado de cada perfil:

```
2026-04-28 09:18:19 [INFO] [Usuário] Iniciando → data: 28/04/2026 | refeição: Almoço e jantar
2026-04-28 09:18:19 [INFO] [Usuario] Reserva confirmada! Data:28/04/2026 Refeição:Almoço e jantar Horário:09:18:19
```

---

## 🔒 Segurança e privacidade

- O app roda **100% local** — nenhum dado é enviado para servidores externos além do próprio Google Forms da UPF
- O `config/config.json` contém e-mail e senha — está no `.gitignore` e **nunca deve ser commitado**
- O `.exe` para de funcionar automaticamente quando o navegador é fechado (heartbeat de 8 segundos)

---

## 📦 Distribuição

Para compartilhar com outra pessoa, envie apenas o arquivo `ReservaRU.exe`. Ela precisará apenas ter o **Google Chrome instalado**.

---

## 📄 Licença

Uso pessoal e acadêmico. Projeto desenvolvido por estudantes da UPF para uso próprio.
