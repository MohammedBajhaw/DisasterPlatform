# Aşama 2: LIO-SAM Stabilizasyonu ve Kurban Tespit Sistemi

Bu kılavuz, birinci aşamayı tamamlar ve LIO-SAM algoritmasının simülasyonda stabilize edilmesi ve eksiksiz bir kurban tespit sisteminin oluşturulması için uygulanan tüm **doğru ve başarılı** adımları özetler.

---

## 1. Simülasyon Ortamında LIO-SAM Stabilizasyonu

### 1.1 Simülasyon Zamanının Etkinleştirilmesi (use_sim_time)
- **Sorun:** LIO-SAM düğümleri sistem zamanını kullanırken, Gazebo simülasyon saatiyle çalışıyordu. Bu durum verilerin senkronizasyonunu bozuyordu.
- **Çözüm:** `run.launch.py` dosyasında `SetParameter(name='use_sim_time', value=True)` ekleyerek tüm düğümlerde simülasyon zamanını zorunlu kıldık.

### 1.2 Lidar Parametrelerinin Ayarlanması
- **Horizon_SCAN:** VLP-16'nın URDF'deki yatay örneklem sayısıyla eşleşmesi için `440` olarak güncellendi.
- **lidarMinRange:** İç mekan simülasyonlarında yakın duvarları görebilmek için `0.5` metreye düşürüldü.

### 1.3 Hareket Kısıtlamalarının Gevşetilmesi (GTSAM Çökme Çözümü)
- **Sorun:** `z_tollerance` ver `rotation_tollerance` değerlerinin çok dar olması (`0.05`), simülasyon sarsıntıları nedeniyle sistemin çökmesine (IndeterminantLinearSystemException) neden oluyordu.
- **Çözüm:** Bu değerleri `1000.0` yaparak kısıtlamaları kaldırdık ve Lidar'ın serbestçe stabilizasyon yapmasına izin verdik.

### 1.4 İç Mekan Moduna Geçiş (Indoor Mode)
- **Voxel Filtreleri:** Daha ince detaylar için küçültüldü (`odometrySurfLeafSize: 0.2`, `mappingCornerLeafSize: 0.1`).
- **Güncelleme Aralığı:** `mappingProcessInterval: 0.1` saniyeye düşürüldü.
- **Döngü Kapatma (Loop Closure):** Karmaşık koridorlarda haritanın kaymasını önlemek için geçici olarak devre dışı bırakıldı.

### 1.5 Harita Çerçevesinin (map frame) Eklenmesi
- **Sorun:** Orijinal kodda `map -> odom` dönüşümü yayınlanmıyordu.
- **Çözüm:** `run.launch.py` dosyasına `static_transform_publisher` ekleyerek `map` ve `odom` çerçevelerini birbirine bağladık.

---

## 2. Kurban Tespit Sisteminin Kurulması

### 2.1 Gazebo'da ArUco Modellerinin Oluşturulması
- Çalışma alanında 5 adet kurban modeli (`aruco_victim_0` - `aruco_victim_4`) oluşturuldu.
- Her model benzersiz bir ArUco işareti (`DICT_5X5_100`) içeren bir küp olarak tasarlandı.
- Modellerin simülasyonda görünmesi için `linorobot2_gazebo` paketine dahil edildi.

### 2.2 Afet Bölgesi Dünyası (Disaster World)
- `disaster_willow.world` dosyası oluşturuldu. Bu dünya, LIO-SAM için ideal olan **willowgarage** ortamı ile belirlenen noktalara yerleştirilmiş 5 kurbanı birleştirir.

### 2.3 Kurban Tespit Düğümü (victim_detector_node)
`victim_detector_pkg` paketi aşağıdaki özelliklerle geliştirildi:
- **Giriş:** Ön kamera görüntüsü (`/front_camera/image`).
- **Algoritma:** OpenCV ArUco kütüphanesi kullanılarak işaretçiler tespit edilir. Mesafe, işaretçinin bilinen boyutundan (30cm) yola çıkarak `solvePnP` yöntemiyle hesaplanır.
- **Dönüşüm:** Tespit edilen konumlar TF kullanılarak robotun kamerasından dünya haritasına (`map`) dönüştürülür.
- **Çıkış:** RViz'de görüntülenmek üzere `/victim_markers` (MarkerArray) üzerinden **kırmızı küreler** ve **sarı etiketler** yayınlanır.

---

## 3. Çalıştırma Komutları

```bash
# 1. Gazebo ve Afet Dünyası
ros2 launch linorobot2_gazebo gazebo.launch.py world:=.../disaster_willow.world

# 2. LIO-SAM SLAM
ros2 launch lio_sam run.launch.py

# 3. Kurban Tespit Sistemi
ros2 run victim_detector_pkg victim_detector_node --ros-args -p use_sim_time:=true

# 4. Robot Kontrolü (Teleop)
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

## 4. RViz Ayarları
- **Fixed Frame:** `map` olarak ayarlanmalıdır.
- **Displays:** `PointCloud2`, `Path` ve kurbanları görmek için `MarkerArray` (konu: `/victim_markers`) eklenmelidir.
