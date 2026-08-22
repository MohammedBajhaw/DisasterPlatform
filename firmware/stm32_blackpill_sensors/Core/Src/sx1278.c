#include "sx1278.h"
#include "usbd_cdc_if.h"

#define REG_FIFO                 0x00
#define REG_OP_MODE              0x01
#define REG_PA_CONFIG            0x09
#define REG_FIFO_ADDR_PTR        0x0D
#define REG_FIFO_TX_BASE_ADDR    0x0E
#define REG_FIFO_RX_BASE_ADDR    0x0F
#define REG_FIFO_RX_CURRENT_ADDR 0x10
#define REG_IRQ_FLAGS            0x12
#define REG_RX_NB_BYTES          0x13
#define REG_MODEM_CONFIG_2       0x1E
#define REG_SYMB_TIMEOUT_LSB     0x1F

#define MODE_LONG_RANGE_MODE     0x80
#define MODE_SLEEP               0x00
#define MODE_STDBY               0x01
#define MODE_TX                  0x03
#define MODE_RX_CONTINUOUS       0x05

static uint8_t SX1278_ReadRegister(uint8_t reg) {
    uint8_t value;
    uint8_t addr = reg & 0x7F;
    HAL_GPIO_WritePin(NSS_PORT, NSS_PIN, GPIO_PIN_RESET);
    HAL_SPI_Transmit(SX1278_SPI, &addr, 1, HAL_MAX_DELAY);
    HAL_SPI_Receive(SX1278_SPI, &value, 1, HAL_MAX_DELAY);
    HAL_GPIO_WritePin(NSS_PORT, NSS_PIN, GPIO_PIN_SET);
    return value;
}

static void SX1278_WriteRegister(uint8_t reg, uint8_t value) {
    uint8_t addr = reg | 0x80;
    HAL_GPIO_WritePin(NSS_PORT, NSS_PIN, GPIO_PIN_RESET);
    HAL_SPI_Transmit(SX1278_SPI, &addr, 1, HAL_MAX_DELAY);
    HAL_SPI_Transmit(SX1278_SPI, &value, 1, HAL_MAX_DELAY);
    HAL_GPIO_WritePin(NSS_PORT, NSS_PIN, GPIO_PIN_SET);
}

void SX1278_Init(void) {
    // Hardware Reset
    HAL_GPIO_WritePin(RST_PORT, RST_PIN, GPIO_PIN_RESET);
    HAL_Delay(10);
    HAL_GPIO_WritePin(RST_PORT, RST_PIN, GPIO_PIN_SET);
    HAL_Delay(10);

    // Read Version (0x42)
    uint8_t ver = SX1278_ReadRegister(0x42);
    if (ver != 0x12) {
        while (1) {
            char err[] = "LoRa SPI Error: Version mismatch!\r\n";
            CDC_Transmit_FS((uint8_t*)err, sizeof(err)-1);
            HAL_Delay(1000);
        }
    }

    // Put into sleep mode
    SX1278_WriteRegister(REG_OP_MODE, MODE_SLEEP);
    HAL_Delay(10);
    
    // Set LoRa mode
    SX1278_WriteRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_STDBY);
    
    // Setup Base Addresses
    SX1278_WriteRegister(REG_FIFO_TX_BASE_ADDR, 0);
    SX1278_WriteRegister(REG_FIFO_RX_BASE_ADDR, 0);
}

void SX1278_SetTxPower(int level) {
    if (level > 17) {
        if (level > 20) level = 20;
        level -= 3;
        SX1278_WriteRegister(REG_PA_CONFIG, 0x80 | (level & 0x0F));
    } else {
        if (level < 2) level = 2;
        SX1278_WriteRegister(REG_PA_CONFIG, 0x70 | ((level - 2) & 0x0F));
    }
}

void SX1278_SetSpreadingFactor(int sf) {
    if (sf < 6) sf = 6;
    else if (sf > 12) sf = 12;

    uint8_t config2 = SX1278_ReadRegister(REG_MODEM_CONFIG_2);
    config2 = (config2 & 0x0F) | ((sf << 4) & 0xF0);
    SX1278_WriteRegister(REG_MODEM_CONFIG_2, config2);
}

void SX1278_BeginPacket(void) {
    // Put in standby
    SX1278_WriteRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_STDBY);
    // Reset FIFO address
    SX1278_WriteRegister(REG_FIFO_ADDR_PTR, 0);
}

void SX1278_Write(uint8_t *buffer, uint8_t size) {
    SX1278_WriteRegister(0x22, size); // Set Payload Length!
    for (uint8_t i = 0; i < size; i++) {
        SX1278_WriteRegister(REG_FIFO, buffer[i]);
    }
}

void SX1278_EndPacket(void) {
    // Put in TX mode
    SX1278_WriteRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_TX);
    
    // Wait for TX Done (IRQ Flag bit 3)
    while ((SX1278_ReadRegister(REG_IRQ_FLAGS) & 0x08) == 0) {
        HAL_Delay(1);
    }
    
    // Clear IRQ flag
    SX1278_WriteRegister(REG_IRQ_FLAGS, 0x08);
}

void SX1278_Receive(void) {
    SX1278_WriteRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_RX_CONTINUOUS);
}

uint8_t SX1278_ParsePacket(void) {
    uint8_t irqFlags = SX1278_ReadRegister(REG_IRQ_FLAGS);
    
    // Check RxDone flag (bit 6)
    if ((irqFlags & 0x40) != 0) {
        // Clear flag
        SX1278_WriteRegister(REG_IRQ_FLAGS, 0x40);
        
        // Read number of bytes received
        uint8_t nbBytes = SX1278_ReadRegister(REG_RX_NB_BYTES);
        
        // Set FIFO address to current RX address
        SX1278_WriteRegister(REG_FIFO_ADDR_PTR, SX1278_ReadRegister(REG_FIFO_RX_CURRENT_ADDR));
        
        return nbBytes;
    }
    return 0;
}

void SX1278_Read(uint8_t *buffer, uint8_t size) {
    for (uint8_t i = 0; i < size; i++) {
        buffer[i] = SX1278_ReadRegister(REG_FIFO);
    }
}
