# Interfaces de Classes do Projeto

Este documento detalha as interfaces públicas das classes, conforme implementadas no projeto.

***

## 🔧 `GradioClient.py`

Gerencia a comunicação com servidores Gradio para inferências multimodais. O cliente encapsula a configuração do servidor, valida arquivos, envia prompts e trata a resposta estruturada.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `ChatMessage` | `dataclass` | Representação simples de uma mensagem de chat (`role`, `content`). |
| `GradioConfig` | `dataclass` | Configuração do servidor Gradio (`server_url`, `username`, `password`, `timeout`). |
| `InferenceRequest` | `dataclass` | Payload da inferência (`prompt`, `image_path`, `audio_path`, `video_path`). |
| `InferenceResponse` | `dataclass` | Resposta estruturada da inferência (`text`, `history`, `raw_response`). |

### 📁 **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `GradioConfig` | `dataclass` | Carrega parâmetros de conexão ao servidor Gradio. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `GradioClientError` | `Exception` | Base de exceções do cliente. |
| `GradioConnectionError` | `GradioClientError` | Erro quando não é possível conectar ao servidor. |
| `GradioInferenceError` | `GradioClientError` | Erro quando a inferência falha (formato inesperado, etc.). |

### 🔧 **Main Class (`GradioVisionClient`)**

#### **Construtor (`__init__`)**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `config` | `GradioConfig` | *(Obrigatório)* | Configuração do servidor Gradio. |

#### **Propriedades Públicas**

| Propriedade | Tipo | Descrição |
| :--- | :--- | :--- |
| `history` | `list[dict[str, Any]]` | Cópia do histórico interno de mensagens. |

#### **Métodos Públicos**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `clear_history` | `() -> None` | Reseta o histórico interno. |
| `health_check` | `() -> bool` | Verifica disponibilidade do servidor. |
| `send_inference` | `(request: InferenceRequest) -> InferenceResponse` | Envia uma inferência multimodal e retorna a resposta estruturada. |

***

## 🔧 `Communication_manager.py`

Gerencia o ciclo de vida da conexão serial, deteção automática do port e encaminhamento de feedbacks recebidos do Arduino.

---

### 📁 **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `SerialConfig` | `dataclass` | Carrega parâmetros de comunicação (enabled, port, baudrate, timeout_seconds, reconnection_attempts, reconnect_interval_seconds). |

---

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `SerialConfig` | `dataclass` | Configurações de conexão serial. |
| `ArduinoFeedback` | `dataclass` | Estrutura que representa um feedback enviado pelo Arduino (ex.: status, valores de sensores, etc.). |

---

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `detect_arduino_port` | `(timeout: Optional[int] = None) -> Optional[str]` | Escaneia portas serial para dispositivos compatíveis. Retorna o nome da porta ou `None`. |
| `parse_arduino_message` | `(raw_message: str) -> Optional[ArduinoFeedback]` | Converte a string crua recebida do Arduino em um objeto `ArduinoFeedback`. Retorna `None` caso a mensagem não possa ser analisada. |

---

### 🔧 **Main Class (`CommunicationManager`)**

#### **Construtor (`__init__`)**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `config` | `SerialConfig` | *(Obrigatório)* | Instância contendo os parâmetros de comunicação serial. |

#### **Métodos Públicos**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `initialize` | `() -> bool` | Determina a porta serial (automaticamente ou via configuração) e cria o `SerialClient`. Retorna `True` se inicializado, `False` caso contrário. |
| `connect_with_retry` | `() -> bool` | Tenta conectar ao dispositivo serial, realizando repetições conforme `config.reconnection_attempts`. Retorna `True` se a conexão foi estabelecida, `False` caso contrário. |
| `register_feedback_listener` | `(listener: Callable[[ArduinoFeedback], None]) -> None` | Inscreve uma função callback que será chamada sempre que um `ArduinoFeedback` for recebido. |
| `send_message` | `(serialized_message: str) -> None` | Envia a mensagem serializada ao Arduino, se o cliente estiver ativo. |
| `disconnect` | `() -> None` | Fecha a conexão serial de forma segura e libera recursos. |

***

## 🔧 `Protocol.py`

Gerencia a construção e serialização de mensagens de protocolo de controle de servos e manipuladores.  
As mensagens são formadas a partir de comandos e argumentos, terminadas pelo caractere `;`.  
O módulo fornece validações auxiliares, enums para estados e categorias de comando, e uma classe builder para criar mensagens pré‑formatadas de forma segura.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `ProtocolMessage` | `dataclass` | Representa uma mensagem de protocolo contendo o nome do comando (`command`) e um dicionário de argumentos (`arguments`). Inclui o método `serialize()` que devolve a string formatada do protocolo. |

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `validate_servo` | `(servo: int) -> None` | Valida que o identificador do servo seja ≥ 0. |
| `validate_position` | `(position: int) -> None` | Valida que a posição do servo esteja entre 0 e 180. |
| `validate_speed` | `(min_speed: int, max_speed: int) -> None` | Valida que os valores de velocidade sejam positivos e que `min_speed ≤ max_speed`. |
| `validate_argument_key` | `(key: str) -> None` | Valida que a chave de argumento esteja em maiúsculas. |

### 🔧 **Main Class (`ProtocolBuilder`)**

A classe `ProtocolBuilder` oferece métodos estáticos para criar mensagens de protocolo pre‑definidas, garantindo a validação de parâmetros e a correta formatação.

#### **Métodos Públicos (estáticos)**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `move_to` | `(servo: int, position: int) -> ProtocolMessage` | Constrói comando `MOVE_TO` com os parâmetros de servo e posição. |
| `grip` | `(state: GripState) -> ProtocolMessage` | Constrói comando `GRIP` com o estado de agarramento (`OPEN` ou `CLOSE`). |
| `reset` | `() -> ProtocolMessage` | Constrói comando `RESET` sem argumentos. |
| `speed` | `(min_speed: int, max_speed: int) -> ProtocolMessage` | Constrói comando `SPEED` com os limites mínimo e máximo de velocidade. |
| `stop` | `() -> ProtocolMessage` | Constrói comando `STOP` (emergência). |
| `showcase` | `(mode: ShowcaseMode) -> ProtocolMessage` | Constrói comando `SHOWCASE` com o modo de exibição (`START` ou `STOP`). |

***

## 🔧 `SerialClient.py`

Gerencia a conexão serial com dispositivos embarcados (ex.: Arduino) permitindo envio de comandos e recepção de feedback em tempo real por meio de callbacks registrados.

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `detect_arduino_port` | `() -> Optional[str]` | Scans available serial ports for devices matching **"arduino"**, **"ch340"** or **"usb serial"**. Returns the device path if found, otherwise `None`. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| *Nenhum* | | |

### 🔧 **Main Class (`SerialClient`)**

#### Construtor (`__init__`)

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `port` | `str` | *(Obrigatório)* | Serial device path (e.g., `"COM3"` or `"/dev/ttyUSB0"`). |
| `baudrate` | `int` | `9600` | Baud rate for serial communication. |
| `timeout` | `float` | `1.0` | Read timeout in seconds. |

#### Propriedades Públicas

| Propriedade | Tipo | Descrição |
| :--- | :--- | :--- |
| `port` | `str` | Serial device path. |
| `baudrate` | `int` | Baud rate. |
| `timeout` | `float` | Read timeout. |
| `serial_connection` | `serial.Serial | None` | Underlying `serial.Serial` instance or `None` if not connected. |
| `running` | `bool` | Indicates if the listener thread is active. |
| `listener_thread` | `threading.Thread | None` | Thread object handling incoming messages. |

#### Métodos Públicos

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `register_callback` | `(callback: Callable[[str], None]) -> None` | Registers a callback function to process incoming serial messages. |
| `connect` | `() -> None` | Opens the serial connection and starts the listener thread. |
| `listen` | `() -> None` | Runs in the background thread; continuously reads from the serial port and triggers registered callbacks. |
| `send` | `(message: str) -> None` | Sends a string message to the micro‑controller. |
| `disconnect` | `() -> None` | Stops listening and closes the serial connection safely. |

***

## 🔧 `Config.py`

Centraliza as configurações do sistema, agrupando parâmetros relacionados à comunicação serial, visão computacional, movimento do robô, tarefas de pick-and-place e componentes de IA. Permite construir objetos de configuração fortemente tipados a partir de dicionários de configuração.

### 📦 **Dataclasses**

| Dataclass        | Tipo        | Descrição                                                                               |
| :--------------- | :---------- | :-------------------------------------------------------------------------------------- |
| `SerialConfig`   | `dataclass` | Armazena parâmetros de comunicação serial e reconexão.                                  |
| `CameraConfig`   | `dataclass` | Contém parâmetros de captura da câmera.                                                 |
| `DetectorConfig` | `dataclass` | Armazena parâmetros do detector de objetos e do modelo utilizado.                       |
| `ToolConfig`     | `dataclass` | Define os offsets físicos da ferramenta em relação ao efetuador final.                  |
| `VisionConfig`   | `dataclass` | Agrupa todas as configurações relacionadas ao sistema de visão.                         |
| `MotionConfig`   | `dataclass` | Agrupa configurações de cinemática, calibração, planejamento e controle do manipulador. |
| `TaskConfig`     | `dataclass` | Contém parâmetros espaciais utilizados em operações de pick-and-place.                  |
| `VLMConfig`      | `dataclass` | Configuração de acesso ao servidor do Vision Language Model (VLM).                      |
| `TTSConfig`      | `dataclass` | Configuração de acesso ao serviço de Text-to-Speech (TTS).                              |
| `STTConfig`      | `dataclass` | Configuração de acesso ao serviço de Speech-to-Text (STT).                              |
| `AgentConfig`    | `dataclass` | Configuração de agentes inteligentes e seus critérios de decisão.                       |
| `AIConfig`       | `dataclass` | Agrupa todas as configurações relacionadas aos serviços de IA.                          |

---

### 📁 **ConfigClasses**

### 🔧 `SerialConfig`

**Propriedades Públicas:**

| Propriedade                  | Tipo            | Descrição                                       |
| :--------------------------- | :-------------- | :---------------------------------------------- |
| `enabled`                    | `bool`          | Indica se a comunicação serial está habilitada. |
| `port`                       | `Optional[str]` | Porta serial utilizada para conexão.            |
| `baudrate`                   | `int`           | Taxa de transmissão da comunicação serial.      |
| `timeout_seconds`            | `float`         | Tempo máximo de espera por resposta.            |
| `reconnection_attempts`      | `int`           | Número máximo de tentativas de reconexão.       |
| `reconnect_interval_seconds` | `float`         | Intervalo entre tentativas de reconexão.        |

**Métodos Públicos:**

| Método      | Assinatura                     | Descrição                                                       |
| :---------- | :----------------------------- | :-------------------------------------------------------------- |
| `from_dict` | `(data: dict) -> SerialConfig` | Cria uma instância de `SerialConfig` a partir de um dicionário. |

---

### 🔧 `CameraConfig`

**Propriedades Públicas:**

| Propriedade    | Tipo              | Descrição                                |
| :------------- | :---------------- | :--------------------------------------- |
| `device_index` | `Union[int, str]` | Identificador do dispositivo de captura. |
| `frame_width`  | `int`             | Largura dos frames capturados.           |
| `frame_height` | `int`             | Altura dos frames capturados.            |
| `fps`          | `int`             | Taxa de quadros por segundo.             |

**Métodos Públicos:**

| Método      | Assinatura                     | Descrição                                                       |
| :---------- | :----------------------------- | :-------------------------------------------------------------- |
| `from_dict` | `(data: dict) -> CameraConfig` | Cria uma instância de `CameraConfig` a partir de um dicionário. |

---

### 🔧 `DetectorConfig`

**Propriedades Públicas:**

| Propriedade            | Tipo        | Descrição                                                  |
| :--------------------- | :---------- | :--------------------------------------------------------- |
| `confidence_threshold` | `float`     | Limiar mínimo de confiança das detecções.                  |
| `iou_threshold`        | `float`     | Limiar de Intersection over Union utilizado pelo detector. |
| `target_labels`        | `List[str]` | Lista de classes alvo monitoradas.                         |
| `model_path`           | `str`       | Caminho para o modelo de detecção.                         |

**Métodos Públicos:**

| Método      | Assinatura                                                  | Descrição                                                               |
| :---------- | :---------------------------------------------------------- | :---------------------------------------------------------------------- |
| `from_dict` | `(detector_data: dict, model_data: dict) -> DetectorConfig` | Constrói a configuração do detector a partir dos parâmetros informados. |

---

### 🔧 `ToolConfig`

**Propriedades Públicas:**

| Propriedade   | Tipo    | Descrição                       |
| :------------ | :------ | :------------------------------ |
| `offset_x_mm` | `float` | Offset da ferramenta no eixo X. |
| `offset_y_mm` | `float` | Offset da ferramenta no eixo Y. |
| `offset_z_mm` | `float` | Offset da ferramenta no eixo Z. |

**Métodos Públicos:**

| Método      | Assinatura                   | Descrição                                                     |
| :---------- | :--------------------------- | :------------------------------------------------------------ |
| `from_dict` | `(data: dict) -> ToolConfig` | Cria uma instância de `ToolConfig` a partir de um dicionário. |

---

### 🔧 `VisionConfig`

**Propriedades Públicas:**

| Propriedade             | Tipo                  | Descrição                                                  |
| :---------------------- | :-------------------- | :--------------------------------------------------------- |
| `camera`                | `CameraConfig`        | Configuração da câmera.                                    |
| `detector`              | `DetectorConfig`      | Configuração do detector de objetos.                       |
| `vlm`                   | `Optional[VLMConfig]` | Configuração opcional do serviço VLM.                      |
| `calibration_file_path` | `str`                 | Caminho do arquivo de calibração.                          |
| `transform_file_path`   | `str`                 | Caminho do arquivo de transformação espacial.              |
| `live_detection_window` | `bool`                | Indica se a janela de detecção em tempo real será exibida. |
| `tool`                  | `ToolConfig`          | Configuração dos offsets da ferramenta.                    |

**Métodos Públicos:**

| Método      | Assinatura                                                      | Descrição                                               |
| :---------- | :-------------------------------------------------------------- | :------------------------------------------------------ |
| `from_dict` | `(data: dict, vlm: Optional[VLMConfig] = None) -> VisionConfig` | Constrói uma configuração completa do sistema de visão. |

---

### 🔧 `MotionConfig`

**Propriedades Públicas:**

| Propriedade   | Tipo               | Descrição                                           |
| :------------ | :----------------- | :-------------------------------------------------- |
| `kinematics`  | `ArmConfiguration` | Configuração física e cinemática do braço robótico. |
| `calibration` | `JointCalibration` | Parâmetros de calibração das juntas.                |
| `planner`     | `PlannerConfig`    | Configuração do planejador de trajetórias.          |
| `controller`  | `ControllerConfig` | Configuração do controlador de movimento.           |

**Métodos Públicos:**

| Método      | Assinatura                     | Descrição                                                             |
| :---------- | :----------------------------- | :-------------------------------------------------------------------- |
| `from_dict` | `(data: dict) -> MotionConfig` | Constrói todas as configurações relacionadas ao sistema de movimento. |

---

### 🔧 `TaskConfig`

**Propriedades Públicas:**

| Propriedade        | Tipo             | Descrição                                             |
| :----------------- | :--------------- | :---------------------------------------------------- |
| `pickup_height_mm` | `float`          | Altura utilizada para captura do objeto.              |
| `safe_height_mm`   | `float`          | Altura segura para deslocamentos.                     |
| `drop_height_mm`   | `float`          | Altura utilizada para liberação do objeto.            |
| `drop_zone`        | `CartesianPoint` | Coordenada de destino para descarte ou armazenamento. |

**Métodos Públicos:**

| Método      | Assinatura                   | Descrição                                          |
| :---------- | :--------------------------- | :------------------------------------------------- |
| `from_dict` | `(data: dict) -> TaskConfig` | Cria uma configuração de tarefa de pick-and-place. |

---

### 🔧 `VLMConfig`

**Propriedades Públicas:**

| Propriedade  | Tipo    | Descrição                                 |
| :----------- | :------ | :---------------------------------------- |
| `server_url` | `str`   | Endereço do servidor VLM.                 |
| `username`   | `str`   | Usuário de autenticação.                  |
| `password`   | `str`   | Senha de autenticação.                    |
| `model_name` | `str`   | Nome do modelo utilizado.                 |
| `timeout`    | `float` | Tempo máximo de espera pelas requisições. |

**Métodos Públicos:**

| Método      | Assinatura                  | Descrição                                            |
| :---------- | :-------------------------- | :--------------------------------------------------- |
| `from_dict` | `(data: dict) -> VLMConfig` | Cria uma configuração VLM a partir de um dicionário. |

---

### 🔧 `TTSConfig`

**Propriedades Públicas:**

| Propriedade  | Tipo  | Descrição                 |
| :----------- | :---- | :------------------------ |
| `server_url` | `str` | Endereço do servidor TTS. |
| `username`   | `str` | Usuário de autenticação.  |
| `password`   | `str` | Senha de autenticação.    |

**Métodos Públicos:**

| Método      | Assinatura                  | Descrição                                            |
| :---------- | :-------------------------- | :--------------------------------------------------- |
| `from_dict` | `(data: dict) -> TTSConfig` | Cria uma configuração TTS a partir de um dicionário. |

---

### 🔧 `STTConfig`

**Propriedades Públicas:**

| Propriedade  | Tipo  | Descrição                 |
| :----------- | :---- | :------------------------ |
| `server_url` | `str` | Endereço do servidor STT. |
| `username`   | `str` | Usuário de autenticação.  |
| `password`   | `str` | Senha de autenticação.    |

**Métodos Públicos:**

| Método      | Assinatura                  | Descrição                                            |
| :---------- | :-------------------------- | :--------------------------------------------------- |
| `from_dict` | `(data: dict) -> STTConfig` | Cria uma configuração STT a partir de um dicionário. |

---

### 🔧 `AgentConfig`

**Propriedades Públicas:**

| Propriedade            | Tipo    | Descrição                                           |
| :--------------------- | :------ | :-------------------------------------------------- |
| `confidence_threshold` | `float` | Limiar mínimo de confiança para decisões do agente. |
| `max_retries`          | `int`   | Número máximo de tentativas permitidas.             |

**Métodos Públicos:**

| Método      | Assinatura                    | Descrição                                                  |
| :---------- | :---------------------------- | :--------------------------------------------------------- |
| `from_dict` | `(data: dict) -> AgentConfig` | Cria uma configuração de agente a partir de um dicionário. |

---

### 🔧 `AIConfig`

**Propriedades Públicas:**

| Propriedade | Tipo          | Descrição                              |
| :---------- | :------------ | :------------------------------------- |
| `vlm`       | `VLMConfig`   | Configuração do serviço VLM.           |
| `tts`       | `TTSConfig`   | Configuração do serviço TTS.           |
| `stt`       | `STTConfig`   | Configuração do serviço STT.           |
| `agents`    | `AgentConfig` | Configuração dos agentes inteligentes. |

**Métodos Públicos:**

| Método      | Assinatura                 | Descrição                                              |
| :---------- | :------------------------- | :----------------------------------------------------- |
| `from_dict` | `(data: dict) -> AIConfig` | Constrói uma configuração completa dos serviços de IA. |

***

## 🔧 `Logger.py`

Gerencia a configuração global de logging da aplicação.

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `setup_logging` | `(level: str = "INFO") -> None` | Configura o logger global, definindo nível, formatter, console e rotativo file handlers. |

***

## 🔧 `Controller.py`

Gerencia a execução de trajetórias para braços robóticos, traduzindo coordenadas cartesianas em comandos de servo e lidando com feedback do hardware para garantir segurança e sincronização.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `ControllerConfig` | `dataclass` | Configurações de limites de velocidade, mapeamento de servos e tempos de espera. |
| `ArduinoFeedback` | `dataclass` | Estrutura contendo dados analisados de mensagens serializadas enviadas pelo Arduino (tipo, comando, status, mensagem bruta). |

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `angle_to_servo_position` | `(angle_degrees: float, range_limits: tuple = (0, 180)) -> int` | Converte ângulo de junta (graus) para passo inteiro de servo, aplicando limite seguro. |
| `extract_angles` | `(motor_angles: MotorAngles) -> List[float]` | Extrai de forma segura os ângulos de junta de um objeto `MotorAngles`, com suporte a versões anteriores e fallback genérico. |
| `serialize_protocol_message` | `(message: Any) -> str` | Serializa objetos de protocolo para sua forma bruta de string; usa `message.serialize()` se disponível. |
| `parse_arduino_message` | `(msg: str) -> Optional[ArduinoFeedback]` | Analisa a string de feedback do Arduino e devolve `ArduinoFeedback`, ou `None` se o formato não corresponder. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `MotionControlError` | `Exception` | Erros genéricos ocorridos durante a execução de comandos de movimento. |

### 🔧 **Main Class (`MotionController`)**

**Construtor (`__init__`):**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `kinematics` | `RoboticArmKinematics` | *(Obrigatório)* | Motor de cálculo de kinematics. |
| `serial_client` | `SerialClient` | *(Obrigatório)* | Interface de comunicação serial. |
| `config` | `ControllerConfig` | *(Obrigatório)* | Configurações de hardware e timing. |

**Métodos Públicos:**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `configure_system_limits` | `() -> None` | Envia limites de velocidade mínima e máxima ao microcontrolador usando `ProtocolBuilder.speed`. |
| `execute_trajectory` | `(waypoints: List[CartesianPoint]) -> None` | Executa sequencialmente os pontos cartesianos da trajetória, convertendo cada ponto em ângulos de junta e enviando comandos de servo sincronizados. |
| `control_gripper` | `(state: GripState) -> None` | Envia comando de estado (abrir/fechar) para o gripper e aguarda confirmação. |
| `emergency_stop` | `() -> None` | Interrompe imediatamente a execução, enviando comando de parada e sinalizando finalização de qualquer operação em curso. |

***

## 🔧 `Kinematics.py`

Responsável por calcular os ângulos dos servomotores para um braço robótico com base rotativa e dois graus de liberdade planários.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `JointCalibration` | `dataclass` | Parâmetros de calibração dos três atuadores. |
| `ArmConfiguration` | `dataclass` | Configuração física e de limites do braço. |
| `MotorAngles` | `dataclass` | Ângulos calculados para cada servo (`base`, `shoulder`, `elbow`). |

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `clamp` | `(value: float, minimum: float, maximum: float) -> float` | Limita um valor numérico ao intervalo \([minimum, maximum]\). |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `InverseKinematicsError` | `Exception` | Erro lançado quando o ponto alvo está fora dos limites físicos. |

### 🔧 **Main Class (`RoboticArmKinematics`)**

**Construtor (`__init__`):**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `configuration` | `ArmConfiguration` | *(Obrigatório)* | Configuração física e de limites do braço robótico. |

**Métodos Públicos:**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `calculate` | `(x: float, y: float, z: float) -> MotorAngles` | Calcula os ângulos de servo para a coordenada cartesiana \((x, y, z)\) dentro das restrições de alcance e de limites de servo. |

***

## 🔧 `motion_manager.py`

Gerencia a planificação, coordenação e execução física de trajetórias de braços robóticos.  
A classe `MotionManager` funciona como orquestrador que interage com kinemática, planejamento de trajetória e controle de motor, além de comunicar com hardware via serial.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `MotionConfig` | `dataclass` | Contém parâmetros de configuração globais do braço, kinematics, planner e controller. |
| `CartesianPoint` | `dataclass` | Representa posição cartesiana (x, y, z, [outras dimensões]) utilizada em planejamento e controle. |
| `GripState` | `enum` | Enum que descreve os estados de grampo (`OPEN`, `CLOSE`, `HALF` etc). |

### 📁 **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `MotionConfig` | `dataclass` | Carrega e guarda configurações de kinemática, planner e controller a partir de arquivos de configuração. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `MotionControlError` | `Exception` | Erro genérico do controller de movimento (motor, grampo, serial, etc). |
| `TrajectoryPlanningError` | `Exception` | Erro na geração de trajeto, colisões ou parâmetros inválidos. |

### 🔧 **Main Class (`MotionManager`)**

**Construtor (`__init__`):**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `config` | `MotionConfig` | *(Obrigatório)* | Configuração global do braço. |

**Métodos Públicos:**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `initialize` | `(serial_client: SerialClient) -> bool` | Instancia kinematics, planner e controller, verificando que as configurações necessárias estão presentes. Retorna `True` se sucesso, `False` caso contrário. |
| `setup_hardware_limits` | `() -> None` | Envia os limites de velocidade mínima/ máxima para o dispositivo de controle. |
| `get_home_position` | `() -> CartesianPoint` | Retorna a posição cartesiana configurada como *home* no planner. |
| `execute_move` | `(start: CartesianPoint, target: CartesianPoint) -> bool` | Planeja e executa trajetória livre de colisão entre `start` e `target`. Retorna `True` se a execução for bem-sucedida, `False` em caso de erro. |
| `execute_pose` | `(target: CartesianPoint) -> bool` | Executa pose cartesiano direto (sem exigir posição corrente). Retorna `True` se bem-sucedida. |
| `get_current_position` | `() -> Optional[CartesianPoint]` | Retorna a última posição executada, ou `None` se ainda não houver nenhuma. |
| `set_gripper_state` | `(state: GripState) -> bool` | Envia comando de abertura/fechamento de grampo. Retorna `True` se bem-sucedido. |
| `trigger_emergency_stop` | `() -> None` | Dispara comando de parada de emergência imediatamente no hardware. |

***

## 🔧 `Planner.py`

Gere trajetórias seguras para braços robóticos, convertendo posições iniciais em pontos intermediários alcançáveis. O módulo emprega validações de cinemática inversa e remove redundâncias de waypoints.

### 📦 **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `calculate_euclidean_distance` | `(point_a: CartesianPoint, point_b: CartesianPoint) -> float` | Calcula a distância Euclidiana entre dois pontos cartesianos em 3D. |
| `remove_consecutive_duplicates` | `(points: List[CartesianPoint]) -> List[CartesianPoint]` | Elimina coordenadas consecutivas idênticas, evitando movimentos redundantes do braço. |

### 📁 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `CartesianPoint` | `dataclass` | Representa um ponto cartesiano (x, y, z). |
| `PlannerConfig` | `dataclass` | Configurações da planificadora (posição inicial e z seguro). |

### ⚙ **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `PlannerConfig` | `dataclass` | Contém `home_position: CartesianPoint` e `safe_z_coordinate: Optional[float]`. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `TrajectoryPlanningError` | `Exception` | Erro genérico de planejamento de trajetória (ex.: ponto fora de alcance). |

### 🔧 **Main Class (`TrajectoryPlanner`)**

**Construtor (`__init__`):**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `kinematics` | `RoboticArmKinematics` | *(Obrigatório)* | Motor de cinemática inversa usado para validar alcance. |
| `config` | `PlannerConfig` | *(Obrigatório)* | Configuração inicial contendo posição de home e restrições de z. |

**Métodos Públicos:**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `plan_trajectory` | `(start: CartesianPoint, target: CartesianPoint) -> List[CartesianPoint]` | Gera uma lista de waypoints cartesianos, no formato *start → home → target*, filtra duplicados consecutivos e valida que todos os waypoints são alcançáveis. |
| | | :raises `TrajectoryPlanningError`: Se algum waypoint estiver fora do alcance físico. | |

***

## 🔧 `robot_state_machine.py`

Gerencia o fluxo de execução de um braço robótico de pick‑and‑place, controlando estados de inicialização, detecção, captura, transporte e liberação de objetos, além de lidar com emergências e retorno à posição inicial.

### 📦 **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `TaskConfig` | `dataclass` | Armazena parâmetros de operação (altura de captura, altura segura, zona de drop, etc.). É carregado de arquivo YAML por `TaskConfig.load_yaml`. |

### 🔧 **Main Class (`StateMachine`)**

**Construtor (`__init__`)**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `context` | `RobotContext` | *(Obrigatório)* | Instância contendo subsistemas e coordenadas de estado. |
| `initial_state` | `str` | *(Obrigatório)* | Nome da chave do estado inicial (ex.: `"IDLE"`). |

**Propriedades Públicas**

| Propriedade | Tipo | Descrição |
| :--- | :--- | :--- |
| `context` | `RobotContext` | Referência ao objeto `RobotContext` que fornece comunicação, visão, e motion. |

**Métodos Públicos**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `register_state` | `(name: str, state: State) -> None` | Mapeia um `State` concreto à chave de transição. |
| `start` | `() -> None` | Inicia a máquina, chamando `on_enter` do estado inicial. |
| `update` | `() -> None` | Executa o ciclo atual do estado ativo e, se necessário, transita para outro estado. |
| `transition_to` | `(next_state_name: str) -> None` | Sai do estado atual (`on_exit`) e entra no próximo (`on_enter`). Lida com erros e transita para `"EMERGENCY_STOP"` se o próximo estado não existir. |

---

## 🔧 **RobotContext**

Armazena referências a subsistemas e coordenadas de posição utilizadas pelos estados.

| Atributo | Tipo | Descrição |
| :--- | :--- | :--- |
| `comm` | `Any` | Gerenciador de comunicação (ex.: serial, TCP). |
| `vision` | `Any` | Gerenciador de visão (câmera, processamento). |
| `motion` | `Any` | Gerenciador de movimento (controlador do braço). |
| `task_config` | `TaskConfig` | Configuração de tarefa. |
| `current_position` | `CartesianPoint` | Posição atual do braço. |
| `target_position` | `Optional[CartesianPoint]` | Posição alvo a ser alcançada (apenas após detecção). |
| `trigger_received` | `bool` | Indica que o acionamento externo foi recebido. |
| `state_machine` | `Optional[StateMachine]` | Referência à máquina de estados (preenchida pelo `StateMachine.__init__`). |

***

## 🔧 `Calibration.py`

Gerencia o processo de calibração de câmera e transformação de coordenadas espaciais. Converte coordenadas de pixels da imagem para coordenadas do mundo real utilizando parâmetros intrínsecos e extrínsecos da câmera.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `CameraIntrinsics` | `dataclass` | Contém a matriz de calibração e os coeficientes de distorção. |
| `CameraExtrinsics` | `dataclass` | Contém a matriz de rotação e o vetor de translação. |
| `WorldCoordinate` | `dataclass` | Representa coordenadas (x, y, z) do mundo. |

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `configure_logging` | `(level: int = logging.INFO) -> None` | Configura o log global do módulo. |
| `load_yaml_file` | `(file_path: Path) -> Dict[str, Any]` | Carrega e parseia um arquivo YAML de configuração. |
| `validate_matrix_shape` | `(matrix: np.ndarray, expected_shape: Tuple[int, int], matrix_name: str) -> None` | Valida dimensões de matrizes. |

### 🔧 **Main Class (`CalibrationEngine`)**

**Construtor (`__init__`)**

| Parâmetro | Tipo | Descrição |
| :--- | :--- | :--- |
| `intrinsics` | `CameraIntrinsics` | Parâmetros intrínsecos da câmera. |
| `extrinsics` | `CameraExtrinsics` | Parâmetros extrínsecos da câmera. |

**Métodos Públicos**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `from_yaml` | `(calibration_file: Path) -> CalibrationEngine` | Cria uma instância de `CalibrationEngine` carregando os dados de calibração a partir de um arquivo YAML. |
| `undistort_pixel` | `(pixel_x: float, pixel_y: float) -> Tuple[float, float]` | Remove a distorção da lente de uma coordenada de pixel da imagem. Retorna as coordenadas corrigidas (x, y). |
| `pixel_to_world` | `(pixel_x: float, pixel_y: float, plane_z: float = 0.0) -> WorldCoordinate` | Converte coordenadas de pixels da imagem para coordenadas do mundo real, assumindo que o objeto está em um plano Z conhecido. Retorna um objeto `WorldCoordinate` com x, y e z. |


***

## 🔧 `Camera.py`

Gerencia a captura contínua de frames de uma fonte de câmera, com suporte a reconexões automáticas e captura em segundo plano.

### 📦 **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `validate_camera_source` | `(source: int | str) -> int | str` | Valida e normaliza a fonte da câmera, aceitando índices numéricos (≥ 0) ou strings não vazias que representam caminhos de arquivo ou URL. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `CameraError` | `Exception` | Erro genérico relacionado à inicialização ou operação da câmera. |

### 🔧 **Main Class (`Camera`)**

#### Construtor (`__init__`)

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `source` | `int | str` | `0` | Índice numérico ou caminho de arquivo da fonte de vídeo. |
| `width` | `int` | `1280` | Largura de saída dos frames. |
| `height` | `int` | `720` | Altura de saída dos frames. |
| `fps` | `int` | `30` | Taxa de quadros por segundo. |
| `backend` | `Optional[int]` | `None` | Código do backend do OpenCV (ex.: `cv2.CAP_DSHOW`). |
| `reconnect_delay` | `float` | `2.0` | Tempo de espera, em segundos, antes de tentar reconectar a fonte. |

#### Propriedades Públicas

| Propriedade | Tipo | Descrição |
| :--- | :--- | :--- |
| `is_running` | `bool` | Indica se a captura de frames está em execução. |
| `capture_enabled` | `bool` | Indica se a aquisição de novos frames está ativada no momento. |

#### Métodos Públicos

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `enable_capture` | `() -> None` | Ativa a aquisição contínua de frames. |
| `disable_capture` | `() -> None` | Desativa a aquisição de frames, preservando o último frame capturado. |
| `register_display_callback` | `(callback: Callable[[Optional[np.ndarray]], None]) -> None` | Registra uma função de callback executada a cada iteração do loop da câmera para renderização. |
| `start` | `() -> None` | Inicia a thread de captura de frames contínua. |
| `stop` | `() -> None` | Para a captura de frames e libera os recursos da câmera. |
| `read` | `() -> Optional[np.ndarray]` | Retorna uma cópia do último frame capturado. Retorna `None` se nenhum frame estiver disponível. |

***

## 🔧 `Detector.py`

Gerencia a interface de detecção de objetos YOLO, fornecendo carregamento de modelo, inferência, análise de resultados e desenho de bounding boxes na imagem.  
O módulo expõe apenas a API pública necessária para a aplicação e omite detalhes internos e membros privados.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `BoundingBox` | `dataclass` | Representa a caixa delimitadora de um objeto. Contém propriedades de largura, altura e coordenadas do centro. |
| `Detection` | `dataclass` | Metadados de uma detecção: ID da classe, nome, confiança e caixa delimitadora. |

#### 📌 **Atributos e Propriedades de `BoundingBox`**

| Atributo / Propriedade | Tipo | Descrição |
| :--- | :--- | :--- |
| `x1` | `int` | Coordenada X do canto superior‑esquerdo. |
| `y1` | `int` | Coordenada Y do canto superior‑esquerdo. |
| `x2` | `int` | Coordenada X do canto inferior‑direito. |
| `y2` | `int` | Coordenada Y do canto inferior‑direito. |
| `width` | `int` | Largura da caixa (`x2 - x1`). |
| `height` | `int` | Altura da caixa (`y2 - y1`). |
| `center_x` | `int` | Coordenada X do centro (`(x1 + x2)//2`). |
| `center_y` | `int` | Coordenada Y do centro (`(y1 + y2)//2`). |

#### 📌 **Atributos de `Detection`**

| Atributo | Tipo | Descrição |
| :--- | :--- | :--- |
| `class_id` | `int` | Identificador inteiro da classe de objeto. |
| `class_name` | `str` | Nome textual da classe. |
| `confidence` | `float` | Probabilidade de correta detecção. |
| `bounding_box` | `BoundingBox` | Caixa delimitadora associada à detecção. |

---

### 📁 **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `validate_model_path` | `(model_path: str | Path) -> Path` | Verifica se o caminho para o arquivo de modelo YOLO existe e é um arquivo. Se não existir lança `FileNotFoundError`; se não for um arquivo lança `ValueError`. Retorna o caminho absoluto. |

---

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `DetectorError` | `Exception` | Erro genérico associado a operações de detecção (carregamento, inferência, análise ou desenho). |

---

### 🔧 **Main Class (`YOLODetector`)**

**Construtor (`__init__`):**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `model_path` | `str | Path` | *(Obrigatório)* | Caminho para o arquivo de modelo YOLO. |
| `confidence_threshold` | `float` | `0.4` | Limite mínimo de confiança para aceitar detecções. |
| `iou_threshold` | `float` | `0.45` | Limite mínimo de Intersection‑Over‑Union para supressão de sobreposição. |
| `device` | `str` | `"cpu"` | Dispositivo de inferência (`cpu` ou `cuda`/`cuda:0`, etc.). |

**Métodos Públicos:**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `detect` | `(frame: np.ndarray) -> list[Detection]` | Executa inferência YOLO no quadro fornecido e devolve uma lista de `Detection`. Garante que o quadro seja um `np.ndarray`; caso contrário, lança `TypeError`. Em caso de falha de inferência, levanta `DetectorError`. |
| `draw_detections` | `(frame: np.ndarray, detections: list[Detection]) -> np.ndarray` | Desenha caixas e rótulos das detecções no quadro e devolve a imagem anotada. Utiliza `cv2.rectangle` e `cv2.putText`. Em caso de erro, levanta `DetectorError`. |

***

## 🔧 `VisionManager.py`

Gerencia a captura de vídeo, detecção de objetos e localização em 3D usando calibração de câmera e transformações de referencial.

### 📦 **Dataclasses**

| Dataclass | Tipo | Descrição |
| :--- | :--- | :--- |
| `LocalizedTarget` | `dataclass` | Combina dados de detecção com coordenadas do mundo. |
| `WorldCoordinate` | `dataclass` | Representa coordenadas (x, y, z) no espaço real. |

### 📁 **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `VisionConfig` | `dataclass` | Carrega parâmetros de câmera, detector e caminhos de arquivos. |

### ⚙ **Utils**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `validate_camera_source` | `(index: int) -> Any` | Retorna objeto de fonte de câmera. |
| `validate_model_path` | `(path: Path | str) -> Path` | Valida e devolve caminho absoluto do modelo. |

### 🚨 **Exceções Personalizadas**

| Exceção | Tipo | Descrição |
| :--- | :--- | :--- |
| `CameraError` | `Exception` | Erro relacionado à câmera. |
| `DetectorError` | `Exception` | Erro relacionado ao detector. |

### 🔧 **Main Class (`VisionManager`)**

**Construtor (`__init__`):**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `config` | `VisionConfig` | *(Obrigatório)* | Configuração da visão. |

**Métodos Públicos:**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `initialize` | `() -> bool` | Inicia câmera, detector e calibração. |
| `start_capture` | `() -> None` | Inicia thread de captura. |
| `stop_capture` | `(destroy_window: bool = True) -> None` | Para thread e libera recursos. |
| `enable_processing` | `() -> None` | Habilita captura de frames. |
| `disable_processing` | `() -> None` | Desabilita captura de frames. |
| `get_latest_frame` | `() -> Optional[np.ndarray]` | Retorna frame mais recente. |
| `process_and_localize` | `(frame: np.ndarray, target_z_plane: float = 0.0) -> List[LocalizedTarget]` | Detecta e localiza objetos em 3D. |
| `update_status` | `(state: str, camera: str, detection: str) -> None` | Atualiza rótulos de status. |

***

## 🔧 `Amadeus_client.py`

Gerencia a orquestração principal do sistema AMADEUS MK‑I, lidando com a inicialização dos subsistemas (comunicação, visão, movimento), a criação da máquina de estados e a execução do ciclo de controle.

### 📁 **ConfigClasses**

| ConfigClass | Tipo | Descrição |
| :--- | :--- | :--- |
| `SerialConfig` | `dataclass` | Configurações de comunicação serial (porta, baud, etc.). |
| `VisionConfig` | `dataclass` | Parâmetros de captura e processamento de visão (resolução, filtros). |
| `MotionConfig` | `dataclass` | Configurações de motor e planejamento (velocidade, limites). |
| `TaskConfig` | `dataclass` | Definições de tarefas (objetivos, tempos). |

### 🔧 **Main Class (`AmadeusClient`)**

**Construtor (`__init__`)**

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `config_path` | `str` | `"config/settings.yaml"` | Caminho do arquivo YAML contendo as definições globais. |

**Métodos Públicos**

| Método | Assinatura | Descrição |
| :--- | :--- | :--- |
| `initialize` | `(self) -> bool` | Faz a leitura do YAML, configura o logging e instancia os gerenciadores de comunicação, visão e movimento, além de montar a máquina de estados. Retorna `True` se tudo for bem-sucedido. |
| `start` | `(self) -> None` | Conecta ao hardware, inicia a máquina de estados e entra no loop principal de controle. |
| `stop` | `(self) -> None` | Interrompe o loop, encerra captura de visão, desconecta o serial e libera recursos. |

**Propriedades Públicas**

| Propriedade | Tipo | Descrição |
| :--- | :--- | :--- |
| `settings` | `Dict[str, Any]` | Dicionário contendo os parâmetros de configuração carregados (exposto como propriedade pública para acesso externo). |

### ⚙ **Funções de Módulo**

| Função | Assinatura | Descrição |
| :--- | :--- | :--- |
| `main` | `() -> None` | Instancia `AmadeusClient`, faz a inicialização e, caso bem-sucedida, entra no estado principal. Se falhar, encerra o processo com código de erro 1. |

