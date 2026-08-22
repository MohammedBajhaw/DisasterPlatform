#include <SPI.h>
#include <LoRa.h>

// STM32F411CEU6 SPI pins for LoRa SX1278
// Adjust these if you use different pins on the Black Pill!
#define SCK_PIN   PA5
#define MISO_PIN  PA6
#define MOSI_PIN  PA7
#define SS_PIN    PA4
#define RST_PIN   PB0
#define DIO0_PIN  PB1

// The expected length of the telemetry packet from Jetson
#define PACKET_LENGTH 12

byte buffer[PACKET_LENGTH];
int bufferIndex = 0;

void setup() {
  // Start USB Serial (UART) connected to Jetson
  Serial.begin(115200);
  while (!Serial);
  
  // Setup LoRa Pins
  LoRa.setPins(SS_PIN, RST_PIN, DIO0_PIN);

  // Initialize LoRa at 433 MHz (SX1278 is usually 433)
  if (!LoRa.begin(433E6)) {
    Serial.println("Starting LoRa failed!");
    while (1);
  }
  
  // Increase range (max power 20dBm, Spreading Factor 12)
  LoRa.setTxPower(20);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  
  Serial.println("STM32F4 LoRa TX Ready. Waiting for Jetson Data...");
}

void loop() {
  // Read incoming bytes from Jetson over USB Serial
  while (Serial.available()) {
    byte b = Serial.read();
    
    // Check for Header: 0xAB 0xCD
    if (bufferIndex == 0 && b != 0xAB) continue;
    if (bufferIndex == 1 && b != 0xCD) { bufferIndex = 0; continue; }
    
    buffer[bufferIndex++] = b;
    
    // If full packet received
    if (bufferIndex >= PACKET_LENGTH) {
      bufferIndex = 0;
      
      // Send the 12-byte payload over LoRa
      LoRa.beginPacket();
      LoRa.write(buffer, PACKET_LENGTH);
      LoRa.endPacket();
      
      // Optional: Blink LED or print debug
      // Serial.println("Packet transmitted over LoRa.");
    }
  }
}
