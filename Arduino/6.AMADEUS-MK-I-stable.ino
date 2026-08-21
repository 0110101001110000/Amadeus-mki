

// Init -------------------------------------------------------------------- //


// Libraries

#include <Servo.h>
#include "Led.h"
#include <Servo.h>


// Defines

#define internal_led_pin LED_BUILTIN
#define internal_led_interval 250

#define joy_enabled 1

#define right_joy_x_pin A4
#define right_joy_y_pin A5

#define right_joy_btn_pin 2
#define right_joy_safezone 20  // 0-100

#define left_joy_x_pin A6
#define left_joy_y_pin A7
#define left_joy_btn_pin 3
#define left_joy_safezone 20  // 0-100

#define base_servo_pin 4
#define base_servo_start_pos 20
#define base_servo_min_pos 0
#define base_servo_max_pos 180

#define shoulder_servo_pin 5
#define shoulder_servo_start_pos 10
#define shoulder_servo_min_pos 0
#define shoulder_servo_max_pos 180  //90

#define elbow_servo_pin 6
#define elbow_servo_start_pos 0
#define elbow_servo_min_pos 0
#define elbow_servo_max_pos 180  // 70

#define gripper_servo_pin 7
#define gripper_servo_start_pos 65
#define gripper_servo_min_pos 63
#define gripper_servo_max_pos 155


// Variables

unsigned long int current_millis = 0;

int servos_interval[3] = { 44, 22, 22 };
byte serial_char_index = 0;

char serial_command_chars[64];
int key;
int value;

bool exec_move_to = false;
bool exec_grip = false;
bool exec_reset_pos = false;
bool exec_speed = false;
bool exec_stop_auto_move = false;
bool exec_showcase = false;

int showcase_step_index = 0;
int showcase_mode = 0;
// int auto_move_init_index = 1;
// int auto_move_end_index  = 2;

bool exec_move_all = false;
int move_all_values[4] = { -1, -1, -1, -1 };


// Classes

class Joystick {

private:

  int pinX;
  int pinY;
  int pinButton;

  int rawX;
  int rawY;

  bool buttonState;

  int mappedX;
  int mappedY;

  int safezoneValue;

public:

  // Constructor
  Joystick(int x, int y, int button, int safezone = 20) {
    pinX = x;
    pinY = y;
    pinButton = button;
    safezoneValue = safezone;
  }

  // Init
  void begin() {
    pinMode(pinX, INPUT);
    pinMode(pinY, INPUT);
    pinMode(pinButton, INPUT_PULLUP);
  }

  // Main methods
  void update() {
    rawX = analogRead(pinX);
    //Serial.print("rawX: "); Serial.print(rawX); Serial.println(";");
    rawY = analogRead(pinY);
    //Serial.print("rawY: "); Serial.print(rawY); Serial.println(";");

    buttonState = !digitalRead(pinButton);

    mappedX = processAxis(rawX);
    // Serial.print("mappedX: "); Serial.print(mappedX); Serial.println(";");
    mappedY = processAxis(rawY);
    // Serial.print("mappedY: "); Serial.print(mappedY); Serial.println(";");
  }
  int processAxis(int value) {
    int mappedAxis;

    int posMinValue = 0;
    int posMaxValue = 512;
    int negMinValue = 512;
    int negMaxValue = 1023;

    bool isPositive = (value <= posMaxValue) ? true : false;

    // Map to 0 -> 100 & 0 -> -100
    if (isPositive) {
      mappedAxis = abs(map(value - posMaxValue, posMinValue, posMaxValue, 0, 100));
      // Serial.print("mappedAxis: "); Serial.print(mappedAxis); Serial.println("; ");
    } else {
      mappedAxis = -(map(value, negMinValue, negMaxValue, 0, 100));
      // Serial.print("mappedAxis: "); Serial.print(mappedAxis); Serial.println("; ");
    }
    //Serial.print("mappedAxis: "); Serial.print(mappedAxis); Serial.println("; ");

    // Safezone
    if (isPositive & (mappedAxis < safezoneValue)) {
      //Serial.println("mappedPositiveAxis: Safezone;");
      return 0;
    } else if (abs(mappedAxis) < safezoneValue) {
      //Serial.println("mappedNegativeAxis: Safezone;");
      return 0;
    }

    // Map to 1 -> 3 & -1 -> -3
    if (isPositive & (mappedAxis >= safezoneValue)) {
      mappedAxis = map(mappedAxis - safezoneValue, 0, 80, 1, 3);
      //Serial.print("mappedAxis: "); Serial.print(mappedAxis); Serial.println("; ");
      return mappedAxis;
    } else if (abs(mappedAxis) >= safezoneValue) {
      mappedAxis = -map(abs(mappedAxis) - safezoneValue, 0, 80, 1, 3);
      //Serial.print("mappedAxis: "); Serial.print(mappedAxis); Serial.println("; ");
      return mappedAxis;
    }
  }

  // Getters
  int getX() {
    return mappedX;
  }
  int getY() {
    return mappedY;
  }
  bool isPressed() {
    return buttonState;
  }
  bool isMoving() {
    return ((mappedX != 0) || (mappedY != 0));
  }

  // Setters
  void setX(int rawX) {
    mappedX = processAxis(rawX);
    return mappedX;
  }
  void setY(int rawY) {
    mappedY = processAxis(rawY);
    return mappedY;
  }
};

class Motor {

private:

  int pin;
  int pos;

  int start_pos;
  int min_pos;
  int max_pos;

  Servo servo;

  unsigned long int prev_time;

public:

  // Constructor
  Motor(int motor_pin, int inicial_pos = 60, int minimum_pos = 0, int maximum_pos = 180) {
    pin = motor_pin;
    pos = inicial_pos;

    start_pos = inicial_pos;
    min_pos = minimum_pos;
    max_pos = maximum_pos;
  }

  // Init
  void begin() {
    servo.attach(pin);
    servo.write(pos);
  }

  // Main methods
  int move(bool increase, int interval) {
    if ((millis() - prev_time) >= interval) {
      update_pos(increase);
      // Serial.print("moving_to: "); Serial.print(pos); Serial.println(";");
      servo.write(pos);
      prev_time = millis();
    }
    return pos;
  }
  bool move_to(int target_pos, int interval = 20) {
    // Serial.print("target_pos: "); Serial.print(target_pos); Serial.println(";");
    // Serial.print("previos_pos: "); Serial.print(pos); Serial.println(";");

    if (target_pos < pos && target_pos < min_pos) {
      target_pos = min_pos;
    } else if (target_pos > pos && target_pos > max_pos) {
      target_pos = max_pos;
    }

    if (target_pos < pos) {
      move(false, interval);
    } else if (target_pos > pos) {
      move(true, interval);
    }

    // Serial.print("current_pos: "); Serial.print(pos); Serial.println(";");

    return (target_pos == pos);
  }

  // Other methods
  void update_pos(bool increase) {
    if (increase) {
      pos = (pos < max_pos) ? pos + 1 : max_pos;
    } else {
      pos = (pos > min_pos) ? pos - 1 : min_pos;
    }
    // Serial.print("new_pos: "); Serial.print(pos); Serial.println(";");
  }

  // Getters
  bool is_in_start_pos() {
    return (pos == start_pos);
  }
  int get_pos() {
    return pos;
  }

  // Setters
  void set_min_pos(int new_min_pos) {
    min_pos = new_min_pos;
  }
  void set_max_pos(int new_max_pos) {
    max_pos = new_max_pos;
  }
};

class RobotArm {

private:

    Motor& base;
    Motor& arm1;
    Motor& arm2;
    Motor& grip;

    float segmentLength;
    float shoulderHeight;

    int baseOffset;
    int arm1Offset;
    int arm2Offset;

public:

    RobotArm(
        Motor& baseMotor,
        Motor& arm1Motor,
        Motor& arm2Motor,
        Motor& gripMotor,

        float armSegmentLength = 80.0,
        float shoulderHeightMm = 90.0,

        int baseServoOffset = 90,
        int arm1ServoOffset = 40,
        int arm2ServoOffset = 55
    )
    :
    base(baseMotor),
    arm1(arm1Motor),
    arm2(arm2Motor),
    grip(gripMotor),
    segmentLength(armSegmentLength),
    baseOffset(baseServoOffset),
    arm1Offset(arm1ServoOffset),
    arm2Offset(arm2ServoOffset)
    {}

    bool move_to_xyz(
        float x,
        float y,
        float z,
        int gripAngle,
        int interval = 20
    )
    {
        float baseAngle;
        float arm1Angle;
        float arm2Angle;

        if (!calculate_angles(
                x,
                y,
                z,
                baseAngle,
                arm1Angle,
                arm2Angle))
        {
            return false;
        }

        bool baseDone =
            base.move_to(round(baseAngle), interval);

        bool arm1Done =
            arm1.move_to(round(arm1Angle), interval);

        bool arm2Done =
            arm2.move_to(round(arm2Angle), interval);

        bool gripDone =
            grip.move_to(gripAngle, interval);

        return
            baseDone &&
            arm1Done &&
            arm2Done &&
            gripDone;
    }

    bool calculate_angles(
        float x,
        float y,
        float z,

        float& baseAngle,
        float& arm1Angle,
        float& arm2Angle
    )
    {
        float b = atan2(y, x) * 180.0 / PI;

        float zRelative = z - shoulderHeight;

        float l = sqrt(x * x + y * y);

        if (l < 0.01)
            l = 0.01;
        
        float h = sqrt(l * l + zRelative * zRelative);

        float v = (h / 2.0) / segmentLength;

        if (v < -1.0 || v > 1.0)
        {
            Serial.print("[ERROR] Target out of reach: ");
            Serial.print("x=");
            Serial.print(x);
            Serial.print(" y=");
            Serial.print(y);
            Serial.print(" z=");
            Serial.println(z);

            return false;
        }

        
        float phi = atan2(zRelative, l) * 180.0 / PI;

        float theta =
            acos(v) * 180.0 / PI;

        float a1 = phi - theta;
        float a2 = phi + theta;

        baseAngle = b + baseOffset;
        arm1Angle = arm1Offset - a1;
        arm2Angle = a2 + arm2Offset;

        return true;
    }

    bool is_reachable(
        float x,
        float y,
        float z
    )
    {
        float l = sqrt(x * x + y * y);

        float zRelative = z - shoulderHeight;

        float h = sqrt(l * l + zRelative * zRelative);

        return h <= (segmentLength * 2.0);
    }

    float max_reach()
    {
        return segmentLength * 2.0;
    }

    void set_segment_length(float length)
    {
        segmentLength = length;
    }

    float get_segment_length()
    {
        return segmentLength;
    }

    void set_offsets(
        int newBaseOffset,
        int newArm1Offset,
        int newArm2Offset
    )
    {
        baseOffset = newBaseOffset;
        arm1Offset = newArm1Offset;
        arm2Offset = newArm2Offset;
    }
};


// Objects

Led builtin_led(internal_led_pin);

Joystick right_joy(right_joy_y_pin, right_joy_x_pin, right_joy_btn_pin, right_joy_safezone);
Joystick left_joy(left_joy_y_pin, left_joy_x_pin, left_joy_btn_pin, left_joy_safezone);

Motor base_servo(base_servo_pin, base_servo_start_pos, base_servo_min_pos, base_servo_max_pos);
Motor shoulder_servo(shoulder_servo_pin, shoulder_servo_start_pos, shoulder_servo_min_pos, shoulder_servo_max_pos);
Motor elbow_servo(elbow_servo_pin, elbow_servo_start_pos, elbow_servo_min_pos, elbow_servo_max_pos);
Motor gripper_servo(gripper_servo_pin, gripper_servo_start_pos, gripper_servo_min_pos, gripper_servo_max_pos);

RobotArm arm(base_servo, shoulder_servo, elbow_servo, gripper_servo);


// Helper functions

void move_servo_from_input(int value, Motor &servo, int servos_interval[], bool invert = false) {
  if (value == 0) { return; }

  if (invert) { !value; }

  bool direction = (value > 0);

  byte index = abs(value) - 1;
  servo.move(direction, servos_interval[index]);
}

int split_key_value(const char *arg, char *key, int key_size, char *value, int value_size, char sep = '=') {
  int i = 0, j = 0;
  int found_equal = 0;

  if (!arg || !key || !value) return 0;

  for (int k = 0; arg[k] != '\0'; k++) {
    if (arg[k] == sep) {
      found_equal = 1;
      continue;
    }

    if (!found_equal) {
      if (i < key_size - 1) {
        key[i++] = arg[k];
      }
    } else {
      if (j < value_size - 1) {
        value[j++] = arg[k];
      }
    }
  }

  key[i] = '\0';
  value[j] = '\0';

  // Evaluate -> 0=error 1=success
  if (!found_equal || i == 0 || j == 0) {
    return 0;
  }

  return 1;
}

void send_response(const char *type, const char *command, const char *message) {
  // Stucture: <TYPE>:<COMMAND>:<STATUS>[:<DATA>]

  Serial.print(type);
  Serial.print(":");
  Serial.print(command);

  if (message != NULL) {
    Serial.print(":");
    Serial.print(message);
  }

  Serial.println();
}

void send_oK(const char *command, const char *message) {
  send_response("OK", command, message);
}

void send_error(const char *command, const char *message) {
  send_response("ERROR", command, message);
}

void send_running(const char *command, const char *message) {
  send_response("RUNNING", command, message);
}

void send_info(const char *command, const char *message) {
  send_response("INFO", command, message);
}


// Functions

bool parse_command(char *cmd) {
  char *command = strtok(cmd, " ");
  ;

  if (command[0] == '\n') {
    command = command + 1;
  }

  // Serial.print("Recived command: "); Serial.print(command); Serial.println(";");

  if (command == NULL) return false;

  if (strcmp(command, "MOVE_TO") == 0) {
    parse_move_to();
  } else if (strcmp(command, "MOVE_ALL") == 0) {
    parse_move_all();
  } else if (strcmp(command, "GRIP") == 0) {
    parse_grip();
  } else if (strcmp(command, "RESET") == 0) {
    exec_reset_pos = true;
  } else if (strcmp(command, "SPEED") == 0) {
    parse_speed();
  } else if (strcmp(command, "STOP") == 0) {
    handle_stop();
    send_info("STOP", "DONE");
  } else if (strcmp(command, "SHOWCASE") == 0) {
    parse_showcase();
  }

  return true;
}

void parse_move_to() {
  char *arg;

  int servo, position = -1;

  while ((arg = strtok(NULL, " ")) != NULL) {
    // Serial.print("Recived arg: "); Serial.print(arg); Serial.println(";");

    char extacted_key[10];
    char extacted_value[10];

    if (split_key_value(arg, extacted_key, sizeof(extacted_key), extacted_value, sizeof(extacted_value))) {
      // Serial.print("Key: "); Serial.print(key); Serial.println(";");
      // Serial.print("Value: "); Serial.print(value); Serial.println(";");

      int val = atoi(extacted_value);

      if (strcmp(extacted_key, "SERVO") == 0) {
        servo = val;
      } else if (strcmp(extacted_key, "POSITION") == 0) {
        position = val;
      }
    }
  }

  // Serial.print("S: "); Serial.println(servo);
  // Serial.print("P: "); Serial.println(position);

  key = servo;
  value = position;
  exec_move_to = true;
}

void parse_move_all() {
  char *arg;

  move_all_values[0] = -1;
  move_all_values[1] = -1;
  move_all_values[2] = -1;
  move_all_values[3] = -1;

  while ((arg = strtok(NULL, " ")) != NULL) {

    char extacted_key[10];
    char extacted_value[10];

    if (split_key_value(arg, extacted_key, sizeof(extacted_key), extacted_value, sizeof(extacted_value))) {

      int val = atoi(extacted_value);

      if (strcmp(extacted_key, "S1") == 0) {
        move_all_values[0] = val;
      } else if (strcmp(extacted_key, "S2") == 0) {
        move_all_values[1] = val;
      } else if (strcmp(extacted_key, "S3") == 0) {
        move_all_values[2] = val;
      } else if (strcmp(extacted_key, "S4") == 0) {
        move_all_values[3] = val;
      }
    }
  }

  exec_move_all = true;
}

bool handle_move_to(int &key, int &value) {
  bool finished = false;
  int interval = servos_interval[0];

  switch (key) {
    case 1:
      finished = base_servo.move_to(value, interval);
      break;
    case 2:
      finished = shoulder_servo.move_to(value, interval);
      // finished = arm.move_to_xyz(75, 0, 0, gripper_servo_start_pos);
      break;
    case 3:
      finished = elbow_servo.move_to(value, interval);
      break;
    case 4:
      finished = gripper_servo.move_to(value, interval);
      break;
  }

  return finished;
}

bool handle_move_all() {
  bool baseDone = true;
  bool shoulderDone = true;
  bool elbowDone = true;
  bool gripperDone = true;

  int interval = servos_interval[0];

  if (move_all_values[0] >= 0) {
    baseDone = base_servo.move_to(move_all_values[0], interval);
  }

  if (move_all_values[1] >= 0) {
    shoulderDone = shoulder_servo.move_to(move_all_values[1], interval);
  }

  if (move_all_values[2] >= 0) {
    elbowDone = elbow_servo.move_to(move_all_values[2], interval);
  }

  if (move_all_values[3] >= 0) {
    gripperDone = gripper_servo.move_to(move_all_values[3], interval);
  }

  return (
    baseDone &&
    shoulderDone &&
    elbowDone &&
    gripperDone
  );
}

void parse_grip() {
  char *arg;

  byte state = -1;

  while ((arg = strtok(NULL, " ")) != NULL) {
    // Serial.print("Recived arg: "); Serial.print(arg); Serial.println(";");

    char extacted_key[10];
    char extacted_value[10];

    if (split_key_value(arg, extacted_key, sizeof(extacted_key), extacted_value, sizeof(extacted_value))) {
      // Serial.print("Key: "); Serial.print(extacted_key); Serial.println(";");
      // Serial.print("Value: "); Serial.print(extacted_value); Serial.println(";");

      byte val = atoi(extacted_value);

      if (strcmp(extacted_key, "STATE") == 0) {
        state = (val != 0 && val != 1) ? -1 : val;
      }
    }
  }

  // Serial.print("STATE: "); Serial.println(state);

  if (state == 1 || state == 0) {
    key = -1;
    value = state;
    exec_grip = true;
  }
}

bool handle_grip(int &value) {
  return gripper_servo.move_to((value == 1) ? gripper_servo_max_pos : 81);
}

bool handle_reset() {
  int interval = servos_interval[0];

  base_servo.move_to(base_servo_start_pos, interval);
  shoulder_servo.move_to(shoulder_servo_start_pos, interval);
  elbow_servo.move_to(elbow_servo_start_pos, interval);
  gripper_servo.move_to(gripper_servo_start_pos, interval);

  // return (base_servo.is_in_start_pos() && elbow_servo.is_in_start_pos());
  return ((base_servo.is_in_start_pos() && shoulder_servo.is_in_start_pos()) && (elbow_servo.is_in_start_pos() && gripper_servo.is_in_start_pos()));
}

void parse_speed() {
  char *arg;

  int min_speed, max_speed = -1;

  while ((arg = strtok(NULL, " ")) != NULL) {
    // Serial.print("Recived arg: "); Serial.print(arg); Serial.println(";");

    char extacted_key[10];
    char extacted_value[10];

    if (split_key_value(arg, extacted_key, sizeof(extacted_key), extacted_value, sizeof(extacted_value))) {
      // Serial.print("Key: "); Serial.print(extacted_key); Serial.println(";");
      // Serial.print("Value: "); Serial.print(extacted_value); Serial.println(";");

      int val = atoi(extacted_value);

      if (strcmp(extacted_key, "MIN") == 0) {
        min_speed = val;
      } else if (strcmp(extacted_key, "MAX") == 0) {
        max_speed = val;
      }
    }
  }

  // Serial.print("STATE: "); Serial.println(state);

  if (min_speed >= 0) {
    key = 1;
    value = min_speed;
    handle_speed(key, value);

    char buffer[50];
    snprintf(buffer, sizeof(buffer), "MIN=%d", value);
    send_oK("SPEED", buffer);
  }
  if (max_speed >= 0) {
    key = 2;
    value = max_speed;
    handle_speed(key, value);

    char buffer[50];
    snprintf(buffer, sizeof(buffer), "MAX=%d", value);
    send_oK("SPEED", buffer);
  }
}

bool handle_speed(int &key, int &value) {
  if (key != 1 && key != 2) {
    return false;
  }

  if (key == 1) {
    servos_interval[0] = value;
    // Serial.print("servos_min_interval: "); Serial.print(servos_interval[0]); Serial.println(";");
  } else if (key == 2) {
    servos_interval[1] = value;
    servos_interval[2] = value;
    // Serial.print("servos_max_interval: "); Serial.print(servos_interval[1]); Serial.println(";");
  }

  return true;
}

void parse_showcase() {
  char *arg;
  int mode = -1;

  while ((arg = strtok(NULL, " ")) != NULL) {
    char extacted_key[10];
    char extacted_value[10];

    if (split_key_value(arg, extacted_key, sizeof(extacted_key), extacted_value, sizeof(extacted_value))) {
      if (strcmp(extacted_key, "MODE") == 0) {
        mode = atoi(extacted_value);
      }
    }
  }

  if (mode >= 0) {
    exec_showcase = true;
    showcase_step_index = 0;
    showcase_mode = mode;
    //send_running("SHOWCASE", "MODE="+String(mode).c_str());
  } else {
    send_error("SHOWCASE", "MISSING_MODE");
  }
}

bool handle_stop() {
  if (exec_move_to) { send_info("MOVE_TO", "STOPPED"); }
  if (exec_move_all) { send_info("MOVE_ALL", "STOPPED"); }
  if (exec_grip) { send_info("GRIP", "STOPPED"); }
  if (exec_reset_pos) { send_info("RESET", "STOPPED"); }
  if (exec_showcase) { send_info("SHOWCASE", "STOPPED"); }

  exec_stop_auto_move = false;
  exec_move_to = false;
  exec_move_all = false;
  exec_grip = false;
  exec_reset_pos = false;
  exec_showcase = false;
  key = -1;
  value = -1;

  return true;
}

bool handle_showcase(int mode) {
  int interval = servos_interval[0];

  // Posições de demonstração (Exemplo de um padrão simples)
  // Mode 0: Movimento A (Base Min) -> Retorno
  // Mode 1: Movimento B (Base Max) -> Retorno

  int target_pos_A = base_servo_min_pos;
  int target_pos_B = base_servo_max_pos;
  int target_reset = base_servo_start_pos;
  
  int next_target_pos;

  // Determinar o alvo com base no modo
  int current_target_pos;
  if (mode == 0) {
    current_target_pos = target_pos_A;
  } else if (mode == 1) {
    current_target_pos = target_pos_B;
  } else {
    // Se o modo for inválido, para
    return false;
  }

  // Sequência de passos (Showcase_step_index controla qual parte da sequência estamos)
  // 0: Move para alvo A (ou B)
  // 1: Retorna à posição inicial
  // 2: Move para alvo B (ou A)
  // 3: Retorna à posição inicial (reinicia o ciclo)

  switch (showcase_step_index) {
    case 0:  // Mover para o ponto de demonstração (A ou B)
      // A função move_to retorna TRUE quando a posição é atingida
      if (base_servo.move_to(current_target_pos, interval)) {
        showcase_step_index = 1;  // Próximo passo: voltar para o reset
        return true;
      }
      return false;

    case 1:  // Retorno à posição inicial após o movimento
      if (base_servo.move_to(target_reset, interval)) {
        showcase_step_index = 2;  // Próximo passo: iniciar o próximo movimento (B ou A)
        // Para garantir o loop contínuo, o segundo movimento pode ser o inverso do primeiro
        next_target_pos = (current_target_pos == target_pos_A) ? target_pos_B : target_pos_A;
        return true;
      }
      return false;

    case 2:  // Movimento de retorno ou segundo movimento (B ou A)
      if (base_servo.move_to(next_target_pos, interval)) {
        showcase_step_index = 3;  // Próximo passo: voltar para o reset
        return true;
      }
      return false;

    case 3:  // Retorno à posição inicial antes de recomeçar o loop
      if (base_servo.move_to(target_reset, interval)) {
        showcase_step_index = 0;  // Loop completo, recomeça em 0
        return true;
      }
      return false;

    default:
      // Estado de erro ou desconhecido
      showcase_step_index = 0;
      return false;
  }
}


// Main functions

void setup() {
  // Serial
  Serial.begin(9600);
  while (!Serial) {};

  // Builtin led
  builtin_led.begin();

  // Joysticks
  right_joy.begin();
  left_joy.begin();

  // Servos
  base_servo.begin();
  shoulder_servo.begin();
  elbow_servo.begin();
  gripper_servo.begin();
}

void loop() {
  // Builtin led
  builtin_led.blink(internal_led_interval);

  // Serial
  while (Serial.available() > 0) {
    char character = Serial.read();

    // Reset index if overflow
    if (serial_char_index >= sizeof(serial_command_chars) - 1) {
      serial_char_index = 0;
    }

    // Store character
    if (character != ';') {
      if (serial_char_index < sizeof(serial_command_chars) - 1) {
        serial_command_chars[serial_char_index++] = character;
      }
    }

    // Process command
    else {
      serial_command_chars[serial_char_index] = '\0';

      // Serial.print("You send: "); Serial.println(serial_command_chars);

      if (parse_command(serial_command_chars) == false) {
        Serial.println("Invalid command!");
        serial_command_chars[0] = '\0';
      }

      serial_char_index = 0;
    }
  }

  // Update joysticks
  right_joy.update();
  left_joy.update();

  // Disable joyticks
  if (!joy_enabled) {
    right_joy.setX(512);
    right_joy.setY(512);
    left_joy.setX(512);
    left_joy.setY(512);
  }


  // Serial.print("right_x: "); Serial.print(right_joy.getX()); Serial.println(";");
  // Serial.print("right_y: "); Serial.print(right_joy.getY()); Serial.println(";");
  // Serial.print("right_is_moving: "); Serial.print(right_joy.isMoving() ? "1" : "0"); Serial.println(";");
  // Serial.print("right_is_btn_pressed: "); Serial.print(right_joy.isPressed() ? "1" : "0"); Serial.println(";");
  // Serial.print("left_x: "); Serial.print(left_joy.getX()); Serial.println(";");
  // Serial.print("left_y: "); Serial.print(left_joy.getY()); Serial.println(";");
  // Serial.print("left_is_moving: "); Serial.print(left_joy.isMoving() ? "1" : "0"); Serial.println(";");
  // Serial.print("left_is_btn_pressed: "); Serial.print(left_joy.isPressed() ? "1" : "0"); Serial.println(";");

  // Move servos by joystick input
  move_servo_from_input(right_joy.getX(), base_servo, servos_interval, false);
  move_servo_from_input(left_joy.getY(), shoulder_servo, servos_interval);
  move_servo_from_input(right_joy.getY(), elbow_servo, servos_interval);
  move_servo_from_input(left_joy.getX(), gripper_servo, servos_interval);

  // Serial.print("base_servo_pos"); Serial.print(base_servo.get_pos()); Serial.println(";");

  // Exec move servo to a position by serial command
  if (exec_move_to) {
    if (!right_joy.isMoving() && !left_joy.isMoving() && !exec_grip && !exec_reset_pos) {
      exec_move_to = !(handle_move_to(key, value));

      if (!exec_move_to) {
        char buffer[50];
        snprintf(buffer, sizeof(buffer), "SERVO=%d:POSITION=%d", key, value);
        send_oK("MOVE_TO", buffer);
      }
    } else {
      exec_move_to = false;
      send_info("MOVE_TO", "STOPPED");
    }

    if (!exec_move_to) {
      value = -1;
      key = -1;
    }
  }

  // Exec move all servos by serial command
  if (exec_move_all) {
    if (!right_joy.isMoving() && !left_joy.isMoving() && !exec_move_to && !exec_grip && !exec_reset_pos) {

      exec_move_all = !handle_move_all();

      if (!exec_move_all) {
        char buffer[80];
        snprintf(
          buffer,
          sizeof(buffer),
          "S1=%d:S2=%d:S3=%d:S4=%d",
          move_all_values[0],
          move_all_values[1],
          move_all_values[2],
          move_all_values[3]
        );

        send_oK("MOVE_ALL", buffer);
      }

    } else {
      exec_move_all = false;
      send_info("MOVE_ALL", "STOPPED");
    }
  }

  // Exec open/close gripper servo by serial command
  if (exec_grip) {
    if (!right_joy.isMoving() && !left_joy.isMoving() && !exec_move_to && !exec_reset_pos) {
      exec_grip = !handle_grip(value);

      if (!exec_grip) {
        char buffer[50];
        snprintf(buffer, sizeof(buffer), "STATE=%d", value);
        send_oK("GRIP", buffer);
      }
    } else {
      exec_grip = false;
      send_info("GRIP", "STOPPED");
    }

    if (!exec_grip) {
      value = -1;
      key = -1;
    }
  }

  // Exec reset all servo pos by serial command or joystick input
  if (right_joy.isPressed() && !right_joy.isMoving() && !left_joy.isMoving()) { exec_reset_pos = true; }
  if (exec_reset_pos) {
    if (!right_joy.isMoving() && !left_joy.isMoving() && !exec_move_to && !exec_grip) {
      exec_reset_pos = !handle_reset();

      if (!exec_reset_pos) {
        send_info("RESET", "DONE");
      }
    } else {
      exec_reset_pos = false;
      send_info("RESET", "STOPPED");
    }
  }

  // Exec showcase mode by serial command
  if (exec_showcase) {
    if (!right_joy.isMoving() && !left_joy.isMoving() && !exec_move_to && !exec_grip && !exec_reset_pos) {
      // Passa o modo (assumindo que o modo foi capturado no parse_showcase)
      handle_showcase(showcase_mode);  // Aqui deve ser usado o modo específico capturado

      // NOTA IMPORTANTE: Como o modo não está globalmente acessível neste ponto,
      // estou assumindo '0' para o exemplo. Em um código real, 'mode' precisaria ser
      // armazenado em uma variável global ao chamar parse_showcase().

      // if (!exec_showcase) {
      //   // Se o showcase parou (por interrupção externa, por exemplo)
      //   send_info("SHOWCASE", "STOPPED_MANUALLY");
      //   exec_showcase = false; // Garante que a flag seja desativada
      // }
    } else {
      // Parar caso haja input manual enquanto showcase roda
      exec_showcase = false;
      send_info("SHOWCASE", "STOPPED");
    }
  }

  // Default delay
  delay(1);

  // Update global millis
  current_millis = millis();
}
