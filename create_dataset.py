import os
import sys
import math
import random
import datetime
import csv

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
                    weekly_mults = [0.95, 0.90, 0.90, 0.92, 0.98, 1.15, 1.20]
                    weekly_mult = weekly_mults[weekday]
                elif dept["er_pattern"] is False:
                    # Outpatient: Closed/very low on weekends, peaks on Mondays
                    if is_holiday == 1:
                        weekly_mult = 0.05 
                    else:
                        weekly_mults = [1.45, 1.30, 1.20, 1.10, 1.00, 0.15, 0.0]
                        weekly_mult = weekly_mults[weekday]
                else:
                    # ICU: Flat across the week
                    weekly_mult = 1.0
                    
                # Weather/Environmental effects
                rain_effect = 1.0 + 0.12 * (rain / 60.0)
                rain_effect = min(1.25, rain_effect)
                
                aqi_effect = 1.0 + 0.18 * (max(0, aqi - 60) / 140.0)
                aqi_effect = min(1.25, aqi_effect)
                
                # Holiday effects
                holiday_mult = 1.0
                if is_holiday == 1:
                    if dept["er_pattern"] is True:
                        holiday_mult = 1.15
                
                # Combine
                expected_value = base_val * trend * weekly_mult * rain_effect * aqi_effect * holiday_mult
                
                # Special hard clamp for outpatient on Sunday
                if dept["er_pattern"] is False and weekday == 6 and is_holiday == 0:
                    admissions = generate_poisson(0.5)
                else:
                    admissions = generate_poisson(expected_value)
                
                # Wait time metric
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

def save_data_to_csv():
    # Definisikan rentang waktu data
    start_date = datetime.date(2022, 1, 1)
    end_date = datetime.date(2026, 5, 31)
    
    # Generate data rumah sakit saja
    hosp_records = generate_hospital_data(start_date, end_date)
    
    csv_file = "hospital_admissions_daily.csv"
    
    print(f"Writing data to {csv_file}...")
    
    # Ambil nama field dari dictionary sebagai header CSV
    if hosp_records:
        headers = hosp_records[0].keys()
        
        with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            # Tulis header kolom
            writer.writeheader()
            # Tulis seluruh baris data
            writer.writerows(hosp_records)
            
        print(f"Process completed! Successfully saved {len(hosp_records)} rows to {csv_file}.")
    else:
        print("No records were generated.")

if __name__ == "__main__":
    save_data_to_csv()