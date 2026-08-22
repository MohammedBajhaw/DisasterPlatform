/* 
 * -----------------------------------------------------------------------------
 * INSTRUCTIONS FOR STM32F411 (BLACK PILL) - TX NODE
 * -----------------------------------------------------------------------------
 * 1. In STM32CubeMX, enable SPI1 (Full-Duplex Master)
 * 2. Enable USART1 (or USART2) at 115200 baud for Jetson communication
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
uint8_t rx_buffer[PACKET_LENGTH];
uint8_t rx_index = 0;
/* USER CODE END PV */

/* USER CODE BEGIN 2 */
// Initialize LoRa
SX1278_Init();
SX1278_SetTxPower(20);
SX1278_SetSpreadingFactor(12);

// Start listening to UART (assuming huart1 is connected to Jetson)
// We will receive byte-by-byte in interrupt mode
uint8_t uart_byte;
HAL_UART_Receive_IT(&huart1, &uart_byte, 1);
/* USER CODE END 2 */

/* USER CODE BEGIN 4 */
// UART Interrupt Callback
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {
        // Check for Header 0xAB 0xCD
        if (rx_index == 0 && uart_byte != 0xAB) goto LISTEN_AGAIN;
        if (rx_index == 1 && uart_byte != 0xCD) { rx_index = 0; goto LISTEN_AGAIN; }
        
        rx_buffer[rx_index++] = uart_byte;
        
        if (rx_index >= PACKET_LENGTH) {
            rx_index = 0; // Reset for next packet
            
            // Transmit over LoRa
            SX1278_BeginPacket();
            SX1278_Write(rx_buffer, PACKET_LENGTH);
            SX1278_EndPacket();
        }
        
LISTEN_AGAIN:
        // Listen for next byte
        HAL_UART_Receive_IT(&huart1, &uart_byte, 1);
    }
}
/* USER CODE END 4 */
