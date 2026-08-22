import os
import subprocess
import time

VICTIM_FLAG = "/dev/shm/victim_found.txt"
RADAR_FLAG = "/dev/shm/radar_empty.txt"

def kill_vision():
    print("[MASTER] 🛑 Killing Vision processes...")
    os.system('echo 1 | sudo -S pkill -2 -f thermal_capture >/dev/null 2>&1')
    os.system('pkill -9 -f rgb_producer >/dev/null 2>&1')
    os.system('pkill -9 -f best_victim_detection.py >/dev/null 2>&1')
    
    with open("/home/raitx2/state_transitions.log", "a") as f:
        f.write(f"{time.time()},VISION_KILLED\n")
        
    print("[MASTER] Stopping Robot Movement...")
    os.system("docker exec my_ros2_robot pkill -9 -f 'ros2 topic pub'")
    os.system("docker exec -d my_ros2_robot bash -c 'source /opt/ros/foxy/setup.bash && ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \"{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}\"' >/dev/null 2>&1")
    
    time.sleep(1)

def kill_voice():
    print("[MASTER] 🛑 Killing Voice & Server processes...")
    os.system('pkill -9 -f talk_gemma_rescue.py >/dev/null 2>&1')
    os.system('killall -9 llama-server >/dev/null 2>&1')
    
    with open("/home/raitx2/state_transitions.log", "a") as f:
        f.write(f"{time.time()},VOICE_KILLED\n")
    time.sleep(1)

def start_vision():
    print("\n" + "="*50)
    print("👀 STATE 1: VISION SEARCHING...")
    print("="*50)
    
    with open("/dev/shm/current_state.txt", "w") as f:
        f.write("VISION")
    with open("/home/raitx2/state_transitions.log", "a") as f:
        f.write(f"{time.time()},VISION_START\n")
    if os.path.exists(VICTIM_FLAG):
        os.remove(VICTIM_FLAG)
        
    print("[MASTER] Starting Thermal Capture...")
    subprocess.Popen("echo 1 | sudo -S /home/raitx2/Lepton3_Jetson/build/thermal_capture/thermal_capture window:=false", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    print("[MASTER] Starting RGB Producer...")
    subprocess.Popen("cd /home/raitx2/RescueCameraFusion/build && ./rgb_producer", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    print("[MASTER] Starting YOLO Model (logging to ~/yolo_vision.log)...")
    subprocess.Popen("python3 /home/raitx2/RescueCameraFusion/best_victim_detection.py > /home/raitx2/yolo_vision.log 2>&1", shell=True)

    print("[MASTER] Nav2 Mode Active. Rotation disabled (waiting for Nav2 goals)...")
    # os.system("docker exec -d my_ros2_robot bash -c 'source /opt/ros/foxy/setup.bash && ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \"{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.12}}\"' >/dev/null 2>&1 &")

def start_voice():
    print("\n" + "="*50)
    print("🗣️ STATE 2: CONVERSING...")
    print("="*50)
    
    with open("/dev/shm/current_state.txt", "w") as f:
        f.write("VOICE")
    with open("/home/raitx2/state_transitions.log", "a") as f:
        f.write(f"{time.time()},VOICE_START\n")
    if os.path.exists(RADAR_FLAG):
        os.remove(RADAR_FLAG)
        
    print("[MASTER] Starting Llama Server (Loading weights, takes ~8 seconds)...")
    subprocess.Popen("/home/raitx2/llama5488/build/bin/llama-server -m /media/raitx2/17E3-A141/gemma3-1b-q4km_backup.gguf --gpu-layers 100 --threads 4 --ctx-size 2048", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    time.sleep(8) # Wait for server to bind port
    
    print("[MASTER] Starting Voice Model...")
    subprocess.Popen(["python3", "/home/raitx2/talk_gemma_rescue.py"])

def kill_telemetry():
    print("[MASTER] 🛑 Killing Telemetry...")
    os.system('pkill -f academic_telemetry.py >/dev/null 2>&1')

def main():
    print("===========================================")
    print("🤖 RESCUE AI MASTER LOOP INITIALIZED")
    print("===========================================")
    
    kill_vision()
    kill_voice()
    kill_telemetry()
    
    print("[MASTER] Starting Academic Telemetry...")
    subprocess.Popen(["python3", "/home/raitx2/academic_telemetry.py"])
    time.sleep(1)
    
    current_state = "VISION"
    start_vision()
    
    try:
        while True:
            if current_state == "VISION":
                if os.path.exists(VICTIM_FLAG):
                    print("\n[MASTER] 🎯 VICTIM DETECTED! Stopping cameras and approaching...")
                    kill_vision()
                    os.remove(VICTIM_FLAG)
                    
                    print("[MASTER] 🚶 Approaching Victim (1 meter straight)...")
                    os.system("docker exec -d my_ros2_robot bash -c 'source /opt/ros/foxy/setup.bash && ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \"{linear: {x: 0.2, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}\"' >/dev/null 2>&1 &")
                    time.sleep(5)  # 0.2 m/s * 5 seconds = 1.0 meter
                    
                    print("[MASTER] 🛑 Reached Victim. Stopping.")
                    os.system("docker exec my_ros2_robot pkill -9 -f 'ros2 topic pub'")
                    os.system("docker exec -d my_ros2_robot bash -c 'source /opt/ros/foxy/setup.bash && ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \"{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}\"' >/dev/null 2>&1")
                    
                    print("[MASTER] Transitioning to Voice Mode...")
                    current_state = "VOICE"
                    start_voice()
                    
            elif current_state == "VOICE":
                if os.path.exists(RADAR_FLAG):
                    print("\n[MASTER] 📡 RADAR EMPTY! Transitioning to Vision Mode...")
                    kill_voice()
                    os.remove(RADAR_FLAG)
                    current_state = "VISION"
                    start_vision()
                    
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[MASTER] Shutting down system...")
        kill_vision()
        kill_voice()
        kill_telemetry()
        print("Goodbye!")

if __name__ == "__main__":
    main()
