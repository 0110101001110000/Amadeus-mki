
# 📡 AMADEUS MK-I — Protocolo de Comunicação Serial

## 🧭 Visão Geral

O protocolo serial do **AMADEUS MK-I** foi projetado para ser:

* simples de interpretar
* compatível com integração futura com ROS 2
* extensível para automações e controle remoto

---

# 🧱 Estrutura Geral do Protocolo

## 📥 Formato padrão

```text
COMMAND ARG=VALUE ARG=VALUE ...;
```

---

## 📌 Regras Gerais

| Regra      | Descrição                          |
| ---------- | ---------------------------------- |
| Terminador | Todo comando deve terminar com `;` |
| Separador  | Argumentos separados por espaço    |
| Formato    | `KEY=VALUE`                        |
| Comandos   | Sempre em MAIÚSCULO                |
| Parsing    | Case-sensitive                     |
| Segurança  | Todo argumento deve ser validado   |

---

# 📚 Tabela de Comandos

| Comando  | Descrição                                      | Argumentos      | Categoria    |
| -------- | ---------------------------------------------- | --------------- | ------------ |
| MOVE_TO  | Move um servo para uma posição específica      | SERVO, POSITION | Movimento    |
| MOVE_ALL | Move múltiplos servos simultaneamente          | S1, S2, S3, S4  | Movimento    |
| GRIP     | Controla abertura/fechamento da garra          | STATE           | Manipulação  |
| RESET    | Retorna o braço à posição inicial              | Nenhum          | Sistema      |
| SPEED    | Define limites globais de velocidade           | MIN, MAX        | Configuração |
| STOP     | Interrompe imediatamente todos os movimentos   | Nenhum          | Emergência   |
| SHOWCASE | Coloca o braço em modo demonstração automático | MODE            | Automação    |

---

# 🎯 MOVE_TO

Move um servo específico para uma posição alvo.

## 📥 Formato

```text
MOVE_TO SERVO=<id> POSITION=<valor>;
```

---

## 📌 Argumentos

| Argumento | Tipo | Descrição   |
| --------- | ---- | ----------- |
| SERVO     | int  | ID do servo |
| POSITION  | int  | Ângulo alvo |

---

## ✅ Exemplo

```text
MOVE_TO SERVO=2 POSITION=90;
```

---

## 🧠 Observações

* Ideal para controle manual
* Base para integração com cinemática futura
* Executa o movimento de apenas um servo por comando

---

# 🔀 MOVE_ALL

Move vários servos simultaneamente para posições específicas.

Cada servo informado é movimentado em paralelo. Argumentos omitidos mantêm a posição atual do respectivo servo.

---

## 📥 Formato

```text
MOVE_ALL S1=<valor> S2=<valor> S3=<valor> S4=<valor>;
```

---

## 📌 Argumentos

| Argumento | Tipo | Descrição               |
| --------- | ---- | ----------------------- |
| S1        | int  | Posição alvo do Servo 1 |
| S2        | int  | Posição alvo do Servo 2 |
| S3        | int  | Posição alvo do Servo 3 |
| S4        | int  | Posição alvo do Servo 4 |

---

## ✅ Exemplos

### Movimentar todos os servos

```text
MOVE_ALL S1=90 S2=120 S3=140 S4=80;
```

### Movimentar apenas alguns servos

```text
MOVE_ALL S1=45 S3=160;
```

---

## 🧠 Observações

* Todos os movimentos são executados simultaneamente.
* Servos não informados permanecem na posição atual.
* Pode ser utilizado para criar poses completas do braço robótico.
* Facilita integrações futuras com cinemática inversa e ROS 2.

---

# ✋ GRIP

Controla o estado da garra.

## 📥 Formato

```text
GRIP STATE=<valor>;
```

---

## 📌 Argumentos

| Argumento | Tipo | Valores válidos | Descrição               |
| --------- | ---- | --------------- | ----------------------- |
| STATE     | int  | 0 ou 1          | 0 = aberto, 1 = fechado |

---

## ✅ Exemplo

```text
GRIP STATE=1;
```

---

# 🔄 RESET

Retorna todos os servos à posição padrão.

## 📥 Formato

```text
RESET;
```

---

## 🧠 Comportamento

* Move o braço para posição inicial segura
* Limpa estados temporários
* Pode cancelar movimentos pendentes

---

# ⚙️ SPEED

Define limites globais de velocidade.

## 📥 Formato

```text
SPEED MIN=<valor> MAX=<valor>;
```

---

## 📌 Argumentos

| Argumento | Tipo | Descrição         |
| --------- | ---- | ----------------- |
| MIN       | int  | Velocidade mínima |
| MAX       | int  | Velocidade máxima |

---

## ✅ Exemplo

```text
SPEED MIN=10 MAX=100;
```

---

## 🧠 Observações

* Afeta a suavidade dos movimentos.
* Os valores representam os intervalos utilizados pelo controlador interno.
* Valores devem ser validados:

  * `MIN <= MAX`
  * limites físicos do hardware

---

# 🛑 STOP

Interrompe imediatamente todos os movimentos do braço.

## 📥 Formato

```text
STOP;
```

---

## ⚠️ Prioridade

Este comando deve:

* interromper movimentações ativas
* cancelar MOVE_TO
* cancelar MOVE_ALL
* cancelar GRIP
* cancelar RESET
* cancelar SHOWCASE
* possuir prioridade máxima
* entrar em estado seguro

---

# 🎭 SHOWCASE

Coloca o braço em um modo de demonstração automática contínua.

O braço executa movimentos pré-programados em loop até receber outro comando de interrupção.

---

## 📥 Formato

```text
SHOWCASE MODE=<valor>;
```

---

## 📌 Argumentos

| Argumento | Tipo | Descrição                    |
| --------- | ---- | ---------------------------- |
| MODE      | int  | ID do padrão de demonstração |

---

## ✅ Exemplos

### Movimento de varredura simples

```text
SHOWCASE MODE=0;
```

---

## ⚠️ Comportamento esperado

Ao ativar SHOWCASE:

* o braço entra em modo autônomo
* comandos manuais podem interromper o modo
* MOVE_TO pode interromper o modo
* MOVE_ALL pode interromper o modo
* STOP deve cancelar imediatamente o showcase

---

# 📤 Respostas do Controlador

O firmware responde utilizando a seguinte estrutura:

```text
TYPE:COMMAND[:DADOS]
```

## Tipos de resposta

| Tipo    | Descrição                     |
| ------- | ----------------------------- |
| OK      | Comando executado com sucesso |
| RUNNING | Operação em andamento         |
| INFO    | Informação de estado          |
| ERROR   | Erro de processamento         |

---

## Exemplos

### Movimento concluído

```text
OK:MOVE_TO:SERVO=2:POSITION=90
```

### Movimento múltiplo concluído

```text
OK:MOVE_ALL:S1=90:S2=120:S3=140:S4=80
```

### Garra acionada

```text
OK:GRIP:STATE=1
```

### Reset concluído

```text
INFO:RESET:DONE
```

### Movimento interrompido

```text
INFO:MOVE_ALL:STOPPED
```

### Erro de comunicação

```text
ERROR:SERIAL:BUFFER_OVERFLOW
```

---

# 🧠 Filosofia de Arquitetura

O protocolo foi estruturado seguindo princípios de:

* desacoplamento entre comunicação e controle
* compatibilidade com middleware robótico
* extensibilidade futura
* interoperabilidade com ROS 2
* simplicidade para depuração serial

---

# 🔗 Compatibilidade Planejada

| Interface           | Compatível |
| ------------------- | ---------- |
| USB Serial          | ✅          |
| Bluetooth Serial    | ✅          |
| Wi-Fi Serial Bridge | ✅          |
| ROS 2 Serial Node   | ✅          |
