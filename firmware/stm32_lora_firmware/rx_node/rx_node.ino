#include <SPI.h>
#include <LoRa.h>

// STM32F103C6T6 Mini (Blue Pill) SPI pins for LoRa SX1278
// Adjust these if you use different pins!
#define SCK_PIN   PA5
#define MISO_PIN  PA6
#define MOSI_PIN  PA7
#define SS_PIN    PA4
#define RST_PIN   PB0
#define DIO0_PIN  PB1

#define PACKET_LENGTH 18

void setup() {
  // Start USB Serial (UART) connected to Host PC
  Serial.begin(115200);
  while (!Serial);
  
  // Setup LoRa Pins
  LoRa.setPins(SS_PIN, RST_PIN, DIO0_PIN);

  // Initialize LoRa at 433 MHz
  if (!LoRa.begin(433E6)) {
    // If it fails, send debug over UART (Node will ignore text)
    Serial.println("Starting LoRa RX failed!");
    while (1);
  }
  
  // Must match the TX settings
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  
  // Register callback for when a packet is received
  LoRa.onReceive(onReceive);
  
  // Put LoRa in receive mode
  LoRa.receive();
}

void loop() {
  // Do nothing in loop, the interrupt callback handles it
}

void onReceive(int packetSize) {
  if (packetSize == 0) return;
  
  byte buffer[255];
  int idx = 0;
  
  // Read packet
  while (LoRa.available() && idx < 255) {
    buffer[idx++] = LoRa.read();
  }
  
  // If the size matches our 12-byte telemetry packet
  if (idx == PACKET_LENGTH) {
    // Check Header 0xAB 0xCD
    if (buffer[0] == 0xAB && buffer[1] == 0xCD) {
      // Send the raw byte array over USB Serial to the Host PC ROS2 node
      Serial.write(buffer, PACKET_LENGTH);
    }
  }
}
