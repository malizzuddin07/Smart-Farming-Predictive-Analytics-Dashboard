from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import requests
import mysql.connector
from datetime import datetime, date, timedelta
from sklearn.tree import DecisionTreeRegressor

app = Flask(__name__)
app.secret_key = 'SMART_FARMING'

# MySQL config
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'smart_farming'
}

# Load and train prediction model
df_raw = pd.read_csv("datasetPadi.csv", header=None)
df = df_raw.iloc[1:13].copy()
df.columns = df_raw.iloc[0]

features = [
    'Fertilizer_N', 'Fertilizer_P', 'Fertilizer_K',
    'SOIL_OC', 'TMIN_All', 'TMAX_All',
    'TotalGDD', 'GDD_Cummulative', 'RAIN1', 'NDVI_BOHOR'
]
target = 'Hasil Kasar'

X = df[features].astype(float)
y = df[target].astype(float)
model = DecisionTreeRegressor(max_depth=2)
model.fit(X, y)

@app.route('/')
def login():
    return render_template("login.html")

@app.route('/register')
def register():
    return render_template("register.html")

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.form
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE ic = %s", (data['ic'],))
    if cursor.fetchone():
        flash("IC already registered.")
        return redirect(url_for('register'))
    cursor.execute("INSERT INTO users (fullname, ic, state, phone, password) VALUES (%s, %s, %s, %s, %s)",
                   (data['fullname'], data['ic'], data['state'], data['phone'], data['password']))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('login'))

@app.route('/login_user', methods=['POST'])
def login_user():
    ic = request.form['ic']
    password = request.form['password']
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE ic = %s AND password = %s", (ic, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session['ic'] = user['ic']
        session['fullname'] = user['fullname']
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid IC or password.")
        return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'ic' not in session:
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM prediction_history WHERE ic = %s ORDER BY predicted_at DESC", (session['ic'],))
    history = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("dashboard.html", name=session['fullname'], history=history)

@app.route('/predict', methods=['POST'])
def predict():
    if 'ic' not in session:
        return redirect(url_for('login'))

    location = request.form['location']
    size = float(request.form['size'])
    API_KEY = "94952312460f37cc99e279e56b5ba41e"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units=metric"

    try:
        weather = requests.get(url).json()
        if weather.get('cod') != 200:
            flash(f"Error: {weather.get('message', 'Invalid location')}")
            return redirect(url_for('dashboard'))

        TMIN_All = weather['main']['temp_min']
        TMAX_All = weather['main']['temp_max']
        RAIN1 = weather.get('rain', {}).get('1h', 0.0)

        input_features = {
            'Fertilizer_N': 80, 'Fertilizer_P': 50, 'Fertilizer_K': 50,
            'SOIL_OC': 1.5, 'TMIN_All': TMIN_All, 'TMAX_All': TMAX_All,
            'TotalGDD': 1700, 'GDD_Cummulative': 1700, 'RAIN1': RAIN1,
            'NDVI_BOHOR': 0.65
        }

        X_input = pd.DataFrame([input_features])
        yield_per_ha = float(model.predict(X_input)[0])  # Ensure float, not float64
        total_yield = float(yield_per_ha * size)         # Ensure float

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prediction_history (ic, location, field_size, yield_per_hectare, total_yield)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['ic'], location, float(size), yield_per_ha, total_yield))

        # Insert farming workflow
        HLT_0 = date.today()
        workflow_steps = [
            (-60, "PRE-PLANTING: Soil suitability check"),
            (-30, "Bajak 1: Remove stubble, compost, plow"),
            (-10, "Bajak 2: Repeat plowing, break clumps"),
            (-3, "Place AWD tube (optional)"),
            (-2, "Bajak 3/Badai: Final leveling"),
            (0, "PLANTING: Certified seeds, apply water (AWD), direct seeding"),
            (1, "VEGETATIVE: AWD water control"),
            (6, "Fertilization 1: NPK 17:20:10"),
            (8, "Maintain 3–5 cm water, AWD & LCC tool"),
            (17, "Fertilization 2: Urea"),
            (28, "Fertilization 3: Compound + Supplement"),
            (45, "REPRODUCTIVE: Continue AWD"),
            (52, "Panicle formation care"),
            (62, "Fertilization 4: Supplement"),
            (68, "Maintain 5 cm water (flowering)"),
            (75, "GRAIN FILLING: Resume AWD"),
            (95, "Dry field to 0 cm"),
            (110, "HARVEST"),
            (121, "POST-HARVEST: Grain drying & storage"),
            (125, "End season: Cleanup & data analysis")
        ]

        for offset, task_id in workflow_steps:
            task_date = HLT_0 + timedelta(days=offset)
            status = 'soon' if task_date > date.today() else 'in_process'
            cursor.execute("""
                INSERT INTO farmer_task_steps (ic, task_id, start_date, status)
                VALUES (%s, %s, %s, %s)
            """, (session['ic'], task_id, task_date, status))

        conn.commit()
        cursor.close()
        conn.close()

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM prediction_history WHERE ic = %s ORDER BY predicted_at DESC", (session['ic'],))
        history = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template("dashboard.html", name=session['fullname'], history=history,
                               prediction=f"📍 {location}\n🌾 {yield_per_ha:.2f} tons/ha\n📦 {total_yield:.2f} tons for {size} ha")
    except Exception as e:
        return f"Prediction error: {e}"

@app.route('/workflow')
def workflow():
    if 'ic' not in session:
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        UPDATE farmer_task_steps
        SET status = 'in_process'
        WHERE ic = %s AND start_date = %s AND status = 'soon'
    """, (session['ic'], date.today()))
    conn.commit()

    cursor.execute("""
        SELECT * FROM farmer_task_steps
        WHERE ic = %s
        ORDER BY start_date
    """, (session['ic'],))
    tasks = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("workflow.html", tasks=tasks)

@app.route('/update_step', methods=['POST'])
def update_step():
    if 'ic' not in session:
        return 'Unauthorized', 401

    from flask import flash

    data = request.form
    task_id = data.get('task_id')
    status = data.get('status')
    remarks = data.get('remarks', '')
    detail1 = data.get('detail1', '')
    detail2 = data.get('detail2', '')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    if status == 'completed':
        cursor.execute("""
            UPDATE farmer_task_steps
            SET status = %s, completed_at = %s,
                remarks = %s, detail1 = %s, detail2 = %s
            WHERE ic = %s AND task_id = %s
        """, (
            status, datetime.now(), remarks,
            detail1, detail2, session['ic'], task_id
        ))
    else:
        cursor.execute("""
            UPDATE farmer_task_steps
            SET status = %s
            WHERE ic = %s AND task_id = %s
        """, (status, session['ic'], task_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("✅ Task updated successfully!")
    return redirect(url_for('workflow'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
