
---
# Table of Contents:
1. [Membuat Dataset](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#1-membuat-dataset)
2. [Membuat Tabel `dim_hospitals`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#2-membuat-tabel-dim_hospitals)
3. [Membuat Tabel `hospital_admissions_daily`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#3-membuat-tabel-hospital_admissions_daily)
4. [Membuat Tabel `schema_metadata`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#4-membuat-tabel-schema_metadata)
5. [Membuat Tabel `schema_metadata_embeddings`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#5-membuat-tabel-schema_metadata_embeddings)
6. [Membuat Connection ID](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#6-membuat-connection-id)
7. [Menambahkan Role ke Remote Model Connection's Service Account](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#7-grant-a-role-to-the-remote-model-connections-service-account)
8. [Membuat custom function](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#8-membuat-custom-function)
9. [Membuat remote function di Bigquery](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#9-buat-remote-function-di-bigquery)
10. [Seeding data ke tabel `schema_metadata_embeddings`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#10-seeding-data-ke-tabel-schema_metadata_embeddings)
11. [Train Model](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#11-train-model)
12. [Model Evaluation](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#12-model-evaluation)
13. [Model Inference](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#13-model-inference)
14. [Membuat tabel `query_examples`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#14-membuat-tabel-query_examples)
15. [Membuat tabel `query_examples_embeddings`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#15-membuat-tabel-query_examples_embeddings)
16. [Seeding data ke table `query_examples_embeddings`](https://github.com/ahmadluay9/bmhs-bigquery/blob/master/bigquery.md#16-seeding-data-ke-tabel-query_examples_embeddings)
---
## 1. Membuat Dataset

Perintah ini akan membuat dataset di region Jakarta (`asia-southeast2`).

```sql
CREATE SCHEMA IF NOT EXISTS `healthcare_forecasting_jakarta_v2`
OPTIONS(
  location = 'asia-southeast2',
  description = 'Dummy Healthcare Dataset wilayah Jakarta  ML Forecasting'
);
```

---

## 2. Membuat Tabel `dim_hospitals`
```sql
CREATE OR REPLACE TABLE `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.dim_hospitals`
(
  hospital_id STRING NOT NULL
    OPTIONS(description="ID unik rumah sakit (Format: RS-XXX) bertindak sebagai Primary Key."),
  
  hospital_name STRING NOT NULL
    OPTIONS(description="Nama resmi rumah sakit di wilayah DKI Jakarta."),
  
  hospital_type STRING
    OPTIONS(description="Klasifikasi fungsional dan tingkat operasional rumah sakit (contoh: RSUD Kelas A/B, RS Pusat Rujukan Nasional)."),
  
  total_beds INT64
    OPTIONS(description="Kapasitas total tempat tidur rawat inap yang tersedia secara operasional."),
  
  district STRING
    OPTIONS(description="Wilayah kota administrasi DKI Jakarta lokasi berdirinya rumah sakit (berguna untuk relasi dengan dataset dengue)."),
  
  latitude FLOAT64
    OPTIONS(description="Koordinat garis lintang (latitude) geospasial lokasi fisik rumah sakit."),
  
  longitude FLOAT64
    OPTIONS(description="Koordinat garis bujur (longitude) geospasial lokasi fisik rumah sakit."),

  -- Mendefinisikan Primary Key pada tabel master
  PRIMARY KEY (hospital_id) NOT ENFORCED
)
OPTIONS(
  description="Tabel dimensi master (Lookup) yang menyimpan profil statis dan metadata operasional dari rumah sakit di Jakarta."
);
```

### a. Seeding Data ke Tabel `dim_hospitals`
```sql
INSERT INTO `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.dim_hospitals`
  (hospital_id, hospital_name, hospital_type, total_beds, district, latitude, longitude)
VALUES
  ('RS-001', 'RSUD Pasar Minggu', 'RSUD Kelas B', 350, 'Jakarta Selatan', -6.2890, 106.8315),
  ('RS-002', 'RSUD Tarakan', 'RSUD Kelas A', 500, 'Jakarta Pusat', -6.1715, 106.8116),
  ('RS-003', 'RSUD Cengkareng', 'RSUD Kelas B', 400, 'Jakarta Barat', -6.1432, 106.7324),
  ('RS-004', 'RS Fatmawati', 'RS Pusat Rujukan Nasional Kelas A', 750, 'Jakarta Selatan', -6.2945, 106.7968);
```

## 3. Membuat Tabel `hospital_admissions_daily`
Tabel ini dikonfigurasi dengan:

* Partisi berdasarkan kolom `date` harian (`DAY`).
* Klasterisasi berdasarkan `hospital_name` dan `department` untuk mengoptimalkan performa query.

```sql
CREATE OR REPLACE TABLE `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily`
(
  date DATE NOT NULL
    OPTIONS(description="Tanggal pencatatan admisi harian (kolom kunci partisi)."),
  
  hospital_id STRING NOT NULL
    OPTIONS(description="Foreign Key yang merujuk pada tabel master dim_hospitals."),
  
  hospital_name STRING NOT NULL
    OPTIONS(description="Nama rumah sakit (dipertahankan untuk kemudahan pelaporan langsung)."),
  
  department STRING NOT NULL
    OPTIONS(description="Nama departemen atau poliklinik di rumah sakit (Emergency Room, ICU, Outpatient)."),
  
  admissions_count INT64 NOT NULL
    OPTIONS(description="Jumlah total pasien yang masuk (admitted) pada hari tersebut."),
  
  avg_wait_time_minutes FLOAT64
    OPTIONS(description="Rata-rata waktu tunggu pasien sebelum mendapatkan penanganan medis (menit)."),
  
  temperature_celsius FLOAT64
    OPTIONS(description="Rata-rata suhu harian wilayah Jakarta pada tanggal tersebut."),
  
  rainfall_mm FLOAT64
    OPTIONS(description="Akumulasi curah hujan harian dalam satuan milimeter (mm)."),
  
  air_quality_index INT64
    OPTIONS(description="Indeks Kualitas Udara (AQI) Jakarta yang dicatat pada hari tersebut."),
  
  is_holiday INT64
    OPTIONS(description="Indikator biner hari libur nasional Indonesia (1 = Ya, 0 = Tidak)."),
  
  is_weekend INT64
    OPTIONS(description="Indikator biner akhir pekan Sabtu/Minggu (1 = Ya, 0 = Tidak)."),

  -- Menghubungkan tabel transaksi ke tabel dimensi melalui Foreign Key
  CONSTRAINT fk_hospital_admissions FOREIGN KEY (hospital_id)
    REFERENCES `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.dim_hospitals`(hospital_id) NOT ENFORCED
)
PARTITION BY date
CLUSTER BY hospital_id, department
OPTIONS(
  description="Tabel transaksi/fakta harian yang menyimpan data jumlah admisi pasien rumah sakit di Jakarta beserta parameter cuaca dan hari libur."
);
```

### a. Seeding Data ke Tabel `hospital_admissions_daily`


Query ini akan membaca langsung berkas CSV dari Cloud Storage dan memasukkannya ke dalam tabel yang telah didefinisikan sebelumnya.

```sql
LOAD DATA OVERWRITE `healthcare_forecasting_jakarta_v2.hospital_admissions_daily`
(
  date DATE NOT NULL,
  hospital_id STRING,
  hospital_name STRING NOT NULL,
  department STRING NOT NULL,
  admissions_count INT64 NOT NULL,
  avg_wait_time_minutes FLOAT64,
  temperature_celsius FLOAT64,
  rainfall_mm FLOAT64,
  air_quality_index INT64,
  is_holiday INT64,
  is_weekend INT64
)
PARTITION BY date
CLUSTER BY hospital_id, department
FROM FILES (
  format = 'CSV',
  uris = ['gs://healthcare-forecasting-jakarta-bucket/hospital_admissions_daily.csv'],
  skip_leading_rows = 1
);
```

#### Penjelasan Parameter:

* **`OVERWRITE`**: Mengosongkan data lama di dalam tabel terlebih dahulu sebelum memasukkan data baru (berfungsi seperti *Write Truncate*). Jika Anda hanya ingin menambahkan data baru tanpa menghapus data yang sudah ada, ganti kata `OVERWRITE` menjadi **`APPEND`**:
```sql
LOAD DATA APPEND `healthcare_forecasting_jakarta_v2.hospital_admissions_daily` ...

```


* **`format = 'CSV'`**: Menentukan bahwa berkas sumber berformat CSV sesuai dengan generator data yang kita buat.
* **`uris`**: Lokasi penyimpanan berkas di GCS (disesuaikan dengan konfigurasi `BUCKET_NAME` dan `GCS_BLOB_NAME` pada berkas di **Canvas**).
* **`skip_header = 1`**: Mengabaikan baris pertama pada CSV karena baris tersebut merupakan nama kolom (header).

## 4. Membuat Tabel `schema_metadata`

```sql
CREATE OR REPLACE TABLE `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata`
(
  table_name STRING NOT NULL
    OPTIONS(description="Nama fisik tabel di dalam dataset BigQuery."),
  
  description STRING NOT NULL
    OPTIONS(description="Deskripsi fungsional lengkap mengenai isi dan kegunaan tabel tersebut."),
  
  ddl STRING NOT NULL
    OPTIONS(description="Pernyataan DDL (Data Definition Language) lengkap untuk merekonstruksi tabel ini."),
  
  sample_data JSON
    OPTIONS(description="Dokumen atau array JSON berisi sampel data representatif (mock data) dari tabel."),

  -- Mendefinisikan Primary Key pada tabel skema
  PRIMARY KEY (table_name) NOT ENFORCED
)
OPTIONS(
  description="Tabel katalog terpadu penyimpan metadata skema dataset, DDL, dan sampel data JSON."
);
```

```sql
-- 2. Seeding data
INSERT INTO `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata`
  (table_name, description, ddl, sample_data)
VALUES
  ('dim_hospitals', 
   'Tabel dimensi master (Lookup) yang menyimpan profil statis dan metadata operasional dari rumah sakit di Jakarta.', 
   'CREATE OR REPLACE TABLE dim_hospitals (hospital_id STRING NOT NULL OPTIONS(description="ID unik rumah sakit (Format: RS-XXX) bertindak sebagai Primary Key."), hospital_name STRING NOT NULL OPTIONS(description="Nama resmi rumah sakit di wilayah DKI Jakarta."), hospital_type STRING OPTIONS(description="Klasifikasi fungsional dan tingkat operasional rumah sakit (contoh: RSUD Kelas B, RS Pusat Rujukan Nasional)."), total_beds INT64 OPTIONS(description="Kapasitas total tempat tidur rawat inap yang tersedia secara operasional."), district STRING OPTIONS(description="Wilayah kota administrasi DKI Jakarta lokasi berdirinya rumah sakit (berguna untuk relasi dengan dataset dengue)."), latitude FLOAT64 OPTIONS(description="Koordinat garis lintang (latitude) geospasial lokasi fisik rumah sakit."), longitude FLOAT64 OPTIONS(description="Koordinat garis bujur (longitude) geospasial lokasi fisik rumah sakit."), PRIMARY KEY (hospital_id) NOT ENFORCED) OPTIONS(description="Tabel dimensi master (Lookup) yang menyimpan profil statis dan metadata operasional dari rumah sakit di Jakarta.");', 
   JSON '[{"hospital_id": "RS-004", "hospital_name": "RS Fatmawati", "hospital_type": "RS Pusat Rujukan Nasional Kelas A", "total_beds": 750, "district": "Jakarta Selatan", "latitude": -6.2945, "longitude": 106.7968}, {"hospital_id": "RS-003", "hospital_name": "RSUD Cengkareng", "hospital_type": "RSUD Kelas B", "total_beds": 400, "district": "Jakarta Barat", "latitude": -6.1432, "longitude": 106.7324}, {"hospital_id": "RS-001", "hospital_name": "RSUD Pasar Minggu", "hospital_type": "RSUD Kelas B", "total_beds": 350, "district": "Jakarta Selatan", "latitude": -6.289, "longitude": 106.8315}]'
  ),
  ('hospital_admissions_daily', 
   'Tabel transaksi/fakta harian yang menyimpan data jumlah admisi pasien rumah sakit di Jakarta beserta parameter cuaca dan hari libur.', 
   'CREATE OR REPLACE TABLE hospital_admissions_daily (date DATE NOT NULL OPTIONS(description="Tanggal pencatatan admisi harian (kolom kunci partisi)."), hospital_id STRING NOT NULL OPTIONS(description="Foreign Key yang merujuk pada tabel master dim_hospitals."), hospital_name STRING NOT NULL OPTIONS(description="Nama rumah sakit (dipertahankan untuk kemudahan pelaporan langsung)."), department STRING NOT NULL OPTIONS(description="Nama departemen atau poliklinik di rumah sakit (Emergency Room, ICU, Outpatient)."), admissions_count INT64 NOT NULL OPTIONS(description="Jumlah total pasien yang masuk (admitted) pada hari tersebut."), avg_wait_time_minutes FLOAT64 OPTIONS(description="Rata-rata waktu tunggu pasien sebelum mendapatkan penanganan medis (menit)."), temperature_celsius FLOAT64 OPTIONS(description="Rata-rata suhu harian wilayah Jakarta pada tanggal tersebut."), rainfall_mm FLOAT64 OPTIONS(description="Akumulasi curah hujan harian dalam satuan milimeter (mm)."), air_quality_index INT64 OPTIONS(description="Indeks Kualitas Udara (AQI) Jakarta yang dicatat pada hari tersebut."), is_holiday INT64 OPTIONS(description="Indikator biner hari libur nasional Indonesia (1 = Ya, 0 = Tidak)."), is_weekend INT64 OPTIONS(description="Indikator biner akhir pekan Sabtu/Minggu (1 = Ya, 0 = Tidak)."), CONSTRAINT fk_hospital_admissions FOREIGN KEY (hospital_id) REFERENCES dim_hospitals(hospital_id) NOT ENFORCED) PARTITION BY date CLUSTER BY hospital_id, department OPTIONS(description="Tabel transaksi/fakta harian yang menyimpan data jumlah admisi pasien rumah sakit di Jakarta beserta parameter cuaca dan hari libur.");', 
   JSON '[{"date": "2022-11-24", "hospital_id": "RS-001", "hospital_name": "RSUD Pasar Minggu", "department": "ICU", "admissions_count": 9, "avg_wait_time_minutes": 20.0, "temperature_celsius": 29.0, "rainfall_mm": 2.5, "air_quality_index": 112, "is_holiday": 0, "is_weekend": 0}, {"date": "2022-11-24", "hospital_id": "RS-001", "hospital_name": "RSUD Pasar Minggu", "department": "Outpatient", "admissions_count": 82, "avg_wait_time_minutes": 46.4, "temperature_celsius": 29.0, "rainfall_mm": 2.5, "air_quality_index": 112, "is_holiday": 0, "is_weekend": 0}, {"date": "2022-11-24", "hospital_id": "RS-001", "hospital_name": "RSUD Pasar Minggu", "department": "Emergency Room", "admissions_count": 38, "avg_wait_time_minutes": 30.0, "temperature_celsius": 29.0, "rainfall_mm": 2.5, "air_quality_index": 112, "is_holiday": 0, "is_weekend": 0}]'
  );
```

## 5. Membuat Tabel `schema_metadata_embeddings`
```sql
CREATE OR REPLACE TABLE `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata_embeddings`
(
  content STRING
    OPTIONS(description="Dokumen semantik terstruktur (Table, Description, Definition) yang di-embed secara utuh."),
  
  embedding ARRAY<FLOAT64>
    OPTIONS(description="Representasi vektor (embedding) dari isi kolom content untuk kebutuhan semantic search.")
)
OPTIONS(
  description="Tabel penyimpan dokumen semantik terstruktur beserta vektor embedding-nya untuk mendukung pencarian skema tabel secara semantik."
);
```

## 6. Membuat Connection ID
Di BigQuery, **Cloud Resource Connection** berperan sebagai jembatan pengubung (*secure delegation*) antara BigQuery dengan Agent Platform API.

Berikut adalah detail peran utama dari *connection* ini:

1. **Authentication & Authorization Bridge**
BigQuery secara *native* tidak memiliki akses langsung untuk memanggil layanan di luar engine SQL-nya. *Connection* ini menjembatani hal tersebut dengan menyediakan sebuah **GCP-managed Service Account** unik yang mewakili sesi query Anda untuk melakukan *handshake* dengan layanan Agent Platform.
2. **Security & IAM Role Binding**
Agar proses pembuatan *embeddings* berhasil, *Service Account* yang dihasilkan oleh *connection* tersebut harus diberikan **IAM Role** berupa `Agent Platform User` (`roles/aiplatform.user`). Dengan begitu, setiap *API call* yang dipicu oleh fungsi `AI.EMBED` lolos proses verifikasi keamanan GCP tanpa Anda harus menuliskan *credentials* atau *API keys* secara manual di dalam SQL script (*hardcoded*).
3. **Secure Data Pipeline (Payload Transfer)**
Saat Anda menjalankan fungsi `AI.EMBED`, *connection* ini bertugas mengirimkan *text payload* dari tabel BigQuery Anda ke *endpoint* model `gemini-embedding-001` di Agent Platform, kemudian menerima kembali respon berupa vektor high-dimensional (`ARRAY<FLOAT64>`) untuk disimpan ke dalam tabel target secara aman.

```sql
CREATE CONNECTION IF NOT EXISTS `YOUR_PROJECT_NAME.asia-southeast2.agent_platform_conn`
OPTIONS (
  connection_type = "CLOUD_RESOURCE"
);
```

## 7. Menambahkan Role ke Remote Model Connection's Service Account
- Buka `Connections`, pilih nama `Connection ID` yang kita buat
- Copy `Service account id` contoh : `bqcx-158103152291-12x4@gcp-sa-bigquery-condel.iam.gserviceaccount.com`
- lalu jalankan command berikut:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_NAME \
    --member="serviceAccount:bqcx-000000000-xxxx@gcp-sa-bigquery-condel.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user" \
    --condition=None
```
- Fungsi: Memberikan otorisasi kepada Service Account koneksi untuk memanggil model-model Agent Platform (seperti gemini-embedding-001).

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_NAME \
    --member="serviceAccount:bqcx-000000000-xxxx@gcp-sa-bigquery-condel.iam.gserviceaccount.com" \
    --role="roles/cloudfunctions.invoker" \
    --condition=None
```

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_NAME \
    --member="serviceAccount:bqcx-000000000-xxxx@gcp-sa-bigquery-condel.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --condition=None
```

- BigQuery membutuhkan izin Cloud Functions Invoker dan Cloud Run Invoker agar dapat mengirimkan payload ke function Anda.

## 8. Membuat custom function
Pada tahap ini, Anda membangun serverless backend yang bertindak sebagai perantara antara BigQuery dan Agent Platform.

```
mkdir text-embeddings
cd text-embeddings
touch main.py requirements.txt
```

### main.py
>[Contoh python script untuk text embeddings](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-text-embeddings )

```python
import json
import os
import functions_framework

# Mengatur environment variables agar SDK menggunakan Agent Platform (Enterprise) di region us-central1
os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = "YOUR_PROJECT_NAME"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

from google import genai
from google.genai.types import EmbedContentConfig

# Inisialisasi client Google Gen AI SDK
client = genai.Client()

@functions_framework.http
def get_vertex_embeddings(request):
    """
    Cloud Function HTTP yang menerima payload batch dari BigQuery Remote Function,
    meminta text embedding menggunakan SDK google-genai terbaru ke Agent Platform,
    dan mengembalikan hasilnya kembali ke BigQuery.
    """
    try:
        request_json = request.get_json(silent=True)
        if not request_json or "calls" not in request_json:
            return json.dumps({"replies": []}), 400, {"Content-Type": "application/json"}

        calls = request_json.get("calls", [])
        replies = []

        # BigQuery mengirimkan data dalam bentuk batch (array di dalam array)
        # Ambil teks yang akan diekstrak embedding-nya
        texts_to_embed = [call[0] for call in calls if call and len(call) > 0]
        
        if not texts_to_embed:
            return json.dumps({"replies": []}), 200, {"Content-Type": "application/json"}

        # Membaca konfigurasi dinamis yang dikirimkan oleh BQ Remote Function (userDefinedContext)
        user_context = request_json.get("userDefinedContext", {})
        model_name = user_context.get("model", "gemini-embedding-001")
        output_dim_str = user_context.get("output_dimensionality", "768")
        
        try:
            output_dim = int(output_dim_str)
        except ValueError:
            output_dim = 768

        # Melakukan panggilan batch embedding ke model gemini-embedding-001
        response = client.models.embed_content(
            model=model_name,
            contents=texts_to_embed,
            config=EmbedContentConfig(
                output_dimensionality=output_dim
            )
        )

        # Memetakan hasil vektor kembali ke format balasan BigQuery
        if response.embeddings:
            for embedding in response.embeddings:
                replies.append(embedding.values)
        else:
            raise Exception("Model tidak mengembalikan data embedding.")

        # Mengembalikan response berformat JSON yang diharapkan oleh BigQuery
        return json.dumps({"replies": replies}), 200, {"Content-Type": "application/json"}

    except Exception as e:
        # Mengembalikan pesan error ke log BigQuery jika terjadi kendala teknis
        return json.dumps({"errorMessage": str(e)}), 400, {"Content-Type": "application/json"}
```

- Inisialisasi Client: Mengatur environment SDK agar mengarah ke proyek `YOUR_PROJECT_NAME` di region `us-central1` untuk pemanggilan Agent Platform API.

- Parsing Batch Payload: BigQuery tidak mengirim data satu per satu, melainkan dalam bentuk batch array di dalam JSON payload berupa parameter `calls` (misal: `{"calls": [["teks1"], ["teks2"]], ...}`).

- Dynamic Context Parsing: Kode Anda sangat bagus karena mampu membaca konfigurasi dinamis yang dikirimkan oleh pengguna BigQuery melalui `userDefinedContext` (seperti nama model dan dimensi output).

- API Call: Memanggil SDK `client.models.embed_content` secara kolektif untuk seluruh teks dalam batch demi efisiensi kuota API dan kecepatan.

- Response Contract Mapping: BigQuery mengharuskan format balasan yang sangat spesifik berupa `{"replies": [[v1, v2, ...], [v1, v2, ...]]}`. Logika di akhir fungsi bertugas menyusun ulang struktur array vektor embeddings agar sesuai dengan kontrak respon BigQuery tersebut.

#### requirements.txt
Mendefinisikan library Python yang dibutuhkan.
```
functions-framework==3.10.1
google-genai==2.8.0
```

### deploy cloud function
```
gcloud functions deploy get-vertex-embeddings \
  --gen2 \
  --runtime=python314 \
  --region=asia-southeast2 \
  --source=. \
  --entry-point=get_vertex_embeddings \
  --trigger-http \
  --no-allow-unauthenticated
```

- `--gen2`: Menggunakan Cloud Functions generasi kedua yang berbasis Cloud Run untuk konkurensi performa yang lebih tinggi.

- `--region=asia-southeast2`: Menempatkan server komputasi Cloud Function di Jakarta, berdekatan dengan dataset BigQuery Anda untuk menghindari isu transfer data cross-region network latency.

- `--no-allow-unauthenticated`: Mengunci fungsi agar bersifat privat. Hanya sistem internal Google Cloud (seperti BigQuery Connection Anda yang telah diberi izin Invoker di Step 2) yang dapat memanggil URL fungsi ini.

```
$ gcloud functions describe get-vertex-embeddings \
  --gen2 \
  --region=asia-southeast2 \
  --format="value(serviceConfig.uri)"
```

Perintah terakhir (`gcloud functions describe ...`) digunakan untuk mengambil alamat URI/URL HTTP resmi dari fungsi yang baru dideploy. URL inilah yang nantinya akan Anda daftarkan di BigQuery sebagai Remote Function.

## 9. Buat remote function di Bigquery 
```sql
CREATE OR REPLACE FUNCTION `healthcare_forecasting_jakarta_v2.get_text_embedding`(text STRING)
RETURNS JSON
REMOTE WITH CONNECTION `YOUR_PROJECT_NAME.asia-southeast2.agent_platform_conn`
OPTIONS (
  -- URL .run.app asli dari Cloud Function Gen 2 Anda (contoh:https://get-vertex-embeddings-g2u45nvkda-et.a.run.app)
  endpoint = 'https://get-vertex-embeddings-xxxxxxxx-et.a.run.app',

  user_defined_context = [
    ("model", "gemini-embedding-001"),
    ("output_dimensionality", "768")
  ]
);
```
Fungsi ini bertindak sebagai jembatan langsung di dalam BigQuery agar Anda bisa memanggil kode Python di Cloud Function yang telah di-deploy sebelumnya langsung menggunakan query SQL standar.

Berikut adalah penjelasan detail untuk setiap baris dari query SQL tersebut:

---

#### 1. Function Declaration

```sql
CREATE OR REPLACE FUNCTION `healthcare_forecasting_jakarta_v2.get_text_embedding`(text STRING)
RETURNS JSON

```

* **`CREATE OR REPLACE FUNCTION`**: Membuat fungsi baru bernama `get_text_embedding` di dalam dataset Anda. Jika fungsi dengan nama tersebut sudah ada, perintah ini akan menimpa (*overwrite*) dengan definisi terbaru.
* **`(text STRING)`**: Mendefinisikan parameter input. Fungsi ini menerima satu kolom bertipe `STRING` (yaitu teks deskripsi yang ingin diubah menjadi *embeddings*).
* **`RETURNS JSON`**: Menentukan tipe data hasil kembalian (*return type*). Karena Cloud Function Anda mengembalikan struktur JSON kompleks (termasuk *replies* vektor atau kemungkinan *error message*), BigQuery akan menangkap dan menyimpannya sebagai tipe data `JSON`.

---

#### 2. Connection Binding

```sql
REMOTE WITH CONNECTION `YOUR_PROJECT_NAME.asia-southeast2.agent_platform_conn`

```

* **`REMOTE WITH CONNECTION`**: Klausa kunci yang memberi tahu BigQuery bahwa ini bukanlah SQL UDF biasa yang dieksekusi di dalam engine internal BigQuery, melainkan sebuah **Remote Function** yang bergantung pada eksekusi server eksternal.
* **`YOUR_PROJECT_NAME.asia-southeast2.agent_platform_conn`**: Menunjuk ke *Cloud Resource Connection* regional (`asia-southeast2`) yang telah Anda buat di langkah sebelumnya. BigQuery akan menggunakan *Service Account* bawaan dari koneksi ini (yang sudah diberi izin `roles/cloudfunctions.invoker` dan `roles/run.invoker`) untuk menembus autentikasi Cloud Function secara aman.

---

#### 3. Konfigurasi Endpoint (`OPTIONS`)

```sql
OPTIONS (
  endpoint = 'https://get-vertex-embeddings-xxxxxx-et.a.run.app',

```

* **`endpoint`**: Parameter wajib yang diisi dengan URL HTTPS fisik dari Cloud Function (2nd Gen) yang Anda dapatkan setelah proses *deploy* di langkah sebelumnya. BigQuery akan mengirimkan data baris tabel Anda dalam format *HTTP POST request* (secara otomatis di-package dalam bentuk *batch*) ke alamat URL ini.

---

#### 4. Pengiriman Parameter Dinamis (`user_defined_context`)

```sql
  user_defined_context = [
    ("model", "gemini-embedding-001"),
    ("output_dimensionality", "768")
  ]
);

```

* **`user_defined_context`**: Fitur BigQuery yang sangat fleksibel untuk mengirimkan metadata tambahan berupa pasangan key-value *custom* ke dalam HTTP *request payload*.
* **Cara Kerjanya**: Ketika query ini dijalankan, BigQuery menyisipkan nilai ini ke dalam JSON *request* di bawah field `"userDefinedContext"`.
* **Relasi ke Backend**: Di dalam kode Python Cloud Function Anda (`main.py`), terdapat baris berikut yang bertugas membaca konteks dinamis ini:
```python
user_context = request_json.get("userDefinedContext", {})
model_name = user_context.get("model", "gemini-embedding-001")

```

Ini memungkinkan Anda untuk mengganti model Agent Platform atau jumlah dimensi output tanpa harus melakukan *re-deploy* kode Python pada Cloud Function. Anda cukup mengubah opsi `user_defined_context` langsung dari sisi SQL BigQuery.

## 10. Seeding data ke tabel `schema_metadata_embeddings`

```sql
INSERT INTO `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata_embeddings` (content, embedding)
WITH prepared_docs AS (
  SELECT 
    CONCAT(
      'Table: YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.', table_name, '\n',
      'Description: ', description, '\n',
      'Definition: ', ddl
    ) AS doc_content
  FROM 
    `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata`
)
SELECT 
  doc_content AS content,
  ARRAY(
    SELECT LAX_FLOAT64(val) 
    FROM UNNEST(
      JSON_QUERY_ARRAY(
        `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.get_text_embedding`(doc_content)
      )
    ) AS val
  ) AS embedding
FROM 
  prepared_docs;
```

Berikut adalah penjelasan detail langkah demi langkah dari query tersebut:
---

### 1. Deklarasi Konstruksi Penyusunan Teks (`WITH prepared_docs AS ...`)

Kueri ini menggunakan fitur **CTE (Common Table Expression)** bernama `prepared_docs` sebagai langkah awal:

```sql
WITH prepared_docs AS (
  SELECT 
    CONCAT(
      'Table: YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.', table_name, '\n',
      'Description: ', description, '\n',
      'Definition: ', ddl
    ) AS doc_content
  FROM 
    `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata`
)

```

* **Peran**: Menyusun dokumen teks mentah terstruktur yang kaya konteks (*context-rich semantic document*).
* **Fungsi `CONCAT(...)**`: Menggabungkan string statis dengan data dinamis dari tabel `schema_metadata`. Format penggabungan ini meniru standar indeksasi sistem pencarian semantik (RAG) profesional:
* Menuliskan nama lengkap tabel (*Fully Qualified Name*).
* Menuliskan deskripsi fungsional tabel (`description`).
* Menyertakan sintaks DDL pembuatan tabel asli (`ddl`) untuk memberikan konteks skema fisik kepada model.


* **Hasil**: Menghasilkan tabel virtual sementara dengan kolom tunggal bernama `doc_content` yang berisi string teks multi-baris (dilengkapi pemisah karakter baris baru `\n`).

---

### 2. Pemanggilan Remote Function (`get_text_embedding`)

```sql
`YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.get_text_embedding`(doc_content)

```

* **Peran**: Mengirimkan teks semantik yang sudah disatukan (`doc_content`) di dalam CTE ke infrastruktur AI eksternal Anda.
* **Proses**: BigQuery mengirimkan string tersebut sebagai HTTP payload ke Cloud Function (2nd Gen) regional Jakarta. Di sana, kode Python dengan SDK `google-genai` akan memanggil model `gemini-embedding-001` di Vertex AI.
* **Output**: Model Vertex AI mengembalikan representasi array numerik dalam bentuk tipe data **`JSON`** BigQuery (contoh: `[0.0125, -0.9842, 0.4351, ...]`).

---

### 3. Ekstraksi dan Konversi Array JSON (`JSON_QUERY_ARRAY`, `UNNEST`, `LAX_FLOAT64`)

Karena output dari *remote function* bertipe data `JSON`, sedangkan kolom target pada tabel database adalah `ARRAY<FLOAT64>`, maka diperlukan konversi tipe data yang aman dan tangguh melalui tahapan berikut:

* **`JSON_QUERY_ARRAY(...)`**: Mengurai objek atau dokumen `JSON` pembungkus hasil API menjadi sebuah tipe array SQL dari elemen-elemen JSON individual.
* **`UNNEST(...) AS val`**: Memecah (*flatten*) array JSON tersebut menjadi baris-baris skalar individual dalam sebuah tabel virtual satu kolom bernama `val`. Setiap baris mewakili satu dimensi dari vektor embedding.
* **`LAX_FLOAT64(val)`**: Mengonversi setiap baris nilai skalar JSON tersebut menjadi tipe data numerik riil **`FLOAT64`** BigQuery. Fungsi `LAX_*` dipilih karena sangat aman; jika ada nilai anomali atau null, ia akan mengembalikan `NULL` secara toleran alih-alih membatalkan seluruh transaksi query (*non-blocking/error-tolerant*).

---

### 4. Penyusunan Kembali dan Penyimpanan Akhir (`ARRAY(...) AS embedding`)

```sql
INSERT INTO `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.schema_metadata_embeddings` (content, embedding)
SELECT 
  doc_content AS content,
  ARRAY( ... ) AS embedding
FROM 
  prepared_docs;

```

* **`ARRAY(...)`**: Konstruktor ini bertugas merangkum kembali seluruh baris numerik `FLOAT64` yang telah dikonversi secara individual tadi ke dalam satu kesatuan objek **`ARRAY<FLOAT64>`** utuh BigQuery.
* **`INSERT INTO`**: Menyimpan dua data tersebut secara permanen ke dalam tabel target:
1. Kolom `content` diisi dengan teks semantik lengkap dari CTE (`doc_content`).
2. Kolom `embedding` diisi dengan array vektor `ARRAY<FLOAT64>` hasil konversi akhir.



---

#### Manfaat Utama dari Desain Kueri Ini:

* **Rich Context Semantic Search**: Model AI tidak hanya melakukan *pencarian kata kunci*, melainkan memahami keterkaitan logis antara nama tabel, deskripsi, dan struktur kolom DDL-nya secara menyeluruh saat Anda melakukan pencarian menggunakan fungsi `VECTOR_SEARCH` nantinya.
* **Optimalisasi Biaya API**: Penggunaan CTE (`prepared_docs`) memastikan string dokumen hanya digabungkan sekali di memori BigQuery sebelum dikirim ke Vertex AI, menghindari pemrosesan ganda (*redundant operations*).

---

## 11. Train Model

```sql
CREATE OR REPLACE MODEL `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_arima`
OPTIONS(
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'date',
  time_series_data_col = 'admissions_count',
  time_series_id_col = ['hospital_id', 'department'],
  holiday_region = 'ID',
  clean_spikes_and_dips = TRUE,
  adjust_step_changes = TRUE
) AS
SELECT 
  date,
  hospital_id,
  department,
  admissions_count
FROM 
  `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily`
WHERE 
  date <= '2026-05-01';
```

Query ini bertujuan untuk **membuat dan melatih model forecasting time-series** menggunakan algoritma bawaan BigQuery, yaitu **ARIMA_PLUS**.

Berikut adalah penjelasan detail untuk setiap bagian dari query SQL tersebut:

---

### 1. Inisialisasi Pembuatan Model

```sql
CREATE OR REPLACE MODEL `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_arima`

```

* **Fungsi**: Membuat model baru bernama `hospital_admissions_arima` di dalam dataset `healthcare_forecasting_jakarta_v2`.
* **Sifat**: Jika model dengan nama tersebut sudah ada, klausa `OR REPLACE` akan menimpanya (menggantinya dengan versi yang baru dilatih).

---

### 2. Opsi Konfigurasi Model (`OPTIONS`)

Bagian ini mengatur bagaimana algoritma BigQuery ML harus memproses data deret waktu Anda.

* **`model_type = 'ARIMA_PLUS'`**
* Ini adalah algoritma *time-series* unggulan di BigQuery. Berbeda dengan ARIMA standar, `ARIMA_PLUS` secara otomatis melakukan serangkaian prapemrosesan (*preprocessing*) yang kompleks seperti mendeteksi tren, pola musiman (harian, mingguan, tahunan), mendeteksi anomali/outlier, dan memperhitungkan hari libur.


* **`time_series_timestamp_col = 'date'`**
* Menentukan kolom mana yang menjadi penunjuk waktu (sumbu X). Di sini kita menggunakan kolom `date`.


* **`time_series_data_col = 'admissions_count'`**
* Menentukan variabel numerik yang ingin kita ramalkan/prediksi nilainya di masa depan (jumlah admisi/pasien masuk).


* **`time_series_id_col = ['hospital_name', 'department']`**
* **Ini adalah fitur yang sangat kuat.** Alih-alih membuat satu model global untuk semua rumah sakit, BigQuery akan secara otomatis membuat **banyak model time-series terpisah** untuk setiap kombinasi unik dari nama rumah sakit dan departemennya (misalnya: model khusus untuk *RSUD Tarakan - Emergency Room*, model khusus untuk *RS Fatmawati - ICU*, dll.). Semuanya berjalan paralel hanya dalam satu query tunggal.


* **`holiday_region = 'ID'`**
* Mengintegrasikan kalender hari libur nasional **Indonesia (ID)** yang sudah disediakan oleh Google. BigQuery akan otomatis menyesuaikan prediksi naik-turunnya jumlah pasien berdasarkan efek hari libur nasional di Indonesia (seperti Lebaran, Tahun Baru, dll.).


* **`clean_spikes_and_dips = TRUE`**
* Mengaktifkan pembersihan data pencilan otomatis. Jika ada lonjakan (spikes) atau penurunan (dips) ekstrem yang bersifat anomali sementara (misalnya ada gangguan pencatatan sistem), model akan membersihkannya terlebih dahulu agar tidak merusak akurasi tren jangka panjang.


* **`adjust_step_changes = TRUE`**
* Menginstruksikan model untuk mendeteksi perubahan baseline permanen (*step changes*). Contoh: Jika sebuah rumah sakit tiba-tiba membuka gedung baru sehingga kapasitasnya melonjak permanen, model akan menyesuaikan baseline proyeksinya secara otomatis.



---

### 3. Data Masukan untuk Pelatihan (`AS SELECT ...`)

```sql
AS
SELECT 
  date,
  hospital_name,
  department,
  admissions_count
FROM 
  `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily`
WHERE 
  date <= '2026-05-01';

```

* **Fungsi**: Memilih kolom yang dibutuhkan dari tabel data harian rumah sakit yang telah di-ingest sebelumnya.
* **Strategi Pembatasan Tanggal (`WHERE date <= '2026-05-01'`)**:
* Di dalam script data generator, data Anda digenerate hingga **31 Mei 2026**.
* Dengan membatasi data pelatihan hanya sampai **1 Mei 2026**, Anda menyisakan data sisa (1 Mei hingga 31 Mei 2026) sebagai **holdout/test set** (data uji).
* Ini adalah praktik terbaik (*best practice*) dalam Data Science agar nantinya Anda bisa membandingkan hasil ramalan model di bulan Mei 2026 dengan data aktual yang sebenarnya guna mengukur tingkat akurasi (seperti nilai MAPE atau RMSE).

---
## 12. Model Evaluation
### a. Evaluasi

####  1. 12 Baris (Rows 1-12 of 12)

Jumlah 12 baris ini terbentuk karena pada konfigurasi query pembuatan model, kita menggunakan parameter:
`time_series_id_col = ['hospital_name', 'department']`

Dalam generator data kita, terdapat **4 Rumah Sakit** dan **3 Departemen**. BigQuery secara otomatis memecah data tersebut menjadi **12 deret waktu (*time series*) yang unik** (4 RS $\times$ 3 Departemen = 12 kombinasi) dan melatih 12 model ARIMA secara paralel. Setiap baris pada tabel ini mewakili hasil evaluasi dari satu model spesifik untuk kombinasi RS dan Departemen tertentu.

---

#### 2. Penjelasan Kolom-Kolom Tabel Evaluasi

Kolom-kolom ini menunjukkan arsitektur terbaik yang dipilih secara otomatis oleh BigQuery (*Auto-ARIMA*) serta metrik statistik performa untuk masing-masing dari 12 model tersebut:

* **`Non Seasonal P` ($p$)**: Menunjukkan ordo *Autoregressive* (AR) bagian non-musiman. Nilai `1` berarti nilai hari ini dipengaruhi oleh 1 hari sebelumnya. Nilai `0` berarti tidak ada pengaruh langsung dari hari sebelumnya secara non-musiman.
* **`Non Seasonal D` ($d$)**: Menunjukkan tingkat *Differencing* (pembedaan) untuk membuat data menjadi stasioner. Semua model menunjukkan nilai `1`, yang berarti data membutuhkan 1 kali proses pengurangan dengan hari sebelumnya agar trennya stabil.
* **`Non Seasonal Q` ($q$)**: Menunjukkan ordo *Moving Average* (MA) bagian non-musiman. Nilai `1` menunjukkan model menggunakan rata-rata bergerak dari 1 error historis sebelumnya untuk memperbaiki prediksi.
* **`Has Drift`**: Berfungsi untuk mendeteksi apakah tren data memiliki kecenderungan naik/turun yang konstan secara jangka panjang (*drift*). Di sini semua bernilai `False`.
* **`Has Spikes And Dips`**: Menunjukkan apakah BigQuery mendeteksi dan membersihkan pencilan (*outliers*) berupa lonjakan (*spikes*) atau penurunan tajam (*dips*) ekstrem yang tidak wajar sebelum melatih model. Beberapa model bernilai `True` (outlier berhasil dihilangkan) dan beberapa `False`.
* **`Has Holiday Effect`**: Semua baris bernilai **`True`**. Ini membuktikan konfigurasi `holiday_region = 'ID'` berhasil diterapkan. Model secara otomatis menyesuaikan prediksinya dengan pola hari libur nasional di Indonesia.
* **`Has Step Changes`**: Menunjukkan apakah model mendeteksi adanya perubahan tingkat (*level*) dasar data secara permanen. Misalnya, jika jumlah pasien tiba-tiba naik permanen karena ada penambahan fasilitas baru.
* **`Log Likelihood`**: Ukuran seberapa cocok model dengan data latih (semakin mendekati 0 atau semakin besar nilainya secara aljabar, semakin baik).
* **`AIC` (Akaike Information Criterion)**: Metrik untuk mengukur kualitas model dengan mempertimbangkan kompleksitasnya. **Semakin rendah nilai AIC, semakin baik dan efisien model tersebut.**
* **`Variance`**: Menunjukkan varians dari *residual* (error prediksi). Nilai varians yang kecil (seperti `6.973` atau `8.771`) menunjukkan tingkat akurasi prediksi model tersebut sangat tinggi dibandingkan yang bervarians besar (seperti `157.507`).
* **`Seasonal Period`**: Pola musiman yang berhasil dideteksi secara otomatis oleh BigQuery:
* `Weekly, Yearly`: Model mendeteksi adanya pola musiman mingguan (misal: Outpatient tutup di hari Minggu) dan tahunan (misal: siklus musim hujan/kemarau di Jakarta).
* `Weekly`: Hanya memiliki pola mingguan berulang.
* `No Seasonality`: Data cenderung flat atau acak tanpa pola musiman yang konsisten (biasanya terjadi pada departemen ICU yang kedatangan pasiennya tidak terduga).

---

### b. Evaluasi terhadap data Mei 2026
```sql
SELECT
  *
FROM
  ML.EVALUATE(
    MODEL `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_arima`,
    (
      SELECT 
        date,
        hospital_id,
        department,
        admissions_count
      FROM 
        `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily`
      WHERE 
        date > '2026-05-01'
    ),
    STRUCT(30 AS horizon, TRUE AS perform_aggregation)
  );
```

query `ML.EVALUATE` khusus ini digunakan untuk menguji seberapa akurat prediksi model jika diadu dengan **data riil yang baru (data holdout/test set)**.

Berikut adalah penjelasan detail untuk setiap komponen di dalam query tersebut:

---

#### 1. Fungsi Utama: `ML.EVALUATE`

Fungsi bawaan (*built-in function*) BigQuery ML ini digunakan untuk menghitung metrik evaluasi model. Khusus untuk model berjenis `ARIMA_PLUS`, `ML.EVALUATE` akan menghitung seberapa besar tingkat *error* atau kesalahan prediksi model terhadap data aktual yang Anda sediakan.

---

#### 2. Argumen Pertama: Objek Model

```sql
MODEL `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_arima`

```

Argumen ini memberi tahu BigQuery model mana yang ingin dievaluasi. Di sini, Anda memanggil model time-series rumah sakit Jakarta yang sudah dibuat pada langkah sebelumnya.

---

#### 3. Argumen Kedua: Data Uji (*Evaluation Data*)

```sql
(
  SELECT 
    date,
    hospital_name,
    department,
    admissions_count
  FROM 
    `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily`
  WHERE 
    date > '2026-05-01'
)

```

Ini adalah bagian yang sangat krusial. Perhatikan klausa **`WHERE date > '2026-05-01'`**.

* Saat membuat model, Anda hanya menggunakan data **sampai tanggal 1 Mei 2026** sebagai data latih (*training set*).
* Di query ini, Anda memasukkan data **setelah tanggal 1 Mei 2026** (data bulan Mei yang tersisa) sebagai data uji (*test set*).
* Model akan diminta meramal untuk tanggal-tanggal di bulan Mei tersebut, lalu BigQuery akan membandingkan hasil ramalan tersebut dengan nilai `admissions_count` aktual yang ada di dalam tabel ini.

---

#### 4. Argumen Ketiga: Parameter Tambahan (`STRUCT`)

```sql
STRUCT(30 AS horizon, TRUE AS perform_aggregation)

```

Bagian ini mengatur bagaimana proses evaluasi dihitung secara teknis:

* **`30 AS horizon`**: Menginstruksikan model untuk mengevaluasi prediksi hingga **30 langkah (hari) ke depan** terhitung sejak titik akhir data latih (artinya, meramal sepanjang bulan Mei 2026).
* **`TRUE AS perform_aggregation`**:
* Jika disetel `TRUE`, BigQuery akan merata-ratakan seluruh *error* prediksi selama 30 hari tersebut dan mengembalikan **1 baris evaluasi saja untuk setiap kombinasi rumah sakit & departemen**.
* Jika disetel `FALSE`, BigQuery akan menampilkan performa *error* hari demi hari secara detail (misal: *error* di hari ke-1 berapa, hari ke-2 berapa, s.d hari ke-30).

---
### Penjelasan Metrik Evaluasi

#### 1. Panduan Singkat Membaca Metrik Evaluasi

* **MAE (*Mean Absolute Error*)**: Menunjukkan rata-rata selisih mutlak (jarak) antara prediksi model dengan jumlah pasien riil dalam satuan **orang/hari**.
* **RMSE (*Root Mean Squared Error*)**: Mirip seperti MAE, tetapi memberikan penalti berat pada error yang besar. Jika nilai RMSE jauh lebih tinggi dari MAE, berarti model sempat kecolongan membuat eror prediksi yang sangat besar di hari-hari tertentu (misalnya saat ada lonjakan pasien dadakan).
* **MAPE (*Mean Absolute Percentage Error*)**: Mengukur persentase rata-rata error. **Formula akurasinya adalah $100\% - \text{MAPE}$**. Nilai di bawah 20% dianggap sangat baik, 20%-50% cukup baik.
* **MASE (*Mean Absolute Scaled Error*)**: Metrik terbaik untuk membandingkan performa antar-departemen. Jika **$\text{MASE} < 1$**, berarti model ARIMA_PLUS Anda **jauh lebih pintar** dan akurat dibandingkan tebakan model dasar (*naive baseline*—seperti menebak bahwa jumlah pasien hari ini akan persis sama dengan kemarin).

#### 2. Analisis Berdasarkan Departemen (Insight Utama)

Jika kita kelompokkan data di atas berdasarkan departemen, kita akan menemukan karakteristik unik dari performa model:

##### Emergency Room (Instalasi Gawat Darurat) — *Performa Terbaik!*

* **Rentang MAPE**: **10.4% – 16.3%** (Artinya akurasi model mencapai **83.7% hingga 89.6%**).
* **Analisis**: Model bekerja sangat akurat di UGD. Sebagai contoh, di **RS Fatmawati UGD**, nilai MAE-nya adalah `7.8`. Artinya, jika model menebak akan ada 50 pasien UGD besok, jumlah aslinya di lapangan melesetnya hanya berkisar antara 42 sampai 58 pasien. Nilai MASE seluruh UGD berada di bawah 1 (`0.70 - 0.89`), membuktikan model ini sangat andal.

##### ICU (Intensive Care Unit) — *Error Kecil secara Angka, tapi Persentase Tinggi*

* **Rentang MAE**: **2.1 – 3.3 orang per hari**.
* **Rentang MAPE**: **25.8% – 50.5%**.
* **Analisis**: Jangan terkecoh oleh tingginya angka MAPE di ICU (terutama RSUD Pasar Minggu yang menyentuh 50.5%). Di ICU, jumlah pasien harian memang sangat sedikit (misal rata-rata hanya 4-6 orang sehari). Jika model menebak 4 pasien padahal aslinya 2 pasien, secara angka mutlak melesetnya cuma **2 orang (MAE sangat kecil)**, namun secara persentase erornya langsung **50%**. Model tetap dinilai sukses karena MASE mayoritas berada di kisaran `0.59 - 0.77`.

##### Outpatient (Poliklinik/Rawat Jalan) — *Tantangan Terbesar Model*

* **Rentang MAE**: **7.5 – 13.4 orang per hari**.
* **Rentang MAPE**: **17.7% – 58.0%**.
* **Analisis**: Departemen Rawat Jalan memiliki volume pasien paling besar dan fluktuatif (sangat ramai di hari Senin, turun di akhir pekan, dan tutup saat hari libur).
* **RSUD Cengkareng** memiliki performa terbaik di kelas rawat jalan dengan MAPE hanya `17.7%`.
* **RSUD Tarakan** memiliki MAPE tertinggi (`58%`). Ini menandakan adanya pola fluktuasi ekstrem di RSUD Tarakan pada bulan Mei 2026 yang belum sepenuhnya tertangkap dengan mulus oleh model, meskipun nilai MASE-nya `0.84` (masih lebih baik daripada model tebakan biasa).

---

#### 3. Kesimpulan Evaluasi Untuk Anda

Jika Anda harus mempresentasikan hasil ini kepada manajemen rumah sakit, berikut adalah poin kesimpulannya:

1. **Model Siap Dipakai**: Nilai **MASE < 1** pada 11 dari 12 kombinasi membuktikan bahwa BigQuery ARIMA_PLUS ini sangat layak digunakan untuk perencanaan logistik obat dan penjadwalan tenaga medis harian.
2. **Fokus Pembenahan**: Departemen *Outpatient* (Rawat Jalan) di RSUD Tarakan perlu diperiksa lebih lanjut. Anda bisa meningkatkan akurasinya di masa depan dengan menambahkan variabel eksternal tambahan (seperti jadwal rotasi dokter spesifik) jika diperlukan.

---
## 13. Model Inference

```sql
SELECT
  hospital_id,
  department,
  forecast_timestamp,
  ROUND(forecast_value) AS forecasted_admissions,
  ROUND(prediction_interval_lower_bound) AS lower_bound,
  ROUND(prediction_interval_upper_bound) AS upper_bound
FROM
  ML.FORECAST(
    MODEL `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_arima`,
    STRUCT(30 AS horizon, 0.90 AS confidence_level)
  )
ORDER BY
  hospital_id,
  department,
  forecast_timestamp;
```

### 1. Fungsi Utama: `ML.FORECAST`

Fungsi bawaan BigQuery ML ini digunakan khusus untuk model deret waktu (*time-series*) seperti `ARIMA_PLUS`. Fungsi ini bertugas mengeksekusi model yang sudah dilatih untuk memproyeksikan nilai-nilai ke masa depan (masa yang belum terjadi di dalam data pelatihan).

Di dalam fungsi ini, terdapat dua parameter penting:

* **`MODEL ...hospital_admissions_arima`**: Menentukan model mana yang digunakan sebagai otak untuk melakukan prediksi.
* **`STRUCT(30 AS horizon, 0.90 AS confidence_level)`**:
* **`30 AS horizon`**: Menginstruksikan model untuk meramal hingga **30 hari ke depan** dari titik data terakhir yang tersedia.
* **`0.90 AS confidence_level`**: Menentukan tingkat kepercayaan (90%) untuk batas atas dan batas bawah prediksi. Artinya, model mendesain rentang prediksi di mana ia 90% yakin bahwa jumlah pasien riil di lapangan nantinya akan jatuh di dalam rentang tersebut.



---

### 2. Kolom yang Dipilih (`SELECT`)

Hasil mentah dari `ML.FORECAST` sebenarnya mengeluarkan banyak kolom statistik teknis. Query Anda melakukan *filtering* dan pembulatan agar outputnya bersih dan mudah dibaca oleh tim operasional rumah sakit:

* **`hospital_name` & `department**`: Menunjukkan identitas rumah sakit dan poliklinik mana yang sedang diramal.
* **`forecast_timestamp`**: Tanggal di masa depan tempat prediksi tersebut berlaku (Hari ke-1, Hari ke-2, hingga Hari ke-30).
* **`ROUND(forecast_value) AS forecasted_admissions`**: Ini adalah **angka prediksi utama**. Karena jumlah pasien/manusia tidak mungkin berbentuk desimal (misal 45.7 orang), fungsi `ROUND` digunakan untuk membulatkannya ke satuan terdekat menjadi bilangan bulat (menjadi 46 orang).
* **`ROUND(prediction_interval_lower_bound) AS lower_bound`**: Batas bawah prediksi (skenario ter-sepi).
* **`ROUND(prediction_interval_upper_bound) AS upper_bound`**: Batas atas prediksi (skenario ter-ramai).

> **Mengapa Batas Atas dan Bawah Penting?**
> Jika untuk tanggal besok `forecasted_admissions` adalah **50**, dengan `lower_bound` **40** dan `upper_bound` **65**, maka manajemen rumah sakit bisa bersiap-siap: *minimal* menyediakan logistik untuk 40 pasien, dan menyiapkan kapasitas darurat hingga 65 pasien.

---

### 3. Pengurutan Data (`ORDER BY`)

```sql
ORDER BY
  hospital_name,
  department,
  forecast_timestamp;

```

Bagian ini memastikan hasil prediksi disajikan secara rapi dan berurutan. Data akan dikelompokkan per rumah sakit dahulu, lalu per departemen di dalam rumah sakit tersebut, dan barisnya diurutkan kronologis dari tanggal terdekat hingga tanggal terjauh (hari ke-1 sampai hari ke-30).

### Penjelasan Hasil Forecast
Data JSON yang Anda kirimkan merupakan hasil proyeksi operasional (*forecast output*) riil untuk bulan Mei 2026.

Berikut adalah penjelasan detail mengenai arti dan fungsi dari setiap kolom hasil query `ML.FORECAST` tersebut, agar Anda bisa membacanya dengan mudah:

---

#### 1. Identitas Entitas (Dimensi Data)

* **`hospital_name` (Nama Rumah Sakit)**
* **Penjelasan**: Menunjukkan lokasi fisik rumah sakit tempat prediksi ini berlaku (misal: `RS Fatmawati`, `RSUD Tarakan`).


* **`department` (Departemen/Poliklinik)**
* **Penjelasan**: Menunjukkan unit spesifik di dalam rumah sakit tersebut. Di sini terlihat model memisahkan karakteristik tiap departemen dengan sangat baik:
* **Emergency Room (UGD)**: Pola kedatangan pasien cenderung fluktuatif harian tapi konstan tinggi.
* **ICU**: Kebutuhan kasur kritis yang sifatnya flat (terlihat prediksinya konstan di angka `15.0` atau `9.0` setiap hari).
* **Outpatient (Rawat Jalan)**: Memiliki pola musiman mingguan yang sangat ekstrem (ramai di hari kerja, turun drastis atau libur di akhir pekan).

---

#### 2. Parameter Waktu

* **`forecast_timestamp` (Tanggal Proyeksi)**
* **Penjelasan**: Kolom penunjuk waktu kapan prediksi tersebut akan terjadi di masa depan.
* **Format**: Ditampilkan dalam bentuk zona waktu standar dunia (`UTC`). Sebagai contoh, `"2026-05-02 00:00:00.000000 UTC"` berarti prediksi tersebut berlaku untuk sepanjang hari pada tanggal **2 Mei 2026**.

---

#### 3. Metrik Prediksi Utama & Rentang Ketidakpastian

Bagian ini adalah inti dari sistem pendukung keputusan operasional (*decision support system*).

* **`forecasted_admissions` (Prediksi Utama Jumlah Pasien)**
* **Penjelasan**: Ini adalah **titik nilai tengah (paling krusial)** yang paling mungkin terjadi berdasarkan perhitungan tren statistik historis oleh algoritma ARIMA.
* **Contoh Kasus**: Pada tanggal 4 Mei 2026 di *RS Fatmawati - Outpatient*, angka prediksinya adalah `298.0` pasien. Manajemen bisa menggunakan angka ini sebagai acuan utama dasar penyediaan jumlah berkas fisik, obat-obatan, dan antrean.


* **`lower_bound` (Batas Bawah Prediksi) & `upper_bound` (Batas Atas Prediksi)**
* **Penjelasan**: Kedua kolom ini membentuk **Interval Prediksi (*Prediction Interval*)** dengan tingkat kepercayaan 90% (sesuai konfigurasi `0.90 AS confidence_level` pada query sebelumnya).
* **Cara Membaca**: Model menyatakan: *"Kami 90% yakin bahwa jumlah pasien riil di lapangan pada tanggal tersebut tidak akan kurang dari `lower_bound` dan tidak akan lebih dari `upper_bound`."*



---

### 💡 Insight Menarik: Mengapa Ada Angka Negatif di Kolom Proyeksi?

Jika Anda perhatikan pada data *Outpatient* di hari Minggu (misalnya **RS Fatmawati - Outpatient tanggal 3 Mei 2026**):

* `forecasted_admissions`: `-3.0`
* `lower_bound`: `-23.0`
* `upper_bound`: `18.0`

#### Mengapa hal ini terjadi secara matematis?

Model ARIMA berbasis rumus statistik linier kontinu. Karena data historis poliklinik rawat jalan pada hari Minggu di dalam script generator kita disetel mendekati **0** (tutup/hanya klinik skeletal), fungsi matematika model terkadang meluncur turun melewati angka nol hingga menghasilkan angka negatif untuk mempertahankan keseimbangan kurva musimannya.

#### Bagaimana cara mengatasinya di aplikasi riil?

Dalam implementasi sistem informasi rumah sakit atau *dashboard* visualisasi, Anda cukup menambahkan fungsi logika sederhana $max(0, \text{nilai})$ untuk melakukan *clamping* otomatis, karena di dunia nyata jumlah pasien tidak mungkin minus:

* Jika hasil prediksi adalah `-3.0`, maka di dashboard dibaca sebagai **0 pasien** (Poliklinik Libur).
* Jika batas bawah adalah `-23.0`, maka dibaca sebagai **0 pasien**.

## 14. Membuat Tabel `query_examples`
```sql
CREATE OR REPLACE TABLE `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.query_examples`
(
  id STRING NOT NULL
    OPTIONS(description="ID unik untuk masing-masing baris contoh kueri."),
  
  question STRING NOT NULL
    OPTIONS(description="Pertanyaan pengguna dalam bahasa alami (natural language question)."),
  
  sql_query STRING NOT NULL
    OPTIONS(description="Sintaks kueri SQL yang valid dan sesuai untuk menjawab pertanyaan tersebut."),

  -- Mendefinisikan Primary Key pada tabel contoh kueri
  PRIMARY KEY (id) NOT ENFORCED
)
OPTIONS(
  description="Tabel katalog referensi internal penyimpan pasangan kueri few-shot Text-to-SQL untuk melatih kecerdasan agen pintar."
);
```

### a. Contoh Kueri Few-Shot

```sql
INSERT INTO `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.query_examples`
  (id, question, sql_query)
VALUES
  ('1', 
   'Berapa total admisi harian untuk setiap rumah sakit di Jakarta Selatan?', 
   'SELECT h.hospital_name, SUM(a.admissions_count) AS total_admisi FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.dim_hospitals` h JOIN `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` a ON h.hospital_id = a.hospital_id WHERE h.district = "Jakarta Selatan" GROUP BY h.hospital_name ORDER BY total_admisi DESC;'
  ),
  ('2', 
   'Berapa rata-rata waktu tunggu Emergency Room ketika hari libur nasional?', 
   'SELECT AVG(avg_wait_time_minutes) AS rata_rata_tunggu FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` WHERE department = "Emergency Room" AND is_holiday = 1;'
  ),
  ('3', 
   'Bagaimana hasil ramalan jumlah pasien untuk 14 hari ke depan?', 
   'SELECT * FROM ML.FORECAST(MODEL `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_arima`, STRUCT(14 AS horizon, 0.95 AS confidence_level));'
  ),
  ('4',
   'Berapa rata-rata harian admisi pasien untuk setiap departemen poliklinik?',
   'SELECT department, AVG(admissions_count) AS rata_rata_admisi, SUM(admissions_count) AS total_admisi FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` GROUP BY department ORDER BY total_admisi DESC;'
  ),
  ('5',
   'Berapa rata-rata admisi harian di UGD saat kondisi udara buruk dibandingkan saat kondisi udara baik?',
   'SELECT CASE WHEN air_quality_index > 100 THEN "Buruk (>100)" ELSE "Baik/Sedang (<=100)" END AS kategori_udara, AVG(admissions_count) AS rata_rata_admisi_er FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` WHERE department = "Emergency Room" GROUP BY kategori_udara;'
  ),
  ('6',
   'Berapa total kapasitas tempat tidur dan jumlah rumah sakit yang tersedia di setiap wilayah kota Jakarta?',
   'SELECT district, COUNT(hospital_id) AS jumlah_rs, SUM(total_beds) AS total_tempat_tidur FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.dim_hospitals` GROUP BY district ORDER BY total_tempat_tidur DESC;'
  ),
  ('7',
   'Bagaimana rata-rata waktu tunggu di UGD saat hujan lebat dibandingkan saat tidak hujan?',
   'SELECT CASE WHEN rainfall_mm > 20 THEN "Hujan Lebat (>20mm)" WHEN rainfall_mm > 0 THEN "Hujan Ringan/Sedang" ELSE "Tidak Hujan" END AS kondisi_hujan, AVG(avg_wait_time_minutes) AS rata_rata_tunggu_er FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` WHERE department = "Emergency Room" GROUP BY kondisi_hujan;'
  ),
  ('8',
   'Berapa perbandingan total pasien Rawat Jalan antara hari kerja dan akhir pekan ?',
   'SELECT CASE WHEN is_weekend = 1 THEN "Akhir Pekan (Weekend)" ELSE "Hari Kerja (Weekday)" END AS jenis_hari, SUM(admissions_count) AS total_admisi_outpatient FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` WHERE department = "Outpatient" GROUP BY jenis_hari;'
  ),
  ('9',
   'Rumah sakit mana yang memiliki rata-rata waktu tunggu UGD terlama di tahun 2025?',
   'SELECT hospital_name, AVG(avg_wait_time_minutes) AS rata_rata_tunggu_er FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` WHERE department = "Emergency Room" AND EXTRACT(YEAR FROM date) = 2025 GROUP BY hospital_name ORDER BY rata_rata_tunggu_er DESC;'
  ),
  ('10',
   'Bagaimana tren bulanan total admisi pasien di seluruh rumah sakit sepanjang tahun 2025?',
   'SELECT EXTRACT(MONTH FROM date) AS bulan, SUM(admissions_count) AS total_admisi FROM `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.hospital_admissions_daily` WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY bulan ORDER BY bulan;'
  );
```

## 15. Membuat Tabel `query_examples_embeddings`
```sql
CREATE OR REPLACE TABLE `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.query_examples_embeddings`
(
  content STRING
    OPTIONS(description="Dokumen semantik terstruktur (Question & SQL) yang di-embed secara utuh."),
  
  embedding ARRAY<FLOAT64>
    OPTIONS(description="Representasi vektor (embedding) dari isi kolom content untuk pencarian kemiripan kueri (semantic search query match).")
)
OPTIONS(
  description="Tabel penyimpan dokumen semantik contoh kueri beserta vektor embedding-nya untuk mendukung pencarian pencocokan kueri few-shot."
);
```


## 16. Seeding data ke tabel `query_examples_embeddings`
```sql
INSERT INTO `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.query_examples_embeddings` (content, embedding)
WITH prepared_queries AS (
  SELECT 
    CONCAT(
      'Question: ', question, '\n',
      'SQL: ', sql_query
    ) AS query_content
  FROM 
    `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.query_examples`
)
SELECT 
  query_content AS content,
  ARRAY(
    SELECT LAX_FLOAT64(val) 
    FROM UNNEST(
      JSON_QUERY_ARRAY(
        `YOUR_PROJECT_NAME.healthcare_forecasting_jakarta_v2.get_text_embedding`(query_content)
      )
    ) AS val
  ) AS embedding
FROM 
  prepared_queries;
```

---
