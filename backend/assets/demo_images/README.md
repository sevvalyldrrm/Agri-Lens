# Demo Görselleri — PlantVillage Veri Seti

Bu klasöre **3 adet** demo görseli koymanız gerekmektedir.

## Beklenen Dosya Adları

| Dosya | Senaryo | PlantVillage Klasörü |
|---|---|---|
| `late_blight.jpg` | Domates Geç Yanıklığı | `Tomato/Tomato_Late_blight/` |
| `early_blight.jpg` | Domates Erken Yanıklığı | `Tomato/Tomato_Early_blight/` |
| `healthy.jpg` | Sağlıklı Domates | `Tomato/Tomato_healthy/` |

## Kaggle'dan İndirme

1. https://www.kaggle.com/datasets/vipoooool/new-plant-diseases-dataset adresine gidin
2. Veri setini indirin ve açın
3. Yukarıdaki klasörlerden birer görsel seçip bu klasöre koyun

## Demo Senaryoları

- **`late_blight.jpg`** + sensör nemi %20 → Gemini **sulama önceliği** verir  
  *(görsel hastalık gösterse de kuraklık stresi daha acildir)*

- **`early_blight.jpg`** + azot 14 mg/kg → Gemini **besin eksikliği önceliği** verir  
  *(sararma hastalıktan değil azot eksikliğinden kaynaklanıyor)*

- **`healthy.jpg`** + normal sensörler → Gemini **temiz rapor** verir

## Görsel Olmadan da Çalışır

Görseller bu klasörde yoksa sistem yalnızca sensör verileriyle analiz yapar.
API'daki `/demo/plant-disease/{scenario}` endpoint'i her iki durumda da çalışır.
