import os
import sys
from google.cloud import storage
from google.api_core.exceptions import NotFound, Forbidden

# Konfigurasi GCS
# Ubah nama bucket sesuai dengan kebutuhan Anda (nama bucket harus unik secara global di GCS)
BUCKET_NAME = "healthcare-forecasting-jakarta-bucket" 
REGION_JAKARTA = "asia-southeast2"
LOCAL_CSV_FILE = "hospital_admissions_daily.csv"
GCS_BLOB_NAME = "hospital_admissions_daily.csv"

def upload_csv_to_gcs(bucket_name, source_file_name, destination_blob_name, location=REGION_JAKARTA):
    """Mengunggah file CSV lokal ke Google Cloud Storage di region Jakarta dan membuatnya dapat diakses publik."""
    
    # 1. Pastikan file lokal yang akan diunggah benar-benar ada
    if not os.path.exists(source_file_name):
        print(f"Error: File lokal '{source_file_name}' tidak ditemukan!")
        print("Silakan jalankan script generator data CSV terlebih dahulu.")
        sys.exit(1)

    print("Menginisialisasi Google Cloud Storage Client...")
    # Client akan otomatis mendeteksi kredensial dari environment variable:
    # GOOGLE_APPLICATION_CREDENTIALS atau dari metadata server jika berjalan di GCP (VM/Cloud Run)
    storage_client = storage.Client()

    # 2. Dapatkan atau buat Bucket di Region Jakarta (asia-southeast2)
    try:
        bucket = storage_client.get_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' ditemukan.")
    except NotFound:
        print(f"Bucket '{bucket_name}' tidak ditemukan. Membuat bucket baru...")
        try:
            # Membuat bucket baru dengan spesifikasi lokasi di Jakarta
            bucket = storage_client.bucket(bucket_name)
            bucket.storage_class = "STANDARD"
            new_bucket = storage_client.create_bucket(bucket, location=location)
            print(f"Sukses: Bucket '{new_bucket.name}' berhasil dibuat di region '{location}'.")
        except Forbidden as e:
            print(f"Error: Akses ditolak saat membuat bucket. Pastikan izin IAM Anda cukup. Detail: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Gagal membuat bucket: {e}")
            sys.exit(1)
    except Forbidden as e:
        print(f"Error: Akses ditolak ke bucket '{bucket_name}'. Detail: {e}")
        sys.exit(1)

    # 3. Proses Upload File & Pengaturan Akses Publik
    print(f"Memulai proses unggah '{source_file_name}' ke GCS...")
    try:
        blob = bucket.blob(destination_blob_name)
        
        # Mengunggah file lokal ke path blob tujuan
        blob.upload_from_filename(source_file_name)
        print("Proses unggah data selesai.")
        
        # Mengatur berkas agar dapat diakses oleh publik (allUsers:READER)
        print("Mengatur izin akses berkas menjadi PUBLIK...")
        try:
            blob.make_public()
            public_url = blob.public_url
            public_success = True
        except Exception as e:
            print("\nPeringatan: Gagal mengatur berkas menjadi publik otomatis.")
            print("Hal ini biasanya terjadi jika fitur 'Public Access Prevention' (PAP) aktif pada bucket Anda.")
            print("Anda perlu menonaktifkan PAP di konsol GCP atau menyetel IAM policy secara manual.")
            print(f"Detail Error: {e}")
            public_url = f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"
            public_success = False
        
        print("\n=== PROSES SELESAI ===")
        print(f"File lokal     : {source_file_name}")
        print(f"Path GCS       : gs://{bucket_name}/{destination_blob_name}")
        print(f"Region GCS     : {bucket.location} ({location})")
        if public_success:
            print("Status Akses   : PUBLIK (Berhasil)")
            print(f"Tautan Publik  : {public_url}")
        else:
            print("Status Akses   : PRIVATE (Gagal otomatis)")
            print(f"Tautan Manual  : {public_url}")
        print("=======================")
        
    except Exception as e:
        print(f"Gagal mengunggah file ke GCS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Jalankan fungsi upload
    upload_csv_to_gcs(
        bucket_name=BUCKET_NAME,
        source_file_name=LOCAL_CSV_FILE,
        destination_blob_name=GCS_BLOB_NAME,
        location=REGION_JAKARTA
    )