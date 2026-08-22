#!/usr/bin/env python3
import serial
import struct
import time
import sys
import os

import glob

# Try to auto-detect the STM32 port
def find_port():
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    if ports:
        return ports[0]
    return 'COM3'

PORT = find_port()
BAUD = 9600

# ANSI Colors for beautiful terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    print(f"{Colors.HEADER}{Colors.BOLD}=== DISASTER ROBOT WIRELESS TELEMETRY (HOST) ==={Colors.ENDC}")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        print(f"{Colors.GREEN}Connected to STM32 F1 Receiver on {PORT} at {BAUD} baud.{Colors.ENDC}\n")
    except Exception as e:
        print(f"{Colors.FAIL}Failed to open port {PORT}: {e}{Colors.ENDC}")
        print("Please check your USB connection or change the PORT variable in this script.")
        sys.exit(1)

    buffer = bytearray()
    
    while True:
        try:
            if ser.in_waiting > 0:
                buffer.extend(ser.read(ser.in_waiting))
                
                while len(buffer) >= 20:
                    if buffer[0] == 0xAB and buffer[1] == 0xCD:
                        packet = buffer[:20]
                        payload = packet[2:19]
                        received_checksum = packet[19]
                        
                        calc_checksum = 0
                        for b in payload:
                            calc_checksum ^= b
                            
                        if calc_checksum == received_checksum:
                            rx, ry, flame, human, seq, gas_adc, radar_dist, temp = struct.unpack('<ffBBHHHB', payload)
                            
                            # Build Dashboard string
                            flame_str = f"{Colors.FAIL}🔥 DETECTED{Colors.ENDC}" if flame else f"{Colors.GREEN}Safe{Colors.ENDC}"
                            human_str = f"{Colors.CYAN}🧍 DETECTED ({radar_dist}cm){Colors.ENDC}" if human else "None"
                            gas_str = f"{Colors.FAIL}TOXIC! ({gas_adc}){Colors.ENDC}" if gas_adc >= 650 else f"{Colors.GREEN}Clean ({gas_adc}){Colors.ENDC}"
                            temp_str = f"{Colors.FAIL}HAZARD ({temp}°C){Colors.ENDC}" if temp >= 40 else f"{Colors.GREEN}Normal ({temp}°C){Colors.ENDC}"
                            
                            clear_screen()
                            print(f"{Colors.HEADER}{Colors.BOLD}=== ROBOT LIVE DASHBOARD ==={Colors.ENDC}\n")
                            print(f"📍 {Colors.BOLD}Robot SLAM Position:{Colors.ENDC} X: {rx:.2f}m, Y: {ry:.2f}m")
                            print("-" * 40)
                            print(f"🔥 {Colors.BOLD}Flame Sensor:{Colors.ENDC}       {flame_str}")
                            print(f"🌫️ {Colors.BOLD}Air Quality (Gas):{Colors.ENDC}  {gas_str}")
                            print(f"🌡️ {Colors.BOLD}Temperature:{Colors.ENDC}        {temp_str}")
                            print(f"📡 {Colors.BOLD}Radar (Human):{Colors.ENDC}      {human_str}")
                            print("-" * 40)
                            print(f"{Colors.BLUE}Last Update: {time.strftime('%H:%M:%S')}{Colors.ENDC}")
                            
                            buffer = buffer[20:]
                        else:
                            buffer.pop(0)
                    else:
                        buffer.pop(0)
            else:
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\nExiting telemetry...")
            ser.close()
            sys.exit(0)
        except Exception as e:
            print(f"{Colors.WARNING}Error reading data: {e}{Colors.ENDC}")
            time.sleep(1)

if __name__ == '__main__':
    main()
