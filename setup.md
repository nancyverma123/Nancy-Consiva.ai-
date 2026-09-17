

## Instructions 

### What they need
- **Python 3.12.** Not 3.13 or 3.14, which fail to install some packages. Get it from https://www.python.org/downloads/release/python-3120/.


### Step 2: Create the Python environment and install packages

**Windows (PowerShell):**
```powershell
cd frontend\backend; py -3.12 -m venv venv; .\venv\Scripts\pip install -r requirements.txt
```



### Step 6: Start the app (2 terminals, every time)

**Terminal 1, backend** (from the `backend` folder):


Windows:
```powershell
.\venv\Scripts\uvicorn app.main:app --port 8000
```

**Terminal 2, frontend** (from the `frontend` folder, one level up):


Windows:
```powershell
py -m http.server 5500 --bind 127.0.0.1
```

### Step 7: Open **http://127.0.0.1:5500** 🎉

---
