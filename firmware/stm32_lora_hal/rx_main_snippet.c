/* 
 * -----------------------------------------------------------------------------
 * INSTRUCTIONS FOR STM32F103 (MINI PILL) - RX NODE
 * -----------------------------------------------------------------------------
 * 1. In STM32CubeMX, enable SPI1 (Full-Duplex Master)
 * 2. Enable USART1 at 115200 baud for Host PC communication
 * 3. Set PA4 (NSS), PB0 (RST), and PB1 (DIO0) as GPIO_Output/GPIO_Input accordingly.
 * 4. Generate Code.
 * 5. Copy sx1278.h to Core/Inc and sx1278.c to Core/Src.
 * 6. Add the following snippets to your generated main.c:
 */

/* USER CODE BEGIN Includes */
#include "sx1278.h"
/* USER CODE END Includes */

/* USER CODE BEGIN PV */
#define PACKET_LENGTH 12
uint8_t lora_rx_buffer[255];
/* USER CODE END PV */

/* USER CODE BEGIN 2 */
// Initialize LoRa
SX1278_Init();
SX1278_SetSpreadingFactor(12);

// Put LoRa in continuous receive mode
SX1278_Receive();
/* USER CODE END 2 */

/* USER CODE BEGIN WHILE */
while (1) {
    // Poll for received LoRa packets
    uint8_t packet_size = SX1278_ParsePacket();
    
    if (packet_size > 0) {
        SX1278_Read(lora_rx_buffer, packet_size);
        
        // If it matches our expected 12-byte telemetry packet size
        if (packet_size == PACKET_LENGTH) {
            // Check Header 0xAB 0xCD
            if (lora_rx_buffer[0] == 0xAB && lora_rx_buffer[1] == 0xCD) {
                // Send the exact byte array over UART to the Host PC
                // (assuming huart1 is connected to the PC)
                HAL_UART_Transmit(&huart1, lora_rx_buffer, PACKET_LENGTH, HAL_MAX_DELAY);
            }
        }
        
        // Put back in receive mode to listen for the next packet
        SX1278_Receive();
    }
    
    /* USER CODE END WHILE */
    /* USER CODE BEGIN 3 */
}
/* USER CODE END 3 */
