# Documento de Padrões: Inicialização de Módulos de IA - Projeto AMADEUS MK-I Client

**Versão:** 1.0  
**Data:** 29/05/2026  
**Responsável:** Arquitetura de Software  
**Escopo:** Módulos de Listening, Thinking e Speaking

---

## 1. Objetivo
Este documento estabelece o padrão de desenvolvimento, estrutura de arquivos e fluxo de construção para novos módulos de Inteligência Artificial (IA) dentro do ecossistema **AMADEUS MK-I Client**. O objetivo é garantir modularidade, portabilidade e facilidade de manutenção, utilizando **Docker** para isolamento e **Gradio** para a interface de exposição dos serviços.

---

## 2. Estrutura de Pastas Padronizada (Template)

Cada novo módulo (ex: `vision-target`, `audio-listening`, `planner-thinking`) deve seguir rigorosamente a estrutura abaixo:

```text
nome-do-modulo/
├── app.py                 # Servidor Gradio principal
├── entrypoint.sh          # Script de inicialização do container
├── Dockerfile             # Configuração da imagem Docker
├── requirements.txt       # Dependências Python
├── README.md              # Documentação do módulo
├── .dockerignore          # Exclui arquivos desnecessários do build
└── models/                # Pasta local para download de modelos (opcional no container, volume no run)
    └── (arquivos .pth, .pt, .onnx, etc.)
```

---

## 3. Especificações Técnicas dos Arquivos

### 3.1. `app.py` (Interface Gradio)
- **Função:** Expor a API/Interface do módulo.
- **Requisitos:**
  - Deve aceitar argumentos via `launch()` do Gradio.
  - Deve ler variáveis de ambiente para autenticação e compartilhamento.
  - Deve carregar o modelo da variável de volume (`/models`).
- **Exemplo de Lógica:**
```python

import os
import gradio as gr


# Global -------------------------------------------------------------------- #


MODULE_NAME = os.getenv("MODULE_NAME", "Whisper")
GRADIO_PORT = os.getenv("GRADIO_PORT", "7860")
GRADIO_SHARE = os.getenv("GRADIO_SHARE", "0")
GRADIO_USER = os.getenv("GRADIO_USER", "admin")
GRADIO_PASSWORD = os.getenv("GRADIO_PASSWORD", "admin")
MODE_DEV = os.getenv("MODE_DEV", "0")


# Utils --------------------------------------------------------------------- #


# ...


# Functions ----------------------------------------------------------------- #


# ...


# Handlers ------------------------------------------------------------------ #


def welcome(name: str) -> str:
    return f"Welcome to Gradio, {name}!"


# Init ---------------------------------------------------------------------- #


with gr.Blocks() as demo:
    gr.Markdown(
    """
    # Hello World 🚀
    Start typing your name below and press the button to see the output.
    """
    )

    inp = gr.Textbox(label="Name", placeholder="What is your name?")
    out = gr.Textbox(label="Output")
    btn = gr.Button("Click me!")

    #inp.change(fn=welcome, inputs=[inp], outputs=[out], api_name="greet")
    btn.click(fn=welcome, inputs=[inp], outputs=[out], api_name="greet")


if __name__ == "__main__":
    auth = (GRADIO_USER, GRADIO_PASSWORD) if GRADIO_USER and GRADIO_PASSWORD else None

    demo.launch(
        theme=gr.themes.Soft(),
        server_name="0.0.0.0",
        server_port=int(GRADIO_PORT),
        share=bool(int(GRADIO_SHARE)),
        auth=auth,
        auth_message="Insira suas credenciais para obter acesso.",
    )

```

### 3.2. `entrypoint.sh` (Inicializador)
- **Função:** Script executável que configura o ambiente e inicia o servidor.
- **Requisitos:**
  - Deve ter permissão de execução (`chmod +x`).
  - Deve exportar variáveis de ambiente para o processo Python.
  - Deve verificar se os modelos existem antes de iniciar.
- **Exemplo:**
  ```bash
  #!/bin/bash
  set -e
  
  # Configurações de Ambiente
  export MODULE_NAME="${MODULE_NAME:-Whisper}"
  export MODELS_PATH="${MODELS_PATH:-/app/models}"
  export GRADIO_PORT="${GRADIO_PORT:-7860}"
  export GRADIO_SHARE="${GRADIO_SHARE:-0}"
  export GRADIO_USER="${GRADIO_USER:-admin}"
  export GRADIO_PASSWORD="${GRADIO_PASSWORD:-admin}"
  export MODE_DEV="${MODE_DEV:-0}"
  
  # Inicializa o Servidor
  echo "Inicializando módulo: ${MODULE_NAME}"
  python app.py
  ```

### 3.3. `Dockerfile`
- **Imagem Base:** Recomenda-se `python:3.11-slim` ou `python:3.11-alpine` para leveza.
- **Volumes:** Deve criar um diretório para modelos dentro da imagem.
- **Entrada:** Deve apontar para `entrypoint.sh`.

```dockerfile
FROM nvidia/cuda:12.9.2-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema (se necessário, ex: ffmpeg, opencv)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cria venv, ativa via PATH e instala dependências dentro dele
COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Usa o venv por padrão no container
ENV PATH="/opt/venv/bin:$PATH"

# Copia arquivos do projeto
COPY app.py entrypoint.sh .

# Definir entrada
ENTRYPOINT ["/app/entrypoint.sh"]
```

### 3.4. `requirements.txt`
- Liste apenas as bibliotecas necessárias para o módulo (ex: `gradio`, `torch`, `transformers`, `numpy`).
- Evite instalação de bibliotecas de sistema no `Dockerfile` se possível.

---

## 4. Variáveis de Ambiente Obrigatórias

Para garantir a segurança e consistência, as seguintes variáveis devem ser passadas ao container:

| Variável | Descrição | Padrão (Exemplo) |
| :--- | :--- | :--- |
| `PORT` | Porta de exposição do servidor | `7860` |
| `GRADIO_SHARE` | Habilita URL pública (1) ou Local (0) | `0` |
| `GRADIO_USER` | Usuário para autenticação Gradio | `admin` |
| `GRADIO_PASSWORD` | Senha para autenticação Gradio | `admin` |
| `MODE_DEV` | Modo de desenvolvimento (habilita logs, debug) | `0` |
| `MODEL_PATH` | Caminho dentro do container onde os modelos serão carregados | `/models` |

---

## 5. Fluxo de Trabalho (Workflow)

Para adicionar um novo módulo, siga os passos abaixo:

### 5.1. Preparação Local
1.  **Criar Pasta:** `mkdir nome-do-modulo && cd nome-do-modulo`
2.  **Estruturar:** Copiar estrutura de pastas (seção 2).
3.  **Modelos:** Baixar/Clonar o modelo necessário na pasta `models/` localmente.
4.  **Desenvolver:** Criar `app.py` e `entrypoint.sh`.
5.  **Dependências:** Criar `requirements.txt`.

### 5.2. Documentação
1.  Preencher `README.md` com:
    *   Descrição do módulo.
    *   Lista de dependências.
    *   Comandos de Build e Run (PowerShell).
    *   Exemplo de uso.

### 5.3. Build e Teste
1.  **Build:** Compilar a imagem Docker.
2.  **Run:** Executar o container montando o volume de modelos.
3.  **Validar:** Acessar o URL gerado e testar a interface.

---

## 6. Comandos PowerShell (PS)

Os comandos abaixo devem ser incluídos no `README.md` do módulo.

### 6.1. Build da Imagem
```powershell
docker build -t amadeus/mk-i-{NOME_MODULO}:{TAG} .
```
*Exemplo:* `docker build -t amadeus/mk-i-vision:1.0 .`

### 6.2. Execução do Container
```powershell
docker run -d -it `
  --name mk-i-{NOME_MODULO} `
  -p {PORTA}:{PORTA} `
  -v "{CAMPAO_LOCAIS_MODELOS}:{CAMPAO_CONTAINER_MODELOS}" `
  -e GRADIO_SHARE={SHARE} `
  -e GRADIO_USER={USER} `
  -e GRADIO_PASSWORD={PASSWORD} `
  -e MODE_DEV={DEV} `
  amadeus/mk-i-{NOME_MODULO}:{TAG}
```
*Exemplo:*
```powershell
docker run -d -it `
  --name mk-i-vision `
  -p 7861:7860 `
  -v "D:/Artificial-intelligence/Whisper/models:/app/models" `
  -e GRADIO_SHARE=0 `
  -e GRADIO_USER=admin `
  -e GRADIO_PASSWORD=admin `
  -e MODE_DEV=0 `
  amadeus/mk-i-vision:1.0
```

### 6.3. Verificação (Opcional)
```powershell
docker logs mk-i-{NOME_MODULO}
```

---

## 7. Exemplo Prático: Módulo "Vision-Target"

Abaixo, um esboço do `README.md` que deve ser seguido para o primeiro módulo.

```markdown
# Módulo Vision-Target (Thinking/Perception)

Este módulo é responsável pela detecção de alvos (parafusos, peças) utilizando Visão Computacional.

## Requisitos

- Docker instalado.
- Python (para desenvolvimento local).

## Estrutura de Pastas

vision-target/
├── app.py
├── entrypoint.sh
├── Dockerfile
├── requirements.txt
├── models/
│   └── yolov8.pt
└── README.md

## Instruções

### 1. Preparação de Modelos

Baixe o modelo YOLOv8 na pasta local models/ antes de rodar o container.

### 2. Build

Execute o comando na raiz do módulo:

docker build -t amadeus/mk-i-vision:1.0 .

### 3. Execução

Execute o container. Certifique-se de que a pasta de modelos local seja montada corretamente.

docker run -d -it ` 
  --name mk-i-vision `
  -p 7861:7860 `
  -v "C:/Users/Usuario/Projetos/amadeus/models:/app/models" `
  -e GRADIO_SHARE=0 `
  -e GRADIO_USER=admin `
  -e GRADIO_PASSWORD=admin `
  -e MODE_DEV=0 `
  amadeus/mk-i-vision:1.0

### 4. Acesso
Abra o navegador e acesse: `http://localhost:7861`
```

---

## 8. Checklist de Validação

Antes de integrar o módulo ao sistema principal, verifique:

- [ ] `app.py` inicia sem erros (`python app.py`).
- [ ] `entrypoint.sh` é executável.
- [ ] `Dockerfile` constrói sem erros.
- [ ] Volume de modelos está montado corretamente (o container vê os modelos).
- [ ] Autenticação Gradio funciona (se share=0).
- [ ] URL de acesso é gerada corretamente (se share=1).
- [ ] Logs do container não apresentam erros de importação.

---

**Nota:** Este padrão deve ser seguido para todos os módulos de IA para garantir que a comunicação com o `AMADEUS MK-I Python Client` central seja padronizada e escalável.
