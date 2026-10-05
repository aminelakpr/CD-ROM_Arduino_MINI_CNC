#include <AccelStepper.h>
#include <Servo.h>

//pin Definitions
const int m1Pins[4] = {8, 10, 9, 11};   // motor 1 (YAxis)
const int m2Pins[4] = {A0, A2, A1, A3}; // motor 2 (XAxis)
const int servoPin = 3;

AccelStepper motor1(8, m1Pins[0], m1Pins[1], m1Pins[2], m1Pins[3]);
AccelStepper motor2(8, m2Pins[0], m2Pins[1], m2Pins[2], m2Pins[3]);
Servo penServo;

//---Calibration
float stepsPerMmX = 500.0; 
float stepsPerMmY = 4.2;   

bool isExecutingMotion = false;
String commandQueue = ""; 

void reportStatus(const char* state) {
  float currentMmX = motor2.currentPosition() / stepsPerMmX;
  float currentMmY = motor1.currentPosition() / stepsPerMmY;
  
  Serial.print("<");
  Serial.print(state);
  Serial.print("|MPos:");
  Serial.print(currentMmX, 3);
  Serial.print(",");
  Serial.print(currentMmY, 3);
  Serial.print(",0.000|FS:0,0>\r\n");
}

void setup() {
  Serial.begin(115200);
  penServo.attach(servoPin);
  penServo.write(110); 
  
  // Lowered baseline speeds
  motor1.setMaxSpeed(30.0);
  motor1.setAcceleration(40.0);
  motor2.setMaxSpeed(600.0);
  motor2.setAcceleration(200.0);
  
  Serial.println("Grbl 1.1h ['$' for help]");
}

void loop() {
  motor1.run();
  motor2.run();

  while (Serial.available() > 0) {
    char c = Serial.peek();
    if (c == '?') {
      Serial.read(); 
      if (motor1.distanceToGo() == 0 && motor2.distanceToGo() == 0) reportStatus("Idle");
      else reportStatus("Run");
    } else {
      commandQueue += (char)Serial.read(); 
    }
  }

  if (isExecutingMotion && motor1.distanceToGo() == 0 && motor2.distanceToGo() == 0) {
    Serial.println("ok"); 
    isExecutingMotion = false;
  }

  if (!isExecutingMotion && commandQueue.indexOf('\n') != -1) {
    int newlineIdx = commandQueue.indexOf('\n');
    String line = commandQueue.substring(0, newlineIdx);
    commandQueue = commandQueue.substring(newlineIdx + 1); 

    line.trim();
    line.toUpperCase();
    
    if (line.length() > 0) {
      if (line.startsWith("G0") || line.startsWith("G1") || line.startsWith("$J=")) {
        bool isRelative = (line.indexOf("G91") != -1);
        float currentMmX = motor2.currentPosition() / stepsPerMmX;
        float currentMmY = motor1.currentPosition() / stepsPerMmY;
        float targetMmX = currentMmX;
        float targetMmY = currentMmY;

        int xIdx = line.indexOf('X');
        int yIdx = line.indexOf('Y');
        if (xIdx != -1) targetMmX = isRelative ? (currentMmX + line.substring(xIdx + 1).toFloat()) : line.substring(xIdx + 1).toFloat();
        if (yIdx != -1) targetMmY = isRelative ? (currentMmY + line.substring(yIdx + 1).toFloat()) : line.substring(yIdx + 1).toFloat();

        long targetStepsX = targetMmX * stepsPerMmX;
        long targetStepsY = targetMmY * stepsPerMmY;
        long dx = abs(targetStepsX - motor2.currentPosition());
        long dy = abs(targetStepsY - motor1.currentPosition());
        long max_steps = max(dx, dy);

        if (max_steps > 0) {
          //SPEED CONTROLS REDUCED HERe
          float MAX_VECTOR_SPEED = 400.0;
          float MAX_VECTOR_ACCEL = 100.0;
          
          float ratioX = (float)dx / max_steps;
          float ratioY = (float)dy / max_steps;

          motor2.setMaxSpeed(max(MAX_VECTOR_SPEED * ratioX, 1.0));
          motor2.setAcceleration(max(MAX_VECTOR_ACCEL * ratioX, 1.0));
          motor1.setMaxSpeed(max(MAX_VECTOR_SPEED * ratioY, 1.0));
          motor1.setAcceleration(max(MAX_VECTOR_ACCEL * ratioY, 1.0));
        }

        motor2.moveTo(targetStepsX);
        motor1.moveTo(targetStepsY);
        isExecutingMotion = true; 
      }
      else if (line.startsWith("M3") || line.startsWith("M03")) {
        penServo.write(102); 
        delay(300);
        Serial.println("ok"); 
      } 
      else if (line.startsWith("M5") || line.startsWith("M05")) {
        penServo.write(110); 
        delay(300);
        Serial.println("ok"); 
      }
      else {
        Serial.println("ok");
      }
    }
  }
}
