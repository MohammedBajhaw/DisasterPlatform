#ifndef SX1278_H
#define SX1278_H

#include "main.h"

// Hardware Abstraction Layer macros (To easily port between F1 and F4)
// User must define the SPI Handle externally (e.g. extern SPI_HandleTypeDef hspi1;)
extern SPI_HandleTypeDef hspi1;
#define SX1278_SPI &hspi1

// Change these to match your CubeMX pin labels
#define NSS_PORT GPIOA
#define NSS_PIN  GPIO_PIN_4

#define RST_PORT GPIOB
#define RST_PIN  GPIO_PIN_0

#define DIO0_PORT GPIOB
#define DIO0_PIN  GPIO_PIN_1

void SX1278_Init(void);
void SX1278_SetTxPower(int level);
void SX1278_SetSpreadingFactor(int sf);
void SX1278_BeginPacket(void);
void SX1278_Write(uint8_t *buffer, uint8_t size);
void SX1278_EndPacket(void);

void SX1278_Receive(void);
uint8_t SX1278_ParsePacket(void);
void SX1278_Read(uint8_t *buffer, uint8_t size);

#endif
