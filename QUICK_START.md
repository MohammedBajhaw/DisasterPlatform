# ⚡ دليل العمل السريع (Quick Start & Workflow Guide)

تم تنظيم وهيكلة هذا المشروع ليكون جاهزاً للعمل السريع، التطوير، والمزامنة المباشرة مع GitHub.

---

## 📂 1. هيكلة المشروع (Project Architecture)

المشروع مقسم بدقة إلى المجلدات التالية:

```text
DisasterPlatform_Clean/
├── Host_PC/                 # كود اللابتوب (محطة التحكم الأرضية)
│   ├── dashboard_server.py  # سيرفر التيليمتري واستقبال بيانات LoRa
│   ├── dashboard_ui/        # واجهة الويب التفاعلية
│   ├── start_all.sh         # سكربت تشغيل نوافذ اللابتوب
│   └── nav2_magic.rviz      # إعدادات العرض ثلاثي الأبعاد
│
├── Jetson/                  # كود الروبوت (Jetson TX2)
│   ├── Dockerfile           # بيئة ROS2 Humble المعزولة
│   ├── rescue_master_loop.py# السكربت الرئيسي للرؤية والذكاء الاصطناعي والصوت
│   ├── talk_gemma_rescue.py # موديل التحدث والإنقاذ (Gemma)
│   ├── best_victim_detection.py # خوارزمية كشف الضحايا والكاميرات
│   └── ros2_ws/src/         # حزم ROS2 الأساسية فقط (تم تنظيف الزوائد):
│       ├── disaster_cartographer # حزمة رسم الخرائط 2D SLAM
│       ├── rplidar_ros           # مشغل حساس الليزر RPLidar
│       ├── m-explore-ros2        # حزمة الاستكشاف الذاتي (Explore Lite)
│       └── sensor_markers        # قراءة الحساسات والتدخل الإدراكي
│
├── firmware/                # أكواد المايكروكنترولر (STM32)
│   ├── stm32_blackpill_sensors/  # حساسات اللهب، الغاز، والحرارة
│   ├── stm32_bluepill_lora/      # منصة إرسال واستقبال LoRa
│   └── ...
│
├── docs/                    # تقارير ومستندات المراحل والاختبارات
├── sync.sh                  # 🚀 سكربت المزامنة السريعة مع GitHub بضغطة زر
└── README.md                # التوثيق العام للمستودع
```

---

## 🚀 2. المزامنة التلقائية مع GitHub (One-Click Sync)

لقد تم حفظ التوكن وبيانات الاعتماد نهائياً في النظام. عند إجراء أي تعديل على الأكواد:

### من أي مكان في النظام:
```bash
sync-robot
```

### أو من داخل مجلد المشروع:
```bash
./sync.sh
```

**ما يحدث بعد تشغيل الأمر:**
1. يكتشف السكربت الملفات المعدلة فوراً.
2. يطلب منك كتابة تعليق لوصف التعديل (أو اضغط `Enter` ليضع تاريخ ووقت التعديل تلقائياً).
3. يرفع الكود مباشرة إلى مستودع GitHub دون طلب أي كلمات مرور!

---

## 🤖 3. مرجع أوامر التشغيل الأساسية (Execution Cheat Sheet)

### أ) على اللابتوب (Host PC):
```bash
cd Host_PC
python3 dashboard_server.py
# لفتح واجهة RViz مع Nav2:
ros2 run rviz2 rviz2 -d /opt/ros/humble/share/nav2_bringup/rviz/nav2_default_view.rviz
```

### ب) على الروبوت (Jetson TX2):

#### 1. داخل حاوية Docker (`my_ros2_robot`):
```bash
# قاعدة الروبوت (Kobuki)
ros2 run kobuki_node kobuki_ros_node --ros-args --params-file /kobuki_ws/src/kobuki_ros/kobuki_node/config/kobuki_node_params.yaml

# رسم الخريطة (Cartographer SLAM)
ros2 launch disaster_cartographer cartographer.launch.py

# الاستكشاف التلقائي
ros2 launch explore_lite explore.launch.py

# قراءة الحساسات السلكية والتدخل
ros2 run sensor_markers wired_sensors_node
ros2 run sensor_markers cognitive_intervention_node
```

#### 2. خارج Docker (على نظام الـ Jetson الأصلي):
```bash
# حلقة التحكم والذكاء الاصطناعي
python3 /home/raitx2/disaster_platform/rescue_master_loop.py
```

---

🔗 **رابط المستودع على GitHub:**  
[https://github.com/MohammedBajhaw/DisasterPlatform](https://github.com/MohammedBajhaw/DisasterPlatform)
