import cv2
import numpy as np
import os
import time
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit

# ==============================================================
# SPECIALIZED VICTIM DETECTION - BEST VERSION
# ==============================================================
TRT_LOGGER = trt.Logger(trt.Logger.INFO)
ENGINE_PATH = "/home/raitx2/yolo/best_person_yolo11.engine"

def load_engine(engine_path):
    if not os.path.exists(engine_path): return None
    with open(engine_path, "rb") as f, trt.Runtime(TRT_LOGGER) as runtime:
        return runtime.deserialize_cuda_engine(f.read())

engine = load_engine(ENGINE_PATH)
if engine:
    context = engine.create_execution_context()
    inputs, outputs, bindings, stream = [], [], [], cuda.Stream()
    for binding in engine:
        size = trt.volume(engine.get_binding_shape(binding))
        dtype = trt.nptype(engine.get_binding_dtype(binding))
        host_mem = cuda.pagelocked_empty(size, dtype)
        device_mem = cuda.mem_alloc(host_mem.nbytes)
        bindings.append(int(device_mem))
        if engine.binding_is_input(binding):
            inputs.append({'host': host_mem, 'device': device_mem})
        else:
            outputs.append({'host': host_mem, 'device': device_mem})

def preprocess(frame):
    img = cv2.resize(frame, (640, 640))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.transpose((2, 0, 1)).astype(np.float32) / 255.0
    img = np.ascontiguousarray(img)
    return img

def detect(img, inputs, outputs, bindings, stream, context):
    np.copyto(inputs[0]['host'], img.ravel().astype(inputs[0]['host'].dtype))
    cuda.memcpy_htod_async(inputs[0]['device'], inputs[0]['host'], stream)
    context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
    cuda.memcpy_dtoh_async(outputs[0]['host'], outputs[0]['device'], stream)
    stream.synchronize()
    return outputs[0]['host']

def post_process_nms(output, frame, conf_threshold=0.6, nms_threshold=0.4):
    num_anchors = 8400
    num_channels = len(output) // num_anchors
    output = output.reshape(num_channels, num_anchors).transpose()
    boxes, confs = [], []
    for row in output:
        confidence = row[4] 
        if confidence > conf_threshold:
            xc, yc, ww, hh = row[:4]
            x = int((xc - ww/2) * 640 / 640)
            y = int((yc - hh/2) * 480 / 640)
            w = int(ww * 640 / 640)
            h = int(hh * 480 / 640)
            boxes.append([x, y, w, h])
            confs.append(float(confidence))
    indices = cv2.dnn.NMSBoxes(boxes, confs, conf_threshold, nms_threshold)
    final_boxes = []
    if len(indices) > 0:
        for i in indices.flatten():
            final_boxes.append(boxes[i] + [confs[i]])
    return final_boxes

def check_thermal_spot():
    thermal_path = "/dev/shm/live_thermal.jpg"
    if os.path.exists(thermal_path):
        thermal = cv2.imread(thermal_path, cv2.IMREAD_GRAYSCALE)
        if thermal is not None:
            thermal = cv2.rotate(thermal, cv2.ROTATE_180)
            # === معايرة ذاتية ديناميكية (Auto-Calibration) ===
            # حساب المتوسط والانحراف المعياري للبيئة الحالية
            mean_val = np.mean(thermal)
            std_val = np.std(thermal)
            
            # العتبة تتأقلم مع المكان: في الشمس ترتفع، وفي البرد تنخفض بناءً على التباين
            dynamic_thresh = int(mean_val + 1.5 * std_val)
            
            # تقليل الحساسية العامة (الحد الأدنى 165 بدلاً من 150) لتجنب الضجيج في الأماكن الباردة
            # والحد الأعلى 230 لتجنب العمى في الأماكن المشمسة جداً
            final_thresh = max(165, min(dynamic_thresh, 230))
            
            _, thresh = cv2.threshold(thermal, final_thresh, 255, cv2.THRESH_BINARY)
            # إضافة دمج البقع (Morphological Closing)
            kernel = np.ones((15, 15), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rois = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                # تجاهل الحواف لتقليل الضجيج
                if x < 15 or y < 15 or (x+w) > 625 or (y+h) > 465: continue
                if w > 12 and h > 12:
                    rois.append((x, y, w, h))
            return True, rois, thermal
    return False, [], None

def main():
    rgb_path = "/dev/shm/live_rgb.jpg"
    pipeline_out = "appsrc ! videoconvert ! video/x-raw,format=YUY2 ! jpegenc ! tcpserversink host=0.0.0.0 port=5000"
    out_stream = cv2.VideoWriter(pipeline_out, cv2.CAP_GSTREAMER, 0, 15, (1280, 480), True)

    print("--- Rescue AI: BEST PERSON DETECTION VERSION (Active) ---")
    
    stable_frames = 0
    flag_file = "/dev/shm/victim_found.txt"
    if os.path.exists(flag_file):
        os.remove(flag_file)

    while True:
        if os.path.exists(flag_file):
            print("Voice AI Active. YOLO paused to save GPU...")
            time.sleep(2)
            continue
            
        has_thermal, thermal_rois, thermal_img = check_thermal_spot()
        if os.path.exists(rgb_path):
            rgb_frame = cv2.imread(rgb_path)
            if rgb_frame is not None:
                rgb_frame = cv2.resize(rgb_frame, (640, 480))
                
                if has_thermal and thermal_img is not None:
                    thermal_bgr = cv2.cvtColor(thermal_img, cv2.COLOR_GRAY2BGR)
                    thermal_bgr = cv2.resize(thermal_bgr, (640, 480))
                    
                    frame_confirmed = False
                    
                    # الفكرة الهندسية الذكية: تشغيل الذكاء الاصطناعي "فقط" إذا التقطت الكاميرا بقعة حرارية
                    if len(thermal_rois) > 0:
                        img_processed = preprocess(rgb_frame)
                        output = detect(img_processed, inputs, outputs, bindings, stream, context)
                        ai_boxes = post_process_nms(output, rgb_frame, conf_threshold=0.60) 

                        for abox in ai_boxes:
                            ax, ay, aw, ah, conf = abox
                            confirmed = False
                            confirmed_spot = None
                            
                            for troi in thermal_rois:
                                tx, ty, tw, th = troi
                                t_cx, t_cy = tx + tw//2, ty + th//2
                                
                                if (ah > aw * 1.5) and (t_cy > ay + ah * 0.75):
                                    continue 
                                    
                                if (ax <= t_cx <= ax + aw) and (ay <= t_cy <= ay + ah):
                                    confirmed = True
                                    frame_confirmed = True
                                    confirmed_spot = (t_cx, t_cy)
                                    break
                            
                            if confirmed:
                                cv2.rectangle(rgb_frame, (ax, ay), (ax+aw, ay+ah), (0, 255, 0), 3)
                                label = f"PERSON CONFIRMED {conf*100:.1f}%"
                                cv2.putText(rgb_frame, label, (ax, ay-10), 1, 1.2, (0, 255, 0), 2)
                                
                                if confirmed_spot is not None:
                                    a_cx, a_cy = ax + aw//2, ay + ah//2
                                    cv2.line(rgb_frame, (a_cx, a_cy), confirmed_spot, (0, 255, 255), 2)
                                    cv2.circle(rgb_frame, confirmed_spot, 5, (0, 0, 255), -1)
                                    cv2.putText(rgb_frame, "Heat Linked!", (a_cx, a_cy - 20), 1, 1.2, (0, 255, 255), 2)
                                
                    if frame_confirmed:
                        stable_frames += 1
                    else:
                        stable_frames = max(0, stable_frames - 1)
                        
                    if stable_frames >= 5:
                        print("VICTIM CONFIRMED! Launching Voice AI flag...")
                        with open(flag_file, "w") as f:
                            f.write("1")
                        stable_frames = 0
                    
                    for troi in thermal_rois:
                        tx, ty, tw, th = troi
                        cv2.rectangle(thermal_bgr, (tx, ty), (tx+tw, ty+th), (0, 0, 255), 2)
                else:
                    thermal_bgr = np.zeros((480, 640, 3), dtype=np.uint8)

                combined = cv2.hconcat([rgb_frame, thermal_bgr])
                out_stream.write(combined)
        time.sleep(0.01)

if __name__ == "__main__":
    main()
