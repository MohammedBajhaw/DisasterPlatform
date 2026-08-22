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

## 🚀 2. نظام المزامنة التلقائية مع GitHub (One-Click Auto-Sync Guide)

هذا التوثيق يشرح كيفية عمل وإعداد نظام المزامنة السريعة، لتتمكن من فهمه وتطبيقه على أي مشروع مستقبلي:

### 📌 كيف تم بناء وإعداد هذا النظام؟ (خطوات إعادة الإعداد من الصفر)

#### الخطوة 1: استخراج رمز الوصول (Personal Access Token - PAT)
بدلاً من كلمات المرور التقليدية التي لم يعد GitHub يدعمها:
1. من المتصفح: اذهب إلى **GitHub** ⬅️ **Settings** ⬅️ **Developer settings** ⬅️ **Personal access tokens (Tokens classic)**.
2. أنشئ توكناً جديداً وحدد خيار **`repo`**، ثم انسخ الرمز الناتج (الذي يبدأ بـ `ghp_`).

#### الخطوة 2: حفظ التوكن في النظام لمنع طلبه في كل مرة (Permanent Credential Storage)
تم تفعيل تخزين الاعتماد عبر الأوامر التالية:
```bash
# 1. إخبار Git بتخزين كلمات المرور محلياً في النظام
git config --global credential.helper store

# 2. حفظ التوكن في ملف ~/.git-credentials بالصيغة:
# https://USERNAME:TOKEN@github.com

# 3. ربط التوكن برابط المستودع المحلي مباشرة:
git remote set-url origin https://<USERNAME>:<TOKEN>@github.com/<USERNAME>/<REPO_NAME>.git
```

#### الخطوة 3: سكربت المزامنة التفاعلي (`sync.sh`)
تم إنشاء سكربت `sync.sh` داخل مجلد المشروع ومنحه صلاحية التشغيل (`chmod +x sync.sh`):
* **كشف التعديلات:** يتحقق تلقائياً هل توجد ملفات جديدة أو معدلة عبر `git status --porcelain`.
* **طلب وصف التعديل (Interactive Prompt):** يطلب منك كتابة تعليق لوصف التعديل، وفي حال الضغط على `Enter` مباشرة يقوم بوضع تاريخ ووقت التعديل كتعليق افتراضي.
* **التنفيذ والرفع:** ينفذ `git add .` و `git commit -m` و `git push origin main` ويعرض تقريراً ملوناً بنجاح العملية.

#### الخطوة 4: إنشاء أمر مختصر عام في النظام (Global Alias)
لتمكين تشغيل السكربت من أي مسار في الـ Terminal دون الحاجة لفتح مجلد المشروع، تمت إضافة السطر التالي إلى نهاية ملف `~/.bashrc`:
```bash
alias sync-robot="/media/mohammed/C60AECF50AECE401/DisasterPlatform_Clean/sync.sh"
```

---

### 💻 طريقة الاستخدام السريع اليومي:

عند إجراء أي تعديل في الكود:
```bash
sync-robot
```
*(أو اكتب `./sync.sh` إذا كنت داخل مجلد المشروع)*

ثم اكتب تعليقك واضغط `Enter`، ليتم الرفع فوراً دون طلب اسم مستخدم أو كلمة مرور! ⚡

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
