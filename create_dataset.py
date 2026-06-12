import os
import sys
import math
import random
import datetime
import json
from google.cloud import bigquery
from google.api_core.exceptions import Conflict

# Set region to Jakarta
REGION = "asia-southeast2"
DATASET_ID = "healthcare_forecasting_jakarta"

def generate_poisson(lam):
    """Generates a Poisson-distributed random variable."""
    if lam <= 0:
        return 0
    if lam < 30:
        # Knuth's algorithm
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= random.random()
        return max(0, k - 1)
    else:
        # Gaussian approximation for larger lambda
        val = random.normalvariate(lam, math.sqrt(lam))
        return max(0, int(round(val)))

def get_indonesian_holidays(year):
    """Returns approximate major holiday dates for Jakarta."""
    holidays = {
        # Fixed date holidays
        datetime.date(year, 1, 1),   # New Year
        datetime.date(year, 8, 17),  # Independence Day
        datetime.date(year, 12, 25), # Christmas
    }
    # Shifting Eid al-Fitr (Lebaran) approximation
    if year == 2022:
        holidays.update({datetime.date(2022, 5, 2), datetime.date(2022, 5, 3)})
    elif year == 2023:
        holidays.update({datetime.date(2023, 4, 21), datetime.date(2023, 4, 22)})
    elif year == 2024:
        holidays.update({datetime.date(2024, 4, 10), datetime.date(2024, 4, 11)})
    elif year == 2025:
        holidays.update({datetime.date(2025, 3, 31), datetime.date(2025, 4, 1)})
    elif year == 2026:
        holidays.update({datetime.date(2026, 3, 20), datetime.date(2026, 3, 21)})
    return holidays

def generate_hospital_data(start_date, end_date):
    """Generates daily hospital admissions data with seasonality, trends, weather and holidays."""
    print("Generating hospital admissions daily dataset...")
    hospitals = [
        {"name": "RSUD Pasar Minggu", "base": 30.0},
        {"name": "RSUD Tarakan", "base": 45.0},
        {"name": "RSUD Cengkareng", "base": 35.0},
        {"name": "RS Fatmawati", "base": 60.0}
    ]
    
    departments = [
        {"name": "Emergency Room", "multiplier": 1.0, "er_pattern": True},
        {"name": "Outpatient", "multiplier": 2.5, "er_pattern": False},
        {"name": "ICU", "multiplier": 0.2, "er_pattern": None}
    ]
    
    records = []
    current_date = start_date
    delta = datetime.timedelta(days=1)
    
    # Store daily weather parameters so they are consistent across hospitals
    daily_weather = {}
    
    # Pre-generate weather & AQI to simulate realistic Jakarta conditions
    while current_date <= end_date:
        doy = current_date.timetuple().tm_yday
        year = current_date.year
        
        # Temp: Warmest in Oct, coolest in Jan during wet season
        temp = 28.0 + 1.5 * math.cos(2 * math.pi * (doy - 280) / 365.25) + random.uniform(-0.8, 0.8)
        
        # Rainfall: Peak in Jan-Feb, dry in Aug
        rain_prob = 0.6 + 0.35 * math.cos(2 * math.pi * (doy - 40) / 365.25)
        if random.random() < rain_prob:
            rain = random.expovariate(1.0 / 18.0)
            if rain < 1.0: rain = 0.0 # Small rain is negligible
        else:
            rain = 0.0
            
        # Air Quality (AQI): Worse in dry season (Jul-Aug) due to stagnation
        aqi = 105.0 + 45.0 * math.cos(2 * math.pi * (doy - 210) / 365.25) + random.normalvariate(0, 12)
        aqi = max(30, min(200, int(round(aqi))))
        
        holidays = get_indonesian_holidays(year)
        is_holiday = 1 if current_date in holidays else 0
        is_weekend = 1 if current_date.weekday() in (5, 6) else 0
        
        daily_weather[current_date] = {
            "temp": round(temp, 1),
            "rain": round(rain, 1),
            "aqi": aqi,
            "is_holiday": is_holiday,
            "is_weekend": is_weekend,
            "weekday": current_date.weekday()
        }
        current_date += delta
        
    # Generate records
    total_days = (end_date - start_date).days + 1
    current_date = start_date
    day_idx = 0
    
    while current_date <= end_date:
        weather = daily_weather[current_date]
        temp = weather["temp"]
        rain = weather["rain"]
        aqi = weather["aqi"]
        is_holiday = weather["is_holiday"]
        is_weekend = weather["is_weekend"]
        weekday = weather["weekday"]
        
        # Trend factor: 4% annual increase in healthcare demand
        trend = 1.0 + 0.04 * (day_idx / 365.25)
        
        for hosp in hospitals:
            for dept in departments:
                base_val = hosp["base"] * dept["multiplier"]
                
                # Apply weekly seasonality
                if dept["er_pattern"] is True:
                    # ER: Higher on weekends
                    # Mon=0.95, Tue=0.90, Wed=0.90, Thu=0.92, Fri=0.98, Sat=1.15, Sun=1.20
                    weekly_mults = [0.95, 0.90, 0.90, 0.92, 0.98, 1.15, 1.20]
                    weekly_mult = weekly_mults[weekday]
                elif dept["er_pattern"] is False:
                    # Outpatient: Closed/very low on weekends, peaks on Mondays
                    # Mon=1.45, Tue=1.30, Wed=1.20, Thu=1.10, Fri=1.00, Sat=0.15, Sun=0.0
                    if is_holiday == 1:
                        weekly_mult = 0.05 # Outpatient is mostly closed on holidays
                    else:
                        weekly_mults = [1.45, 1.30, 1.20, 1.10, 1.00, 0.15, 0.0]
                        weekly_mult = weekly_mults[weekday]
                else:
                    # ICU: Flat across the week
                    weekly_mult = 1.0
                    
                # Weather/Environmental effects
                # Outpatient and ER: spike up to 12% during high rain (respiratory, accidents, waterborne illness)
                rain_effect = 1.0 + 0.12 * (rain / 60.0)
                rain_effect = min(1.25, rain_effect)
                
                # Outpatient and ICU: spike up to 18% during high AQI (smog causes respiratory issues)
                aqi_effect = 1.0 + 0.18 * (max(0, aqi - 60) / 140.0)
                aqi_effect = min(1.25, aqi_effect)
                
                # Holiday effects
                holiday_mult = 1.0
                if is_holiday == 1:
                    if dept["er_pattern"] is True:
                        # ER spikes slightly on holidays
                        holiday_mult = 1.15
                    elif dept["er_pattern"] is False:
                        # Outpatient already handled
                        pass
                
                # Combine
                expected_value = base_val * trend * weekly_mult * rain_effect * aqi_effect * holiday_mult
                
                # Special hard clamp for outpatient on Sunday
                if dept["er_pattern"] is False and weekday == 6 and is_holiday == 0:
                    # Sunday outpatient might have a very small skeletal clinic or 0
                    admissions = generate_poisson(0.5)
                elif dept["er_pattern"] is False and is_holiday == 1:
                    admissions = generate_poisson(expected_value)
                else:
                    admissions = generate_poisson(expected_value)
                
                # Wait time metric: increases with admissions
                avg_wait = 15.0 + 0.4 * admissions + random.uniform(-3, 3)
                avg_wait = max(5.0, round(avg_wait, 1))
                
                records.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "hospital_name": hosp["name"],
                    "department": dept["name"],
                    "admissions_count": int(admissions),
                    "avg_wait_time_minutes": float(avg_wait),
                    "temperature_celsius": float(temp),
                    "rainfall_mm": float(rain),
                    "air_quality_index": int(aqi),
                    "is_holiday": int(is_holiday),
                    "is_weekend": int(is_weekend)
                })
                
        current_date += delta
        day_idx += 1
        
    return records

def generate_dengue_data(start_date, end_date):
    """Generates weekly dengue fever case count data for Jakarta districts."""
    print("Generating weekly dengue fever dataset...")
    districts = [
        {"name": "Jakarta Selatan", "base": 35.0},
        {"name": "Jakarta Timur", "base": 45.0},
        {"name": "Jakarta Barat", "base": 40.0},
        {"name": "Jakarta Utara", "base": 25.0},
        {"name": "Jakarta Pusat", "base": 18.0}
    ]
    
    records = []
    
    # Adjust start date to the nearest Monday
    current_date = start_date - datetime.timedelta(days=start_date.weekday())
    delta = datetime.timedelta(days=7)
    
    while current_date <= end_date:
        doy = current_date.timetuple().tm_yday
        year = current_date.year
        
        # Humidity: Higher in wet season (Jan-Feb = ~84%), lower in dry season (Aug-Sep = ~72%)
        humidity = 78.0 + 6.0 * math.cos(2 * math.pi * (doy - 40) / 365.25) + random.uniform(-2.0, 2.0)
        humidity = round(max(50.0, min(100.0, humidity)), 1)
        
        # Rainfall weekly sum: higher in wet season
        rain_weekly = 30.0 + 25.0 * math.cos(2 * math.pi * (doy - 40) / 365.25) + random.expovariate(1.0 / 20.0)
        rain_weekly = round(max(0.0, rain_weekly), 1)
        
        # Temp weekly avg
        temp = 28.0 + 1.2 * math.cos(2 * math.pi * (doy - 280) / 365.25) + random.uniform(-0.5, 0.5)
        temp = round(temp, 1)
        
        # Trend factor: 2% annual increase due to urbanization
        years_since_start = (current_date - start_date).days / 365.25
        trend = 1.0 + 0.02 * years_since_start
        
        # Dengue peaks in transition period from wet to dry season (typically March to May)
        # Peak around doy 115 (April 25)
        dengue_seasonality = 1.0 + 0.75 * math.cos(2 * math.pi * (doy - 115) / 365.25)
        
        for dist in districts:
            base_val = dist["base"]
            
            # Additional humudity factor: mosquitoes thrive in humid conditions
            humidity_factor = 1.0 + 0.04 * (humidity - 78.0)
            humidity_factor = max(0.7, min(1.3, humidity_factor))
            
            expected_cases = base_val * trend * dengue_seasonality * humidity_factor
            cases = generate_poisson(expected_cases)
            
            records.append({
                "week_start_date": current_date.strftime("%Y-%m-%d"),
                "district": dist["name"],
                "case_count": int(cases),
                "average_humidity_pct": float(humidity),
                "total_rainfall_mm": float(rain_weekly),
                "average_temp_celsius": float(temp)
            })
            
        current_date += delta
        
    return records

def create_bq_dataset_and_upload():
    # Initialize Client
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "eikon-dev-ai-team")
    client = bigquery.Client(project=project_id)
    
    dataset_ref = client.dataset(DATASET_ID)
    
    # Check if dataset exists, create it if not in Jakarta region (asia-southeast2)
    try:
        dataset = client.get_dataset(dataset_ref)
        print(f"Dataset {DATASET_ID} already exists.")
    except Exception:
        print(f"Creating dataset {DATASET_ID} in region {REGION}...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = REGION
        dataset.description = "Dummy Healthcare Dataset for Jakarta Region for ML Forecasting"
        dataset = client.create_dataset(dataset)
        print(f"Dataset {DATASET_ID} created successfully.")
        
    # Generate and Write Data
    start_date = datetime.date(2022, 1, 1)
    end_date = datetime.date(2026, 5, 31)
    
    hosp_records = generate_hospital_data(start_date, end_date)
    dengue_records = generate_dengue_data(start_date, end_date)
    
    # Save to NDJSON locally in current workspace for upload
    hosp_file = "hospital_admissions_daily.json"
    dengue_file = "dengue_cases_weekly.json"
    
    print("Writing temporary NDJSON files...")
    with open(hosp_file, 'w', encoding='utf-8') as f:
        for r in hosp_records:
            f.write(json.dumps(r) + '\n')
            
    with open(dengue_file, 'w', encoding='utf-8') as f:
        for r in dengue_records:
            f.write(json.dumps(r) + '\n')
            
    # Load to BigQuery - Hospital Admissions
    print("Loading hospital_admissions_daily to BigQuery...")
    hosp_table_ref = dataset_ref.table("hospital_admissions_daily")
    
    hosp_schema = [
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("hospital_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("department", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("admissions_count", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("avg_wait_time_minutes", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("temperature_celsius", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("rainfall_mm", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("air_quality_index", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("is_holiday", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("is_weekend", "INTEGER", mode="NULLABLE"),
    ]
    
    hosp_job_config = bigquery.LoadJobConfig(
        schema=hosp_schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="date"
        ),
        clustering_fields=["hospital_name", "department"]
    )
    
    with open(hosp_file, "rb") as source_file:
        job = client.load_table_from_file(source_file, hosp_table_ref, job_config=hosp_job_config)
    job.result() # Wait for job to complete
    print(f"Table hospital_admissions_daily uploaded successfully with {len(hosp_records)} rows.")
    
    # Load to BigQuery - Dengue Cases
    print("Loading dengue_cases_weekly to BigQuery...")
    dengue_table_ref = dataset_ref.table("dengue_cases_weekly")
    
    dengue_schema = [
        bigquery.SchemaField("week_start_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("district", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("case_count", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("average_humidity_pct", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("total_rainfall_mm", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("average_temp_celsius", "FLOAT", mode="NULLABLE"),
    ]
    
    dengue_job_config = bigquery.LoadJobConfig(
        schema=dengue_schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="week_start_date"
        ),
        clustering_fields=["district"]
    )
    
    with open(dengue_file, "rb") as source_file:
        job = client.load_table_from_file(source_file, dengue_table_ref, job_config=dengue_job_config)
    job.result() # Wait for job to complete
    print(f"Table dengue_cases_weekly uploaded successfully with {len(dengue_records)} rows.")
    
    # Clean up local temporary files
    try:
        os.remove(hosp_file)
        os.remove(dengue_file)
        print("Temporary local files cleaned up.")
    except Exception as e:
        print(f"Error cleaning up local files: {e}")
        
    print("Dataset generation and BQ upload process completed successfully!")

if __name__ == "__main__":
    create_bq_dataset_and_upload()
