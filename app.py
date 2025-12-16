#!/usr/bin/env python3.9
# --- IMPORTS ---
from dotenv import load_dotenv
import os

# Load environment variables from a .env file if present (for local testing)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
import requests
import mysql.connector
from datetime import datetime, date, timedelta
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from google.oauth2 import service_account
import ee   
import sys
import json
import logging 

# --- LOGGING SETUP ---
# Render captures stdout/stderr automatically
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FLASK APP SETUP ---
app = Flask(__name__)
# Get secret key from Render Environment Variable
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback_secret_key_for_local_dev')

# --- GEE INITIALIZATION ---
try:
    gee_project_id = os.environ.get('GEE_PROJECT_ID', 'smartfarmingndvi')
    
    # Render stores secrets in /etc/secrets/ or we look for it locally
    # We check the Env Var 'GEE_KEY_PATH' first, otherwise look for 'gee-key.json'
    key_path = os.environ.get('GEE_KEY_PATH', 'gee-key.json')
    
    # If the path provided in ENV doesn't start with /, assume it is in the basedir
    if not key_path.startswith('/'):
        key_path = os.path.join(basedir, key_path)

    if os.path.exists(key_path):
        # Authenticate using the file
        service_account_email = os.environ.get('GEE_SA_EMAIL') # Optional if JSON has it
        credentials = ee.ServiceAccountCredentials(service_account_email, key_path)
        ee.Initialize(credentials=credentials, project=gee_project_id)
        logger.info(f"GEE Initialized via Service Account Key at: {key_path}")
    else:
        # Fallback: Try default credentials (rarely works on Render without setup)
        logger.warning(f"GEE Key file not found at {key_path}. Trying default credentials...")
        ee.Initialize(project=gee_project_id)

except Exception as e:
    logger.critical(f"CRITICAL WARNING: GEE Error: {e}")

# --- DATABASE CONFIGURATION (Render + Aiven) ---
def get_db_connection():
    try:
        # Get CA Certificate path from Env Var or default to 'ca.pem'
        ssl_ca = os.environ.get('SSL_CA_PATH', 'ca.pem')
        if not ssl_ca.startswith('/'):
             ssl_ca = os.path.join(basedir, ssl_ca)

        db_config = {
            'host': os.environ.get('DB_HOST'),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'database': os.environ.get('DB_NAME'),
            'port': int(os.environ.get('DB_PORT', 3306)) # Aiven uses non-standard ports
        }

        # Check if running on Render/Cloud (SSL File exists)
        if os.path.exists(ssl_ca):
            db_config['ssl_ca'] = ssl_ca
            db_config['ssl_disabled'] = False
        else:
            # Fallback for local testing if no SSL cert is present
            logger.warning("SSL CA cert not found. Attempting insecure connection (okay for localhost, bad for cloud).")
        
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Database Connection Error: {err}")
        return None

# --- HELPER: ANOMALY CHECKER ---
def check_for_anomalies(raw_inputs):
    anomalies = []
    ndvi = float(raw_inputs.get('NDVI_BOHOR') or 0.0)
    if ndvi < 0.2: anomalies.append("Very low NDVI detected. Field may be bare or facing severe stress.")
    ph = float(raw_inputs.get('SOIL_pH') or 0.0)
    if ph < 5.0 or ph > 7.5: anomalies.append(f"Soil pH ({ph:.1f}) is outside the optimal 5.5-7.0 range.")
    tmin = float(raw_inputs.get('TMIN_All') or 0); tmax = float(raw_inputs.get('TMAX_All') or 0)
    if tmin < 15 or tmax > 40: anomalies.append("Extreme temperature forecast detected.")
    return anomalies

# --- HELPER: GEE DATA ---
def get_gee_data(lon, lat, target_date):
    result = {'latest_ndvi': 0.65, 'soil_ph': 5.5, 'soil_cec': 12.0, 'soil_oc': 1.5}
    try:
        point = ee.Geometry.Point(lon, lat); area = point.buffer(50)
        end_date = ee.Date(target_date.strftime('%Y-%m-%d'))
        start_date_recent = end_date.advance(-180, 'day')

        # NDVI
        try:
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(area).filterDate(start_date_recent, end_date).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            def calculate_ndvi(image): return image.normalizedDifference(['B8', 'B4']).rename('NDVI').copyProperties(image, ['system:time_start'])
            recent_image = s2.map(calculate_ndvi).sort('system:time_start', False).first()
            if recent_image:
                val = recent_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=area, scale=10).get('NDVI')
                if val.getInfo(): result['latest_ndvi'] = float(val.getInfo())
        except Exception: pass

        # Soil
        try:
            ph_img = ee.Image("projects/soilgrids-isric/phh2o_mean").select('phh2o_0-5cm_mean')
            cec_img = ee.Image("projects/soilgrids-isric/cec_mean").select('cec_0-5cm_mean')
            oc_img = ee.Image("projects/soilgrids-isric/soc_mean").select('soc_0-5cm_mean')
            
            # Reduce regions
            data = ee.Image.cat([ph_img, cec_img, oc_img]).reduceRegion(reducer=ee.Reducer.firstNonNull(), geometry=point, scale=250).getInfo()
            
            if data:
                if 'phh2o_0-5cm_mean' in data: result['soil_ph'] = float(data['phh2o_0-5cm_mean']) / 10.0
                if 'cec_0-5cm_mean' in data: result['soil_cec'] = float(data['cec_0-5cm_mean']) / 10.0
                if 'soc_0-5cm_mean' in data: result['soil_oc'] = float(data['soc_0-5cm_mean']) / 100.0
                
        except Exception as soil_err: logger.error(f"GEE Err Soil: {soil_err}")
    except Exception as e: logger.error(f"GEE General Error: {e}")
    return result

# --- HELPER: NASA POWER SRAD ---
def get_historical_srad(lon, lat, days_back=365):
    historical_srad_data = {'dates': [], 'values': [], 'daily_values': []}
    try:
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=days_back - 1)
        url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN&community=RE&longitude={lon}&latitude={lat}&start={start_date.strftime('%Y%m%d')}&end={end_date.strftime('%Y%m%d')}&format=JSON"
        
        resp = requests.get(url, timeout=20); resp.raise_for_status()
        data = resp.json().get('properties', {}).get('parameter', {}).get('ALLSKY_SFC_SW_DWN', {})
        
        monthly_sums = {}; monthly_counts = {}
        for d, val in data.items():
            if val >= -99:
                historical_srad_data['daily_values'].append(float(val))
                m_key = d[:6] # YYYYMM
                monthly_sums[m_key] = monthly_sums.get(m_key, 0) + float(val)
                monthly_counts[m_key] = monthly_counts.get(m_key, 0) + 1
        
        for m in sorted(monthly_sums.keys()):
            # Convert YYYYMM to readable format if needed, here keeping simple for chart
            month_label = f"{m[:4]}-{m[4:]}"
            historical_srad_data['dates'].append(month_label)
            historical_srad_data['values'].append(monthly_sums[m] / monthly_counts[m])
            
    except Exception as e: logger.error(f"SRAD History Error: {e}")
    return historical_srad_data

def get_365_day_avg_srad(lon, lat):
    data = get_historical_srad(lon, lat)
    vals = data.get('daily_values', [])
    return sum(vals)/len(vals) if vals else 4.5

# --- HELPER: 3-DAY FORECAST ---
def get_3day_forecast(lon, lat):
    forecast_data = []
    key = os.environ.get('WEATHERAPI_KEY')
    if not key: return []
    
    try:
        # Request 3 days of forecast
        url = f"http://api.weatherapi.com/v1/forecast.json?key={key}&q={lat},{lon}&days=3&aqi=no&alerts=no"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        
        # Parse the response
        days = resp.json().get('forecast', {}).get('forecastday', [])
        for d in days:
            # Determine if it's Today, Tomorrow, or day name
            d_date = datetime.strptime(d['date'], '%Y-%m-%d').date()
            today = date.today()
            if d_date == today:
                day_label = "Today"
            elif d_date == today + timedelta(days=1):
                day_label = "Tomorrow"
            else:
                day_label = d_date.strftime('%A') # e.g., "Friday"

            forecast_data.append({
                'label': day_label,
                'date': d['date'],
                'condition': d['day']['condition']['text'],
                'icon': d['day']['condition']['icon'],
                'temp_max': d['day']['maxtemp_c'],
                'temp_min': d['day']['mintemp_c'],
                'rain': d['day']['totalprecip_mm']
            })
    except Exception as e:
        logger.error(f"3-Day Forecast Error: {e}")
        
    return forecast_data

def get_single_day_srad(lon, lat, target_date):
    try:
        d_str = target_date.strftime('%Y%m%d')
        url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN&community=RE&longitude={lon}&latitude={lat}&start={d_str}&end={d_str}&format=JSON"
        resp = requests.get(url, timeout=10); resp.raise_for_status()
        val = resp.json().get('properties', {}).get('parameter', {}).get('ALLSKY_SFC_SW_DWN', {}).get(d_str, -999)
        if val > -90: return float(val)
    except Exception: pass
    return get_365_day_avg_srad(lon, lat)



# --- HELPER: WEATHER API ---
def get_historical_or_forecast_weather(lon, lat, target_date):
    # Default values
    tmin, tmax, rain = 24.0, 32.0, 0.0
    key = os.environ.get('WEATHERAPI_KEY')
    if not key: return tmin, tmax, rain
    
    try:
        days_diff = (target_date - date.today()).days
        if days_diff < 0: # Past
            url = f"http://api.weatherapi.com/v1/history.json?key={key}&q={lat},{lon}&dt={target_date.strftime('%Y-%m-%d')}"
            resp = requests.get(url, timeout=10); resp.raise_for_status()
            day = resp.json().get('forecast', {}).get('forecastday', [])[0].get('day', {})
            tmin = day.get('mintemp_c', tmin); tmax = day.get('maxtemp_c', tmax); rain = day.get('totalprecip_mm', rain)
        else: # Future/Today
            url = f"http://api.weatherapi.com/v1/forecast.json?key={key}&q={lat},{lon}&days=3&aqi=no&alerts=no"
            resp = requests.get(url, timeout=10); resp.raise_for_status()
            forecast = resp.json().get('forecast', {}).get('forecastday', [])
            idx = 0 if days_diff <= 0 else (days_diff if days_diff < 3 else 0)
            if idx < len(forecast):
                day = forecast[idx].get('day', {})
                tmin = day.get('mintemp_c', tmin); tmax = day.get('maxtemp_c', tmax); rain = day.get('totalprecip_mm', rain)
    except Exception as e: logger.error(f"Weather API Error: {e}")
    return tmin, tmax, rain

# --- ML SETUP ---
normalization_params = {
    'NDVI_BOHOR': {'min': 0.0, 'max': 1.0, 'optimal': (0.6, 0.9)},
    'TMIN_All': {'min': 20.0, 'max': 30.0, 'optimal': (22.0, 27.0)},
    'TMAX_All': {'min': 25.0, 'max': 40.0, 'optimal': (30.0, 35.0)},
    'RAIN1': {'min': 0.0, 'max': 50.0, 'optimal': (5.0, 30.0)},
    'TotalSRAD': {'min': 0.0, 'max': 8.0, 'optimal': (4.0, 6.0)},
    'SOIL_pH': {'min': 4.0, 'max': 8.0, 'optimal': (5.5, 7.0)},
    'SOIL_CEC (meq/100)': {'min': 5.0, 'max': 40.0, 'optimal': (15.0, 30.0)},
    'SOIL_OC': {'min': 0.5, 'max': 10.0, 'optimal': (1.0, 5.0)}
}
def normalize_value(value, feature_name):
    if feature_name not in normalization_params: return value
    p=normalization_params[feature_name]; 
    return max(0.0, min(1.0, (value-p['min'])/(p['max']-p['min']))) if p['max']!=p['min'] else 0.5

features=['NDVI_BOHOR','TMIN_All','TMAX_All','RAIN1','TotalSRAD','SOIL_pH','SOIL_CEC (meq/100)','SOIL_OC']
model = None

try:
    csv_path = os.path.join(basedir, "datasetPadi_synthetic_normalized_orange.csv") 
    df = pd.read_csv(csv_path, header=0, skiprows=[1, 2])
    X = df[features]; y = pd.to_numeric(df['Hasil Kasar'], errors='coerce')
    full_df = X.join(y).dropna()
    model = Ridge(); model.fit(full_df[features], full_df['Hasil Kasar'])
    logger.info("Model trained successfully.")
except Exception as e:
    logger.error(f"Model Training Error: {e}")

# --- ROUTES ---

@app.route('/')
def login_page():
    if 'ic' in session: return redirect(url_for('dashboard_home'))
    return render_template("login.html")

@app.route('/register')
def register_page(): return render_template("register.html")

@app.route('/register_user', methods=['POST'])
def register_user():
    f=request.form
    conn = get_db_connection()
    if not conn: flash("Database error", "error"); return redirect(url_for('register_page'))
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (fullname,ic,state,phone,password) VALUES (%s,%s,%s,%s,%s)", 
                   (f['fullname'], f['ic'], f['state'], f['phone'], f['password']))
        conn.commit()
        flash("Registered!", "success"); return redirect(url_for('login_page'))
    except Exception as e:
        flash("Registration failed. IC may exist.", "error"); logger.error(e)
        return redirect(url_for('register_page'))
    finally: cur.close(); conn.close()

@app.route('/login_user', methods=['POST'])
def login_user():
    conn = get_db_connection()
    if not conn: flash("Database error", "error"); return redirect(url_for('login_page'))
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE ic=%s", (request.form['ic'],))
    user = cur.fetchone()
    cur.close(); conn.close()
    if user and user['password'] == request.form['password']:
        session['ic'] = user['ic']; session['fullname'] = user['fullname']
        return redirect(url_for('dashboard_home'))
    flash("Invalid credentials", "error"); return redirect(url_for('login_page'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login_page'))

@app.route('/dashboard')
def dashboard_home():
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection()
    sessions = []
    if conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM planting_sessions WHERE user_ic=%s ORDER BY planting_date DESC", (session['ic'],))
        sessions = cur.fetchall()
        cur.close(); conn.close()
    return render_template("dashboard_home.html", sessions=sessions, today=date.today())

@app.route('/new_session')
def new_session_form():
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection(); templates = []
    if conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM workflow_templates")
        templates = cur.fetchall()
        cur.close(); conn.close()
    return render_template("new_session_form.html", templates=templates)

@app.route('/create_session', methods=['POST'])
def create_session():
    if 'ic' not in session: return redirect(url_for('login_page'))
    if not model: flash("Model not loaded", "error"); return redirect(url_for('dashboard_home'))
    
    f = request.form
    try:
        # Get Weather/Coords
        key = os.environ.get('WEATHERAPI_KEY')
        geo_url = f"http://api.weatherapi.com/v1/search.json?key={key}&q={f['location']}"
        geo_resp = requests.get(geo_url); geo_resp.raise_for_status()
        loc_data = geo_resp.json()[0]
        lat, lon = float(loc_data['lat']), float(loc_data['lon'])
        
        p_date = datetime.strptime(f['planting_date'], '%Y-%m-%d').date()
        
        # Get Inputs
        tmin, tmax, rain = get_historical_or_forecast_weather(lon, lat, p_date)
        srad = get_single_day_srad(lon, lat, p_date)
        gee = get_gee_data(lon, lat, p_date)
        
        raw = {
            'NDVI_BOHOR': gee['latest_ndvi'], 'TMIN_All': tmin, 'TMAX_All': tmax,
            'RAIN1': rain, 'TotalSRAD': srad, 
            'SOIL_pH': float(f['SOIL_pH']) if f.get('SOIL_pH') else gee['soil_ph'],
            'SOIL_CEC (meq/100)': float(f['SOIL_CEC']) if f.get('SOIL_CEC') else gee['soil_cec'],
            'SOIL_OC': float(f['SOIL_OC']) if f.get('SOIL_OC') else gee['soil_oc']
        }
        
        # Predict
        input_vector = pd.DataFrame([{k: normalize_value(v, k) for k, v in raw.items()}])[features]
        yield_ha = max(0, float(model.predict(input_vector)[0]))
        total_yield = yield_ha * float(f['size'])
        
        # Save DB
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        
        # Get template offset
        cur.execute("SELECT harvest_day_offset FROM workflow_templates WHERE id=%s", (f['template_id'],))
        offset = cur.fetchone()['harvest_day_offset']
        h_date = p_date + timedelta(days=offset)
        
        # Create Session
        cur.execute("""INSERT INTO planting_sessions 
            (user_ic, session_name, location, latitude, longitude, field_size, planting_date, expected_harvest_date, predicted_yield_per_ha, predicted_total_yield, template_id_used)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (session['ic'], f['session_name'], f['location'], lat, lon, f['size'], p_date, h_date, yield_ha, total_yield, f['template_id']))
        sess_id = cur.lastrowid
        
        # Save History
        cur.execute("""INSERT INTO prediction_history 
            (session_id, TMIN_All, TMAX_All, RAIN1, NDVI_BOHOR, TotalSRAD, SOIL_pH, SOIL_CEC, SOIL_OC)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (sess_id, raw['TMIN_All'], raw['TMAX_All'], raw['RAIN1'], raw['NDVI_BOHOR'], raw['TotalSRAD'], raw['SOIL_pH'], raw['SOIL_CEC (meq/100)'], raw['SOIL_OC']))
            
        # Create Tasks
        cur.execute("SELECT task_name, days_offset FROM workflow_template_steps WHERE template_id=%s", (f['template_id'],))
        for step in cur.fetchall():
            t_date = p_date + timedelta(days=step['days_offset'])
            status = 'skipped' if t_date < date.today() else ('in_process' if t_date == date.today() else 'soon')
            cur.execute("INSERT INTO farmer_task_steps (session_id, user_ic, task_id, start_date, status) VALUES (%s,%s,%s,%s,%s)",
                       (sess_id, session['ic'], step['task_name'], t_date, status))
                       
        conn.commit(); cur.close(); conn.close()
        flash("Session Created!", "success"); return redirect(url_for('session_dashboard', session_id=sess_id))
        
    except Exception as e:
        logger.error(f"Create Session Error: {e}")
        flash(f"Error: {e}", "error"); return redirect(url_for('new_session_form'))

@app.route('/session/<int:session_id>')
def session_dashboard(session_id):
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection()
    if not conn: return redirect(url_for('dashboard_home'))
    
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM planting_sessions WHERE session_id=%s AND user_ic=%s", (session_id, session['ic']))
    sess_data = cur.fetchone()
    
    if not sess_data: cur.close(); conn.close(); return redirect(url_for('dashboard_home'))
    
    # Get Tasks
    sort = request.args.get('sort_by', 'default')
    sql = "SELECT * FROM farmer_task_steps WHERE session_id=%s"
    if sort in ['soon','in_process','completed','skipped']: sql += f" AND status='{sort}'"
    sql += " ORDER BY start_date ASC"
    cur.execute(sql, (session_id,))
    tasks = cur.fetchall()
    
    # Get Prediction Data
    cur.execute("SELECT * FROM prediction_history WHERE session_id=%s", (session_id,))
    hist = cur.fetchone() or {}
    cur.close(); conn.close()
    
    # --- DATA PROCESSING & ALERTS ---
    input_breakdown = {'raw': {}, 'normalized': {}, 'anomalies': [], 'advice': []}
    alert_memo = None # Default is no alert
    
    if hist:
        raw = {k: hist.get(k) for k in features if k in hist}
        input_breakdown['raw'] = raw
        input_breakdown['normalized'] = {k: f"{normalize_value(v, k):.2f}" for k,v in raw.items() if v is not None}
        
        # Check for suitability anomalies
        anomalies = check_for_anomalies(raw)
        input_breakdown['anomalies'] = anomalies
        
        # Logic for Alert Memo
        if anomalies:
            alert_memo = {
                "level": "danger", # render as red box
                "title": "NOT SUITABLE FOR PLANTING",
                "message": f"Critical issues detected: {'; '.join(anomalies)}. Planting is high risk."
            }
        elif raw.get('SOIL_pH', 6) < 5.5:
             # Soft warning
             alert_memo = {
                "level": "warning", # render as yellow box
                "title": "CONDITIONS SUB-OPTIMAL",
                "message": "Soil pH is low. Yield may be reduced without treatment."
             }
        else:
             # All good
             alert_memo = {
                "level": "success", # render as green box
                "title": "CONDITIONS SUITABLE",
                "message": "Environmental factors look good for paddy cultivation."
             }

    # --- WEATHER & GRAPHS ---
    # 1. Get 3-Day Forecast
    weather_3day = get_3day_forecast(sess_data['longitude'], sess_data['latitude'])
    
    # 2. Get Historical SRAD (Fixing the missing graph from previous request)
    srad_data = get_historical_srad(sess_data['longitude'], sess_data['latitude'])

    return render_template("session_dashboard.html", 
                           session_details=sess_data, 
                           tasks=tasks, 
                           input_breakdown=input_breakdown,
                           alert_memo=alert_memo,
                           weather_forecast=weather_3day, 
                           historical_srad_json=json.dumps(srad_data),
                           norm_params_json=json.dumps(normalization_params))

@app.route('/update_step', methods=['POST'])
def update_step():
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection(); cur = conn.cursor()
    f = request.form
    try:
        cur.execute("UPDATE farmer_task_steps SET status=%s, remarks=%s, detail1=%s, detail2=%s, completed_at=%s WHERE id=%s",
                   (f['status'], f['remarks'], f['detail1'], f['detail2'], datetime.now() if f['status']=='completed' else None, f['task_id']))
        conn.commit()
    except Exception as e: logger.error(e)
    finally: cur.close(); conn.close()
    return redirect(url_for('session_dashboard', session_id=f['session_id']))

@app.route('/delete_session/<int:session_id>', methods=['POST'])
def delete_session(session_id):
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM planting_sessions WHERE session_id=%s AND user_ic=%s", (session_id, session['ic']))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('dashboard_home'))

@app.route('/edit_session/<int:session_id>')
def edit_session_form(session_id):
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM planting_sessions WHERE session_id=%s", (session_id,))
    data = cur.fetchone()
    cur.close(); conn.close()
    return render_template("edit_session_form.html", session_data=data)

@app.route('/update_session/<int:session_id>', methods=['POST'])
def update_session(session_id):
    if 'ic' not in session: return redirect(url_for('login_page'))
    f = request.form
    conn = get_db_connection(); cur = conn.cursor()
    # Recalculate total yield if size changed
    cur.execute("UPDATE planting_sessions SET session_name=%s, field_size=%s, predicted_total_yield=predicted_yield_per_ha*%s WHERE session_id=%s",
               (f['session_name'], f['field_size'], f['field_size'], session_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for('session_dashboard', session_id=session_id))

@app.route('/settings')
def settings_page():
    if 'ic' not in session: return redirect(url_for('login_page'))
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE ic=%s", (session['ic'],))
    user = cur.fetchone(); cur.close(); conn.close()
    return render_template("settings.html", user=user)

# --- TEMPLATE FILTERS ---
@app.template_filter('timestamp_to_date')
def timestamp_to_date_filter(s):
    try: return datetime.fromtimestamp(int(s))
    except: return None

if __name__ == '__main__':
    # Render runs via Gunicorn, this is for local testing only
    app.run(debug=True)