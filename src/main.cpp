#include <Arduino.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include "config.h"

static Adafruit_LIS3DH lis = Adafruit_LIS3DH();
static bool sensorInitialized = false;

// Low-pass filter state (alpha = 0.1, from production firmware)
static constexpr float kLpfAlpha = 0.1f;
static float g_fx = 0, g_fy = 0, g_fz = 0;
static bool lpfSeeded = false;

// Timing: emit CSV at ~50 Hz (20ms interval)
static constexpr uint32_t kOutputIntervalMs = 20UL;
static uint32_t lastOutputMs = 0;

// Sensor polling at 100 Hz (10ms) to feed LPF properly
static constexpr uint32_t kSampleIntervalMs = 10UL;
static uint32_t lastSampleMs = 0;

static void recoverI2CBus() {
    Wire.end();
    pinMode(PIN_I2C_SDA, INPUT_PULLUP);
    pinMode(PIN_I2C_SCL, INPUT_PULLUP);
    delayMicroseconds(10);

    if (digitalRead(PIN_I2C_SDA) == LOW) {
        pinMode(PIN_I2C_SCL, OUTPUT);
        for (int i = 0; i < 9; i++) {
            digitalWrite(PIN_I2C_SCL, LOW);
            delayMicroseconds(5);
            digitalWrite(PIN_I2C_SCL, HIGH);
            delayMicroseconds(5);
            pinMode(PIN_I2C_SDA, INPUT_PULLUP);
            if (digitalRead(PIN_I2C_SDA) == HIGH) break;
        }
    }

    pinMode(PIN_I2C_SDA, OUTPUT);
    digitalWrite(PIN_I2C_SDA, LOW);
    pinMode(PIN_I2C_SCL, OUTPUT);
    digitalWrite(PIN_I2C_SCL, HIGH);
    delayMicroseconds(5);
    digitalWrite(PIN_I2C_SDA, HIGH);
    delayMicroseconds(5);
    pinMode(PIN_I2C_SDA, INPUT);
    pinMode(PIN_I2C_SCL, INPUT);
}

static void initSensor() {
    recoverI2CBus();
    Wire.setPins(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.begin();

    for (int attempt = 0; attempt < 5; attempt++) {
        if (lis.begin(0x18) || lis.begin(0x19)) {
            lis.setRange(LIS3DH_RANGE_2_G);
            lis.setDataRate(LIS3DH_DATARATE_100_HZ);
            sensorInitialized = true;
            Serial.println("# LIS3DH OK (±2G, 100Hz)");
            return;
        }
        delay(200);
    }
    sensorInitialized = false;
    Serial.println("# LIS3DH init FAILED");
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) {}

    initSensor();
    if (sensorInitialized) {
        Serial.println("timestamp_ms,acc_x,acc_y,acc_z");
    }
}

void loop() {
    if (!sensorInitialized) return;

    uint32_t now = millis();

    // Poll sensor at 100 Hz to keep LPF fed
    if (now - lastSampleMs >= kSampleIntervalMs) {
        lastSampleMs = now;

        sensors_event_t e;
        lis.getEvent(&e);

        if (e.acceleration.x == 0.0f && e.acceleration.y == 0.0f && e.acceleration.z == 0.0f) {
            return;
        }

        if (!lpfSeeded) {
            g_fx = e.acceleration.x;
            g_fy = e.acceleration.y;
            g_fz = e.acceleration.z;
            lpfSeeded = true;
        } else {
            g_fx = kLpfAlpha * e.acceleration.x + (1.0f - kLpfAlpha) * g_fx;
            g_fy = kLpfAlpha * e.acceleration.y + (1.0f - kLpfAlpha) * g_fy;
            g_fz = kLpfAlpha * e.acceleration.z + (1.0f - kLpfAlpha) * g_fz;
        }
    }

    // Output filtered CSV at 50 Hz
    if (lpfSeeded && (now - lastOutputMs >= kOutputIntervalMs)) {
        lastOutputMs = now;
        Serial.print(now);
        Serial.print(',');
        Serial.print(g_fx, 4);
        Serial.print(',');
        Serial.print(g_fy, 4);
        Serial.print(',');
        Serial.println(g_fz, 4);
    }
}
