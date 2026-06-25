/*
  Minimal research firmware logger

  Purpose:
  - Read IMU values
  - Compute a simple tilt angle
  - Print only the fields needed for the dataset

  Serial format:
  timestamp_ms,accX,accY,accZ,angle

  The Python script labels the rows as standing or sitting based on capture time.
*/

#include <Arduino.h>

// Replace this with your actual IMU library and sensor init code.
// The sketch is intentionally minimal and self-contained for research use.

static const unsigned long SAMPLE_PERIOD_MS = 20;  // 50 Hz
static unsigned long lastSampleMs = 0;

static float readAccX() {
  // TODO: replace with real sensor read
  return 0.00f;
}

static float readAccY() {
  // TODO: replace with real sensor read
  return 0.98f;
}

static float readAccZ() {
  // TODO: replace with real sensor read
  return 0.10f;
}

static float computeAngleDeg(float accX, float accY, float accZ) {
  (void)accX;
  return atan2f(accZ, accY) * 180.0f / PI;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }
  Serial.println("timestamp_ms,accX,accY,accZ,angle");
}

void loop() {
  const unsigned long now = millis();
  if (now - lastSampleMs < SAMPLE_PERIOD_MS) {
    return;
  }
  lastSampleMs = now;

  const float accX = readAccX();
  const float accY = readAccY();
  const float accZ = readAccZ();
  const float angle = computeAngleDeg(accX, accY, accZ);

  Serial.print(now);
  Serial.print(",");
  Serial.print(accX, 4);
  Serial.print(",");
  Serial.print(accY, 4);
  Serial.print(",");
  Serial.print(accZ, 4);
  Serial.print(",");
  Serial.println(angle, 4);
}
