import serial
import time
import sys

# إعداد منفذ الـ USB وسرعة الاتصال (تأكد من تعديل /dev/ttyUSB0 إذا لزم الأمر)
PORT = '/dev/ttyUSB0'
BAUD_RATE = 256000 # السرعة الافتراضية للرادار

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
    print(f"[+] Connected successfully to {PORT}")
except Exception as e:
    print(f"[-] Error connecting to {PORT}: {e}")
    sys.exit(1)

def send_command(cmd_bytes, description):
    print(f"[*] Sending: {description}...")
    ser.write(cmd_bytes)
    time.sleep(0.5) # انتظار استجابة الرادار
    reply = ser.read(ser.in_waiting or 100)
    if reply:
        print(f"    [+] Response received: {reply.hex()}")
    else:
        print("    [-] No response.")

# 1. الدخول إلى وضع الإعدادات (Engineering Mode)
enable_config = bytes.fromhex("FD FC FB FA 04 00 FF 00 01 00 04 03 02 01")
send_command(enable_config, "Enable Configuration Mode")

# دالة لتغيير حساسية البوابة
def set_gate_sensitivity(gate, motion_sens, static_sens):
    # تحويل الأرقام إلى هيكس بترميز Little Endian
    cmd_header = bytes.fromhex("FD FC FB FA 14 00 64 00")
    
    # نوع المتغير 0000 يعني رقم البوابة
    p_gate = bytes.fromhex("00 00") + gate.to_bytes(4, 'little')
    # نوع المتغير 0100 يعني حساسية الحركة
    p_motion = bytes.fromhex("01 00") + motion_sens.to_bytes(4, 'little')
    # نوع المتغير 0200 يعني حساسية السكون
    p_static = bytes.fromhex("02 00") + static_sens.to_bytes(4, 'little')
    
    cmd_footer = bytes.fromhex("04 03 02 01")
    
    full_cmd = cmd_header + p_gate + p_motion + p_static + cmd_footer
    send_command(full_cmd, f"Set Gate {gate} (Motion: {motion_sens}, Static: {static_sens})")

# 2. تعديل الحساسيات (القيم من 0 إلى 100)
# البوابة 0 و 1 نعطيها حساسية 50 لكي تستطيع التقاطك في المسافات الأقل من 140 سم
set_gate_sensitivity(0, 50, 50)
set_gate_sensitivity(1, 50, 50)

# البوابة 2 و 3 نقلل حساسيتها إلى 30 لكي لا تلتقط التنفس الخفيف وتعتبره هدفاً جديداً
set_gate_sensitivity(2, 30, 30)
set_gate_sensitivity(3, 30, 30)

# 3. حفظ الإعدادات والخروج من وضع التهيئة
disable_config = bytes.fromhex("FD FC FB FA 02 00 FE 00 04 03 02 01")
send_command(disable_config, "Save & Exit Configuration Mode")

ser.close()
print("\n[+] Configuration Complete! Restart the radar to apply changes.")
