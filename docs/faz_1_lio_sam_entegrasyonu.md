# Kapsamlı Kılavuz: LIO-SAM Algoritmasının Linorobot2 Robotu ile Entegrasyonu (Aşama 1)

Bu kılavuz, **3D SLAM (LIO-SAM)** algoritmasının Gazebo simülasyon sistemindeki özel **Linorobot2** robotunuzla birleştirilmesi için uygulanan tüm doğru ve başarılı adımları özetlemektedir.

## 1. Kurulum ve Bağımlılıklar
- **Algoritmanın Yüklenmesi:** LIO-SAM deposunu (`ros2` dalı) çalışma alanınızdaki (`disaster_platform`) `src` klasörüne çektik.
- **GTSAM Matematik Kütüphanesi:** ROS 2 (Humble) depoları bu kütüphanenin varsayılan sistem sürümünü içermese de, `sudo apt install ros-humble-gtsam` komutunu kullanarak ROS 2 için hazırlanmış paketi kurduk.

## 2. Robot Tasarım Ayarları (URDF / Xacro)
- **Dört Çeker Sisteme Geçiş (4WD):** İstikrarlı ve güçlü bir sürüş sağlamak için `~/.bashrc` dosyasında `export LINOROBOT2_BASE=4wd` ortam değişkenini ayarladık.
- **Tutarlı Robot Fizik Ayarları:** Robotun Gazebo içinde yere tam temas etmesini sağlamak ve sarsıntıları azaltmak için URDF dosyalarında şasi (Chassis) ve tekerlek boyutlarını büyüttük.
- **Lidar Sensörü (Velodyne-VLP16):** 
  - `laser.urdf.xacro` içinde, Linorobot2 tabanından gönderilen standart parametreleri kabul edecek şekilde özel bir Lidar tanımı yaptık.
  - Lidar'ı doğrudan robotun üstüne (`base_link`) sabitledik ve ona net bir çerçeve adı verdik: `velodyne`.

## 3. IMU Sensörü Ayarı ve Hızlandırılması
- **Hız Sorunu (Update Rate):** LIO-SAM gibi karmaşık SLAM algoritmaları, 200 Hz'den yüksek çok hızlı anlık sensör okumaları (IMU Preintegration) gerektirir.
- **Çözüm:** Linorobot2'deki `imu.urdf.xacro` dosyasına girerek, robotun ivme ve dönüşlerini tam doğrulukla hesaplamak ve haritanın çökmesini önlemek için güncelleme hızını (Update Rate) `10 Hz`den **`400 Hz`**e çıkardık.

## 4. LIO-SAM Yapılandırma Dosyası (params.yaml)
Yapılandırma dosyasındaki ana faktörler aşağıdaki gibi ayarlandı:
- **Konular (Topics):** Veriler PointCloud için `velodyne_points/` ve IMU dönüş verileri için `imu/data/` konularına yönlendirildi.
- **Hassas Robot Çerçeveleri (Frames):**
  - **Robot Kök Çerçevesi:** Hesaplama çelişkilerini önlemek için `baselinkFrame`, robotun yerdeki kökeni olan `base_footprint` olarak ayarlandı.
  - **Lidar Çerçevesi:** `lidarFrame: velodyne`.
- **Tam Hizalama (Extrinsics):** IMU ve LiDAR robot gövdesine tam paralel monte edildiği için "Birim Matris" (Identity Matrix) kullanıldı.
- **Dikey Sapma İzolasyonu (Z-Tolerance):** Yüzeyde (2D) hareket eden bir robotla çalıştığımız için dikey hareket toleransını (`z_tollerance: 0.05` ve `rotation_tollerance: 0.05`) düşürdük; bu, algoritmayı düz bir harita tutmaya zorladı ve zemin bozulmalarını önledi.

## 5. Koordinat Çatışması Çözümü (TF Conflict) ⚠️
> [!IMPORTANT]
> Görseldeki sarsıntıları ve robotun ekranda uçmasını önlemek için koordinat sisteminde (TF) sorumlulukları birleştirdik:
- **LIO-SAM Ortamında (`run.launch.py`):** ODOM hareketini engelleyen ve tekerleksiz sahte bir robot yayınlayan yayıncıları (`robot_state_publisher` ve `static_transform_publisher`) kaldırdık.
- **Linorobot2 Ortamında (`ekf.yaml`):** Robotun Odom sisteminin yalnızca LIO-SAM tarafından kontrol edilmesi için `robot_localization` filtresinin koordinat yayınlamasını `publish_tf: false` yaparak durdurduk.

Bu düzenleme ile Robot sistemi (Gazebo), sensör yönlendirmesi ve LIO-SAM entegrasyonu tam bir uyum içinde çalışır hale geldi!
