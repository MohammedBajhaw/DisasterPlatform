import requests
import subprocess
import os
import sys
import signal
import time
import re
import argparse
import arabic_reshaper
from bidi.algorithm import get_display

# Settings
PIPER_EXE = os.path.expanduser("~/piper/piper/piper")
MODELS_DIR = os.path.expanduser("~/piper")
WHISPER_EXE = os.path.expanduser("~/whisper.cpp/main")
WHISPER_MODEL = os.path.expanduser("~/whisper.cpp/models/ggml-base.bin") # Reverted to Base (Small took 141s)

VOICE_MODELS = {
    "tr": os.path.join(MODELS_DIR, "tr_TR-dfki-medium.onnx"),
    "ar": os.path.join(MODELS_DIR, "ar_JO-kareem-medium.onnx"),
    "en": os.path.join(MODELS_DIR, "en_US-lessac-medium.onnx")
}

# LLM managed dynamically to save Jetson memory
def kill_llm():
    os.system("killall -9 llama-server >/dev/null 2>&1")

def start_llm():
    print("⏳ Loading AI Brain (LLM) into memory...")
    cmd = "/home/raitx2/llama5488/build/bin/llama-server -m /media/raitx2/17E3-A141/gemma3-1b-q4km_backup.gguf --gpu-layers 100 --threads 4 --ctx-size 2048"
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_for_llm():
    # Poll the server until it's ready
    url = "http://localhost:8080/health"
    start = time.time()
    while time.time() - start < 20: # wait up to 20 seconds
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return True
        except:
            time.sleep(0.5)
    return False

def speak(text, lang="tr"):
    # CLEANUP: Remove text between parentheses and asterisks
    clean_text = re.sub(r'\(.*?\)', '', text)
    clean_text = re.sub(r'\*(.*?)\*', '', clean_text)
    clean_text = clean_text.replace("Model:", "").replace("model", "").replace("<end_of_turn>", "").strip()
    
    if not clean_text or len(clean_text) < 2:
        return

    display_text = get_display(arabic_reshaper.reshape(clean_text))
    print("\n[AI]: " + display_text)
    model = VOICE_MODELS.get(lang, VOICE_MODELS["tr"])
    
    piper_cmd = [PIPER_EXE, "--model", model, "--output_raw"]
    aplay_cmd = ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]
    
    try:
        p1 = subprocess.Popen(piper_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(aplay_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p1.stdin.write(clean_text.encode("utf-8"))
        p1.stdin.close()
        p2.wait()
    except Exception as e:
        print("Audio Error: " + str(e))

def record_audio_auto(duration=5):
    wav_file = os.path.expanduser("~/record_raw.wav")
    clean_file = os.path.expanduser("~/record.wav")
    
    print(f"\n🔴 RECORDING (AUTO) for {duration} seconds...")
    cmd = ['arecord', '-D', 'plughw:2,0', '-r', '16000', '-f', 'S16_LE', '-c', '1', '-d', str(duration), wav_file]
    subprocess.run(cmd, stderr=subprocess.DEVNULL)
    
    return wav_file

def transcribe_audio_offline(wav_file, lang="tr"):
    print("✅ Transcribing (BASE MODEL - OFFLINE)...")
    start_time = time.time()
    try:
        # إضافة -t 4 لاستخدام الأنوية بأقصى كفاءة
        cmd = [WHISPER_EXE, "-m", WHISPER_MODEL, "-f", wav_file, "-nt", "-l", lang, "-t", "4"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        transcription = result.stdout.strip()
        latency = time.time() - start_time
        print(f"⏱️  STT Latency: {latency:.2f} seconds")
        
        with open("/home/raitx2/ai_latency.csv", "a") as f:
            f.write(f"STT,{latency:.2f}\n")
        
        # Cleanup temp files
        if os.path.exists(wav_file): os.remove(wav_file)
        raw_file = os.path.expanduser("~/record_raw.wav")
        if os.path.exists(raw_file): os.remove(raw_file)
            
        return transcription
    except Exception as e:
        print("Offline STT Error: " + str(e))
        return ""

def ask_ai(user_text, lang="tr"):
    url = "http://localhost:8080/completion"
    
    if lang == "tr":
        system_instruction = "Sen enkaz altında kalan bir yaralıyı hayatta tutmaya çalışan bir kurtarma robotusun. Ona sadece kısa ve pratik tıbbi tavsiyeler ver.\n\nÖrnek 1:\nUser: Bacağım kanıyor.\nModel: Lütfen kanayan yere elinle sıkıca bastır. Ekipler yolda, uyanık kal.\n\nÖrnek 2:\nUser: Çok korkuyorum.\nModel: Korkma, ben yanındayım. Derin nefes al ve enerjini koru.\n\nÖrnek 3:\nUser: Nefes alamıyorum.\nModel: Ağzını elbiseyle kapat ve yavaşça nefes al. Toz yutmamaya çalış.\n\nŞimdi sen cevap ver:"
    elif lang == "ar":
        system_instruction = "أنت روبوت إنقاذ. أنت تتحدث مباشرة مع المصاب (وليس مع منقذ آخر). خاطبه دائماً بـ 'أنت' (مثل: 'اضغط على جرحك'، 'لا تنم'). لا تقل أبداً 'الشخص المصاب'. لا تقل 'اذهب للطبيب'. أبقِ المصاب مستيقظاً وهدّئ من روعه. اقتصر على جملتين قصيرتين كحد أقصى. تحدث باختصار ولا تصف أفعالك."
    else:
        system_instruction = "You are a Rescue Robot. YOU ARE TALKING DIRECTLY TO THE INJURED VICTIM (not a bystander). Always address them as 'you' (e.g., 'press on your wound', 'stay awake'). NEVER use 'the victim' or 'patient'. NEVER say 'see a doctor'. Keep them awake and calm. Limit response to 2 short sentences. DO NOT describe your actions."

    prompt = "<start_of_turn>user\n{}\n\n{}<end_of_turn>\n<start_of_turn>model\n".format(system_instruction, user_text)
    
    payload = {
        "prompt": prompt,
        "n_predict": 80,
        "temperature": 0.4,
        "stop": ["<end_of_turn>", "user", "model"]
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)
        content = response.json()["content"].strip()
        latency = time.time() - start_time
        print(f"⏱️  LLM Latency: {latency:.2f} seconds")
        
        with open("/home/raitx2/ai_latency.csv", "a") as f:
            f.write(f"LLM,{latency:.2f}\n")
            
        return content
    except Exception as e:
        return "Error: Llama server is not responding."

def main():
    print("\n" + "="*50)
    print("🚑 Rescue AI Voice Active (100% OFFLINE) 🎤")
    print("="*50)
    
    current_lang = "tr"
    print("🚨 VOICE MODE ACTIVATED! Initiating dialogue...")
    speak("Merhaba, ben bir arama kurtarma robotuyum. Seni görüyorum ve buradayım. Lütfen bana durumunu anlat.", "tr")
    
    while True:
        try:
            wav_file = record_audio_auto(duration=5)
            
            # التحقق من الملف
            if not os.path.exists(wav_file) or os.path.getsize(wav_file) < 4000:
                print("No speech detected. Retrying...")
                continue
                
            # 1. Kill LLM to free GPU memory for Whisper
            kill_llm()
            time.sleep(0.5) # Wait for memory to actually free
            
            # 2. Transcribe (now it has full 8GB RAM!)
            user_input = transcribe_audio_offline(wav_file, current_lang)
            
            if not user_input.strip() or len(user_input) < 2:
                print("Could not understand clearly. Retrying...")
                start_llm() # Restart for next loop just in case
                wait_for_llm()
                continue
                
            display_user = get_display(arabic_reshaper.reshape(user_input))
            print("\n[User]: " + display_user)
            
            # 3. Restart LLM to generate response
            start_llm()
            if not wait_for_llm():
                print("Error: LLM Server failed to start.")
                continue
                
            ai_response = ask_ai(user_input, current_lang)
            speak(ai_response, current_lang)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
