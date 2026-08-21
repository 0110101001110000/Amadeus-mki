class Led {

private:

  int pin;

  unsigned long int blinkPrevTime = 0;

public:

  // Constructor
  Led(int ledPin) {
    pin = ledPin;
  }

  // Init
  void begin() {
    pinMode(pin, OUTPUT);
  }

  // Main methods
  void blink(int delay_interval = 250) {
    if ((millis() - blinkPrevTime) >= delay_interval) {
      alternate();
      blinkPrevTime = millis();
    }
  }

  // Getters
  bool isOn() {
    return digitalRead(pin);
  }
  bool isOff() {
    return !isOn();
  }

  // Setters
  bool on() {
    digitalWrite(pin, 1);
    return isOn();
  }
  bool off() {
    digitalWrite(pin, 0);
    return isOff();
  }
  bool alternate() {
    digitalWrite(pin, !digitalRead(pin));
    return digitalRead(pin);
  }
};