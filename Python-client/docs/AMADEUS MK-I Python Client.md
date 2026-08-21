# 🤖 AMADEUS MK-I Client 


## Sobre


O Projeto AMADEUS MK-I Client visa desenvolver uma arquitetura de software robusta e modular para habilitar o controle autônomo de um braço robótico. Utilizando uma cadeia de percepção que integra visão computacional (detecção de objetos e mapeamento espacial) com módulos de planejamento e controle de movimento, o sistema é capaz de observar o ambiente, identificar alvos específicos (como parafusos), calcular as trajetórias necessárias, e executar ações complexas. O objetivo final é permitir que o robô execute tarefas de alto nível, como a operação de "pick-and-place" ou classificação automatizada, transformando dados visuais brutos em ações mecânicas precisas através de uma comunicação eficiente com o microcontrolador.


## Estrutura Modular do Sistema


### Pastas


AMADEUS-MK-I-Python-client
├── ai/
│   └── llm_client.py
├── communication/
│   ├── communication_manager.py
│   ├── protocol.py
│   └── serial_client.py
├── config/
│   ├── config.py
│   └── settings.yaml
├── core/
│   └── logger.py
├── docs/
├── logs/
├── models/
│   └── yolo/
├── motion/
│   ├── motion_manager.py
│   ├── kinematics.py
│   ├── planner.py
│   └── controller.py
├── state_machine/
│   └── states.py
├── vision/
│   ├── calibrate_workspace.py
│   ├── calibration.py
│   ├── calibration_data.yaml
│   ├── camera.py
│   ├── camera_calibrator.py
│   ├── detector.py
│   ├── vision_manager.py
│   ├── calibration_images/
│   │   └── ... (images)
│   └── workspace_transform.yaml
├── main.py
├── pyproject.toml
└── uv.lock


### 🚀 **Core & Configuração (Onde o sistema é iniciado e configurado)**

| Arquivo | Descrição Geral | Responsabilidade Primária |
| :--- | :--- | :--- |
| `main.py` | O ponto de entrada principal do cliente Python. Este arquivo é responsável por inicializar todos os módulos (configuração, estado da máquina, comunicação, visão) e iniciar o ciclo de operação principal. | Gerenciar o *lifecycle* do robô, iniciar a Máquina de Estados e orquestrar a execução das tarefas. |
| `config/settings.yaml` | Arquivo de configuração centralizado que armazena parâmetros fixos do sistema. | Armazenar e fornecer configurações globais, como endereços de porta serial, limites de movimento do braço, caminhos de modelos de IA, e parâmetros de calibração. |
| `state\_machine/states.py` | Define o conjunto de estados possíveis que o robô pode assumir (ex: `IDLE`, `DETECTING\_TARGET`, `MOVING\_TO\_OBJECT`, `PICKING`, `DROPPING`). | Implementar a lógica de transição entre estados, garantindo que as ações sejam executadas na ordem correta e que o robô reaja apropriadamente a eventos. |

### 🧠 **Visão Computacional (A Camada de Percepção)**

| Arquivo | Descrição Geral | Responsabilidade Primária |
| :--- | :--- | :--- |
| `vision/camera.py` | Interface de comunicação com o hardware da câmera. Responsável por capturar frames de vídeo. | Fornecer um fluxo de imagem em tempo real (frames) para os módulos de processamento. |
| `vision/detector.py` | Utiliza os modelos de Inteligência Artificial (como o YOLO) para analisar os frames de imagem. | Realizar a localização (bounding box) e a classificação dos objetos na imagem, retornando metadados sobre o alvo. |
| `vision/calibration.py` | Módulo de conversão espacial. Recebe coordenadas de pixels (2D) e as transforma em coordenadas reais no ambiente (3D). | Aplicar transformações geométricas e calibrações (intrínsecas e extrínsecas) para mapear pixels em coordenadas espaciais do mundo real. |
| `models/yolo/` | Diretório que armazena os modelos pré-treinados de Deep Learning (e.g., pesos do YOLO). | Fornecer os modelos de Machine Learning necessários para a função de detecção de objetos. |

### ⚙️ **Comunicação (O Elo entre o Software e o Hardware)**

| Arquivo | Descrição Geral | Responsabilidade Primária |
| :--- | :--- | :--- |
| `communication/protocol.py` | Define a estrutura e o formato dos dados que serão trocados entre o Cliente Python e o Microcontrolador (ex: quais bytes significam "Mover para X, Y, Z" ou "Status OK"). | Padronizar a comunicação. Garantir que o comando enviado seja compreendido exatamente como esperado pelo hardware de baixo nível. |
| `communication/serial\_client.py` | Módulo de baixo nível responsável por gerenciar a conexão física (ex: porta serial, UART). | Estabelecer, manter e gerenciar a leitura e escrita de dados de forma confiável através do protocolo definido. |

### 🤸 **Movimento e Planejamento (A Camada de Ação)**

| Arquivo | Descrição Geral | Responsabilidade Primária |
| :--- | :--- | :--- |
| `motion/kinematics.py` | Contém os modelos matemáticos do braço robótico. | Realizar a **cinemática inversa** (transformar posição desejada [x, y, z] em ângulos das juntas [$\theta_1, \theta_2, ...$]) e a cinemática direta. |
| `motion/planner.py` | Responsável por definir a rota ideal do robô entre o ponto atual e o ponto alvo. | Gerar sequências de pontos de passagem (waypoints) e planejar trajetórias suaves, considerando restrições de espaço e obstáculos. |
| `motion/controller.py` | Gerencia o controle de execução do movimento. Traduz as trajetórias planejadas em comandos de controle contínuos. | Aplicar algoritmos de controle (como PID) para garantir que os servos atinjam os ângulos desejados com precisão, e enviar os comandos finalizados ao `serial\_client`. |

### 🎯 **Tarefas de Aplicação (A Lógica de Negócio de Alto Nível)**

| Arquivo | Descrição Geral | Responsabilidade Primária |
| :--- | :--- | :--- |
| `tasks/pick\_and\_place.py` | Implementa a sequência completa de ações para o cenário de "pegar e colocar" (P&P). | Orquestrar a lógica de alto nível: detectar $\rightarrow$ planejar $\rightarrow$ mover para objeto $\rightarrow$ agarrar $\rightarrow$ mover para destino $\rightarrow$ soltar. |
| `tasks/sorting.py` | Implementa um fluxo de trabalho mais complexo onde o robô deve classificar objetos com base em suas características ou tipo. | Gerenciar a lógica de classificação, definindo destinos apropriados (caixas, esteiras) com base na identificação feita pelo detector de objetos. |


## 🗺️ Roteiro de Desenvolvimento (Sequência Lógica)


### 🟢 Fase 1: Fundação e Comunicação (O Corpo e a Infraestrutura)
*Objetivo: Garantir que o cliente Python consiga "conversar" com o hardware de baixo nível e estabelecer a estrutura do sistema.*

| Tarefa | Arquivos Envolvidos | Descrição | Dependências |
| :--- | :--- | :--- | :--- |
| **1.1. Configuração Inicial** | `config/settings.yaml`, `main.py` | Configurar todos os parâmetros globais do sistema (portas, limites, caminhos de modelos). Criar o esqueleto do `main.py`. | Nenhuma. |
| **1.2. Comunicação Básica** | `communication/protocol.py`, `communication/serial\_client.py` | Definir o protocolo de mensagens mais simples (e.g., "ping", "status") e implementar a camada serial para enviar e receber esses comandos básicos. | 1.1 |
| **1.3. Estrutura de Estados** | `state\_machine/states.py` | Criar a Máquina de Estados (FSM) em um modo simplificado (ex: `INIT` $\rightarrow$ `READY` $\rightarrow$ `IDLE`). Focar apenas no controle de fluxo. | 1.1 |
| **1.4. Interface da Câmera** | `vision/camera.py` | Implementar a interface para capturar frames de vídeo de forma contínua e estável, sem processamento adicional. | 1.1 |

---

### 🟡 Fase 2: Percepção (Os Sentidos)
*Objetivo: Permitir que o robô veja o ambiente e entenda onde estão os objetos em um espaço físico.*

| Tarefa | Arquivos Envolvidos | Descrição | Dependências |
| :--- | :--- | :--- | :--- |
| **2.1. Detecção de Objetos** | `vision/detector.py`, `models/yolo/` | Integrar o modelo YOLO. Desenvolver a lógica para receber um frame da câmera e retornar as coordenadas de *pixels* e o tipo de cada objeto detectado. | 1.4 |
| **2.2. Calibração e Mapeamento** | `vision/calibration.py` | Implementar o algoritmo de calibração. Receber as coordenadas de *pixels* e transformá-las em coordenadas 3D reais do ambiente de trabalho (world coordinates). | 2.1 |
| **2.3. Teste de Percepção** | `main.py` (teste) | Testar o fluxo completo: Câmera $\rightarrow$ Detecção $\rightarrow$ Calibração. O sistema deve ser capaz de informar "Um objeto de tipo X foi encontrado na posição Y, Z". | 2.2 |

---

### 🟠 Fase 3: Cinemática e Movimento (O Corpo Funcional)
*Objetivo: Dar ao robô a capacidade matemática e de controle para saber como se mover.*

| Tarefa | Arquivos Envolvidos | Descrição | Dependências |
| :--- | :--- | :--- | :--- |
| **3.1. Cinemática do Braço** | `motion/kinematics.py` | Implementar os modelos matemáticos do braço: Cinemática Direta (Juntas $\rightarrow$ Posição) e, crucialmente, a **Cinemática Inversa** (Posição $\rightarrow$ Juntas). | 1.1 |
| **3.2. Planejamento de Trajetória** | `motion/planner.py` | Desenvolver o algoritmo de planejamento. Dada uma posição de destino (obtida na Fase 2), gerar uma sequência de *waypoints* seguros para o robô seguir. | 2.2, 3.1 |
| **3.3. Controlador de Movimento** | `motion/controller.py` | Implementar a lógica de controle. Receber a sequência de *waypoints* e calcular os comandos de servo (velocidade, aceleração) para que o braço siga a trajetória com precisão. | 3.1, 3.2 |
| **3.4. Teste de Movimento Isolado** | `communication/serial\_client.py`, `motion/controller.py` | Testar o ciclo: Cliente Python $\rightarrow$ Controller $\rightarrow$ Comandos Serial $\rightarrow$ Microcontrolador $\rightarrow$ Movimento real do braço (sem IA). | 3.3, 1.2 |

---

### 🔴 Fase 4: Integração e Autonomia (O Cérebro)
*Objetivo: Conectar todos os módulos para executar a tarefa de alto nível.*

| Tarefa | Arquivos Envolvidos | Descrição | Dependências |
| :--- | :--- | :--- | :--- |
| **4.1. Implementação da Tarefa P&P** | `tasks/pick\_and\_place.py` | Criar a lógica de execução da tarefa P&P. Este módulo coordena: Detecção (onde está?), Planejamento (qual caminho?), Movimento (mover-se!), e o evento final (pegar/soltar). | 2.3, 3.4 |
| **4.2. Lógica de Captura** | `motion/controller.py`, `tasks/pick\_and\_place.py` | Implementar os movimentos específicos de "grasp" (agarrar) e "release" (soltar), que são movimentos de precisão baseados na posição do objeto. | 4.1 |
| **4.3. Orquestração Principal** | `main.py`, `state\_machine/states.py` | Refinar a Máquina de Estados para ser o maestro. Ela deve receber um evento (ex: "Iniciar P&P") e orquestrar a transição de estado, chamando os módulos de visão, planejamento e movimento na ordem correta. | 4.1, 1.3 |

---

### 🟣 Fase 5: Refinamento e Escala (Polimento)
*Objetivo: Tornar o sistema robusto, eficiente e capaz de lidar com cenários mais complexos.*

| Tarefa | Arquivos Envolvidos | Descrição | Dependências |
| :--- | :--- | :--- | :--- |
| **5.1. Tratamento de Erros** | Todos os módulos | Adicionar mecanismos de *timeout*, *retry* e tratamento de exceções em todos os pontos críticos (ex: falha na comunicação, objeto fora do campo de visão, erro de cinemática). | 4.3 |
| **5.2. Implementação de Sorting** | `tasks/sorting.py` | Estender a lógica de alto nível para lidar com múltiplos alvos e destinos (classificação), utilizando o output de classificação do `detector.py`. | 4.1 |
| **5.3. Otimização e Benchmarking** | Todos os módulos | Otimizar o ciclo de loop (Latência). Medir o tempo desde a detecção até a conclusão da ação para garantir que o sistema seja em tempo real. | 4.3 |

---

## Resumo do Fluxo de Dados

O fluxo de dados deve seguir esta sequência lógica no `main.py` e na FSM:

$$\text{Configuração} \rightarrow \text{Câmera} \xrightarrow{\text{Pixel}} \text{Detector} \xrightarrow{\text{Coordenada 3D}} \text{Planner} \xrightarrow{\text{Waypoints}} \text{Controller} \xrightarrow{\text{Comando Serial}} \text{Servo}$$

---

### Principais Estados de Máquina

| Estado           | Ação principal                             |
|------------------|--------------------------------------------|
| `INIT`           | Carrega config, abre serial, cria objetos. |
| `IDLE`           | Espera gatilho.                            |
| `DETECT_TARGET`  | Detecta objeto e converte coordenadas.     |
| `PICKUP_PREP`    | Planeja rota de captura.                   |
| `PICKUP`         | Executa captura (garra).                   |
| `MOVE_TO_DROP`   | Transporta para zona de descarte.          |
| `DROP`           | Libera objeto.                             |
| `RETURN_HOME`    | Retorna ao ponto inicial.                  |
| `EMERGENCY_STOP` | Interrompe tudo.                           |

---

### Detalhamento dos Estados e Transições:

1. **`INIT` (Inicialização)**:
   * **Ações**: Carrega as dependências do `settings.yaml`, inicializa o log global, faz a busca física e abre a conexão serial, instancia as classes do robô (cinemática, planejador, controlador, câmera e detector).
   * **Transição**: Vai para `IDLE` se tudo inicializar corretamente. Vai para `EMERGENCY_STOP` caso ocorra falha crítica em periféricos de hardware.

2. **`IDLE` (Espera Ativa)**:
   * **Ações**: Garante que o braço esteja posicionado na coordenada padrão de descanso (`home_position`). Aguarda uma ação de gatilho do usuário (por exemplo, pressionar uma tecla no terminal de execução, como `'g'`).
   * **Transição**: Vai para `DETECT_TARGET` após o disparo do gatilho.

3. **`DETECT_TARGET` (Detecção do Alvo)**:
   * **Ações**: Solicita a leitura do último frame válido da câmera, aplica a inferência YOLO, localiza a posição 2D do alvo e converte-a para a coordenada cartesiana real 3D usando as rotinas de calibração do sistema.
   * **Transição**: Se o objeto for identificado com sucesso, armazena a coordenada destino e avança para `PICKUP_PREP`. Se não encontrar objetos por determinado limite de tempo, retorna para `IDLE`.

4. **`PICKUP_PREP` (Preparação de Captura)**:
   * **Ações**: Envia o comando de abertura para o atuador da garra (`GripState.OPEN`). Planeja uma trajetória segura partindo de `home_position` até a projeção vertical do alvo (utilizando um Z de segurança para evitar colisões com objetos próximos no plano de trabalho). Transmite a trajetória e monitora o término do movimento do robô.
   * **Transição**: Avança para `PICKUP` assim que o braço estiver estabilizado na posição projetada.

5. **`PICKUP` (Captura)**:
   * **Ações**: Move o efetuador linearmente para baixo até atingir a altura nominal de pegada do objeto (`pickup_height_mm`). Executa o fechamento completo da garra (`GripState.CLOSE`) e aguarda o tempo de acoplamento físico. Por fim, eleva o braço de volta para a altura segura de transporte (`safe_height_mm`).
   * **Transição**: Avança para `MOVE_TO_DROP`.

6. **`MOVE_TO_DROP` (Deslocamento ao Descarte)**:
   * **Ações**: Recupera a coordenada da zona de descarte cadastrada nas propriedades de tarefas do arquivo de configurações (`tasks.pick_and_place.drop_zone`). Planeja a trajetória de transporte segura entre a coordenada atual e a coordenada acima do ponto de descarte. Executa o movimento coordenado.
   * **Transição**: Assim que atingir a posição e descer até a altura nominal de descarte (`drop_height_mm`), avança para o estado `DROP`.

7. **`DROP` (Descarte)**:
   * **Ações**: Envia o comando serial para abertura da garra (`GripState.OPEN`), liberando o objeto na zona apropriada.
   * **Transição**: Avança para `RETURN_HOME`.

8. **`RETURN_HOME` (Retorno)**:
   * **Ações**: Planeja a trajetória de retorno partindo da zona de descarte de volta para o ponto inicial do sistema (`home_position`). Envia o comando para fechar a garra para mantê-la protegida contra colisões acidentais enquanto o braço estiver em repouso.
   * **Transição**: Retorna ao estado `IDLE` e aguarda novas tarefas.

9. **`EMERGENCY_STOP` (Parada de Emergência)**:
   * **Ações**: Interrompe imediatamente qualquer envio sequencial de comandos de movimento, envia uma mensagem de parada prioritária ao microcontrolador (`ProtocolBuilder.stop()`), desativa as threads em segundo plano e notifica as exceções nos logs do sistema.
