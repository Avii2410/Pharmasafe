from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from itertools import combinations
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "pharmacy_secret_key_2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

engine = create_engine("sqlite:///pharmacy.db")
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    pharmacy_name = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    drug1 = Column(String)
    drug2 = Column(String)
    generic1 = Column(String)
    generic2 = Column(String)
    status = Column(String)
    total_cases = Column(Integer)
    searched_at = Column(DateTime, default=datetime.now)

class ADRReport(Base):
    __tablename__ = "adr_reports"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    patient_age = Column(Integer)
    patient_gender = Column(String)
    medicine = Column(String)
    side_effect = Column(String)
    severity = Column(String)
    description = Column(String)
    reported_at = Column(DateTime, default=datetime.now)

class Medicine(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    name = Column(String)
    generic_name = Column(String)
    quantity = Column(Integer)
    price = Column(Integer)
    expiry_date = Column(String)
    low_stock_threshold = Column(Integer, default=10)
    added_at = Column(DateTime, default=datetime.now)

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    customer_name = Column(String)
    total_amount = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True)
    sale_id = Column(Integer)
    medicine_name = Column(String)
    quantity = Column(Integer)
    price = Column(Integer)
    total = Column(Integer)

Base.metadata.create_all(engine)

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    pharmacy_name: str

class ADRCreate(BaseModel):
    patient_age: int
    patient_gender: str
    medicine: str
    side_effect: str
    severity: str
    description: str

class MedicineCreate(BaseModel):
    name: str
    generic_name: str
    quantity: int
    price: int
    expiry_date: str
    low_stock_threshold: int = 10

class SaleItemCreate(BaseModel):
    medicine_name: str
    quantity: int
    price: int

class SaleCreate(BaseModel):
    customer_name: str
    items: list[SaleItemCreate]

INDIAN_MEDICINES = {
    "dolo 650": "acetaminophen", "dolo": "acetaminophen", "crocin": "acetaminophen",
    "paracetamol": "acetaminophen", "calpol": "acetaminophen", "febrex": "acetaminophen",
    "metacin": "acetaminophen", "pacimol": "acetaminophen", "p 500": "acetaminophen",
    "p 650": "acetaminophen", "ibuprofen": "ibuprofen", "brufen": "ibuprofen",
    "combiflam": "ibuprofen", "ibugesic": "ibuprofen", "advil": "ibuprofen",
    "nurofen": "ibuprofen", "meftal spas": "mefenamic acid", "meftal": "mefenamic acid",
    "ponstan": "mefenamic acid", "mefkind": "mefenamic acid", "mefenamic acid": "mefenamic acid",
    "aspirin": "aspirin", "disprin": "aspirin", "ecosprin": "aspirin", "loprin": "aspirin",
    "diclofenac": "diclofenac", "voveran": "diclofenac", "voltaren": "diclofenac",
    "diclomol": "diclofenac", "naproxen": "naproxen", "naprosyn": "naproxen",
    "amoxicillin": "amoxicillin", "mox": "amoxicillin", "novamox": "amoxicillin",
    "azithromycin": "azithromycin", "azee": "azithromycin", "azithral": "azithromycin",
    "ciprofloxacin": "ciprofloxacin", "cifran": "ciprofloxacin", "ciplox": "ciprofloxacin",
    "cefixime": "cefixime", "taxim": "cefixime", "zifi": "cefixime",
    "doxycycline": "doxycycline", "doxt": "doxycycline", "metronidazole": "metronidazole",
    "flagyl": "metronidazole", "metrogyl": "metronidazole",
    "augmentin": "amoxicillin clavulanate", "clavam": "amoxicillin clavulanate",
    "fluconazole": "fluconazole", "forcan": "fluconazole", "omeprazole": "omeprazole",
    "omez": "omeprazole", "pantoprazole": "pantoprazole", "pan 40": "pantoprazole",
    "pantocid": "pantoprazole", "rabeprazole": "rabeprazole", "razo": "rabeprazole",
    "domperidone": "domperidone", "domstal": "domperidone", "metformin": "metformin",
    "glycomet": "metformin", "glucophage": "metformin", "glimepiride": "glimepiride",
    "amaryl": "glimepiride", "sitagliptin": "sitagliptin", "januvia": "sitagliptin",
    "amlodipine": "amlodipine", "amlong": "amlodipine", "norvasc": "amlodipine",
    "telmisartan": "telmisartan", "telma": "telmisartan", "losartan": "losartan",
    "losacar": "losartan", "metoprolol": "metoprolol", "metolar": "metoprolol",
    "atenolol": "atenolol", "ramipril": "ramipril", "cardace": "ramipril",
    "atorvastatin": "atorvastatin", "lipitor": "atorvastatin", "atorva": "atorvastatin",
    "rosuvastatin": "rosuvastatin", "crestor": "rosuvastatin", "cetirizine": "cetirizine",
    "cetzine": "cetirizine", "zyrtec": "cetirizine", "loratadine": "loratadine",
    "lorfast": "loratadine", "fexofenadine": "fexofenadine", "allegra": "fexofenadine",
    "montelukast": "montelukast", "montair": "montelukast", "salbutamol": "salbutamol",
    "asthalin": "salbutamol", "prednisolone": "prednisolone", "wysolone": "prednisolone",
    "dexamethasone": "dexamethasone", "dexona": "dexamethasone",
    "levothyroxine": "levothyroxine", "eltroxin": "levothyroxine", "thyronorm": "levothyroxine",
    "tramadol": "tramadol", "pregabalin": "pregabalin", "lyrica": "pregabalin",
    "gabapentin": "gabapentin", "gabapin": "gabapentin", "warfarin": "warfarin",
    "warf": "warfarin", "clopidogrel": "clopidogrel", "clopivas": "clopidogrel",
    "plavix": "clopidogrel", "sertraline": "sertraline", "serta": "sertraline",
    "fluoxetine": "fluoxetine", "fludac": "fluoxetine", "escitalopram": "escitalopram",
    "nexito": "escitalopram",
}

def get_generic_name(medicine: str):
    return INDIAN_MEDICINES.get(medicine.lower().strip(), medicine.lower().strip())

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def check_pair(drug1, drug2):
    generic1 = get_generic_name(drug1)
    generic2 = get_generic_name(drug2)
    url = f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{generic1}+AND+patient.drug.medicinalproduct:{generic2}&limit=1"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        total = data["meta"]["results"]["total"]
        return {"drug1": drug1, "drug2": drug2, "generic1": generic1, "generic2": generic2, "status": "Warning!" if total > 0 else "Safe", "total_cases": total}
    return {"drug1": drug1, "drug2": drug2, "generic1": generic1, "generic2": generic2, "status": "Not Found", "total_cases": 0}

def generate_pdf(drug1, drug2, generic1, generic2, status, total_cases, message):
    filename = f"report_{drug1}_{drug2}.pdf".replace(" ", "_")
    filepath = f"./{filename}"
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    c.setFillColor(colors.HexColor("#2563EB"))
    c.rect(0, height - 80, width, 80, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, height - 50, "PharmaSafe - Drug Interaction Report")
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 68, f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 120, "Medicines Checked:")
    c.setFont("Helvetica", 12)
    c.drawString(40, height - 145, f"Medicine 1: {drug1.upper()}  (Generic: {generic1})")
    c.drawString(40, height - 165, f"Medicine 2: {drug2.upper()}  (Generic: {generic2})")
    if total_cases > 0:
        c.setFillColor(colors.HexColor("#FFFBEB"))
    else:
        c.setFillColor(colors.HexColor("#ECFDF5"))
    c.rect(30, height - 260, width - 60, 70, fill=True, stroke=False)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 210, f"Result: {status}")
    c.setFont("Helvetica", 12)
    c.drawString(40, height - 235, f"{message}")
    if total_cases > 0:
        c.setFillColor(colors.red)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(40, height - 290, f"Total Adverse Cases Reported: {total_cases}")
    c.setFillColor(colors.grey)
    c.setFont("Helvetica", 9)
    c.drawString(40, 60, "Disclaimer: This report is for informational purposes only.")
    c.drawString(40, 45, "Always consult a licensed pharmacist or doctor before taking medicines.")
    c.drawString(40, 30, "Data Source: OpenFDA Adverse Event Reporting System")
    c.save()
    return filepath

@app.get("/")
def home():
    return {"message": "PharmaSafe API Running!"}

@app.post("/signup")
def signup(user: UserCreate):
    db = SessionLocal()
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(name=user.name, email=user.email, hashed_password=hash_password(user.password), pharmacy_name=user.pharmacy_name)
    db.add(new_user)
    db.commit()
    db.close()
    return {"message": "Account created!"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    user = db.query(User).filter(User.email == form_data.username).first()
    db.close()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "name": user.name, "pharmacy_name": user.pharmacy_name}

@app.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"name": current_user.name, "email": current_user.email, "pharmacy_name": current_user.pharmacy_name}

@app.get("/check-interaction")
def check_interaction(drug1: str, drug2: str, current_user: User = Depends(get_current_user)):
    generic1 = get_generic_name(drug1)
    generic2 = get_generic_name(drug2)
    url = f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{generic1}+AND+patient.drug.medicinalproduct:{generic2}&limit=1"
    response = requests.get(url)
    db = SessionLocal()
    if response.status_code == 200:
        data = response.json()
        total = data["meta"]["results"]["total"]
        status = "Warning - Interaction Found!" if total > 0 else "No Interaction Found"
        message = f"{total} adverse event cases found" if total > 0 else "No adverse events found"
    else:
        status = "No Data Found"
        message = "Medicine not found in database"
        total = 0
    history = SearchHistory(user_id=current_user.id, drug1=drug1, drug2=drug2, generic1=generic1, generic2=generic2, status=status, total_cases=total)
    db.add(history)
    db.commit()
    db.close()
    return {"drug1": drug1, "drug2": drug2, "generic1": generic1, "generic2": generic2, "status": status, "total_cases": total, "message": message}

@app.get("/check-multiple")
def check_multiple(medicines: str, current_user: User = Depends(get_current_user)):
    medicine_list = [m.strip() for m in medicines.split(",") if m.strip()]
    if len(medicine_list) < 2:
        return {"error": "At least 2 medicines required"}
    results = []
    pairs = list(combinations(medicine_list, 2))
    for drug1, drug2 in pairs:
        result = check_pair(drug1, drug2)
        results.append(result)
        db = SessionLocal()
        history = SearchHistory(user_id=current_user.id, drug1=drug1, drug2=drug2, generic1=result["generic1"], generic2=result["generic2"], status=result["status"], total_cases=result["total_cases"])
        db.add(history)
        db.commit()
        db.close()
    total_warnings = sum(1 for r in results if r["total_cases"] > 0)
    return {"medicines": medicine_list, "total_pairs_checked": len(pairs), "total_warnings": total_warnings, "results": results}

@app.get("/history")
def get_history(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    history = db.query(SearchHistory).filter(SearchHistory.user_id == current_user.id).order_by(SearchHistory.searched_at.desc()).limit(10).all()
    db.close()
    return [{"id": h.id, "drug1": h.drug1, "drug2": h.drug2, "status": h.status, "total_cases": h.total_cases, "searched_at": h.searched_at.strftime("%d %b %Y, %I:%M %p")} for h in history]

@app.get("/download-report")
def download_report(drug1: str, drug2: str, status: str, total_cases: int, message: str):
    generic1 = get_generic_name(drug1)
    generic2 = get_generic_name(drug2)
    filepath = generate_pdf(drug1, drug2, generic1, generic2, status, total_cases, message)
    return FileResponse(filepath, media_type="application/pdf", filename=f"PharmaSafe_Report_{drug1}_{drug2}.pdf".replace(" ", "_"))

@app.get("/pharmacies")
def get_pharmacies(medicine: str):
    pharmacies = [
        {"id": 1, "name": "Arvind Medical Store", "lat": 23.2599, "lng": 77.4126, "address": "MP Nagar, Bhopal", "phone": "9876543210", "medicines": ["dolo 650", "meftal spas", "aspirin", "combiflam", "crocin"]},
        {"id": 2, "name": "Sharma Pharmacy", "lat": 23.2630, "lng": 77.4200, "address": "Arera Colony, Bhopal", "phone": "9876543211", "medicines": ["dolo 650", "warfarin", "metformin", "azithromycin"]},
        {"id": 3, "name": "City Medical", "lat": 23.2550, "lng": 77.4050, "address": "New Market, Bhopal", "phone": "9876543212", "medicines": ["meftal spas", "ibuprofen", "cetirizine", "pantoprazole"]},
        {"id": 4, "name": "Sai Medical Store", "lat": 23.2680, "lng": 77.4300, "address": "Kolar Road, Bhopal", "phone": "9876543213", "medicines": ["aspirin", "metformin", "atorvastatin", "dolo 650"]},
        {"id": 5, "name": "Life Care Pharmacy", "lat": 23.2520, "lng": 77.4180, "address": "Habibganj, Bhopal", "phone": "9876543214", "medicines": ["combiflam", "cetirizine", "azithromycin", "meftal spas"]},
    ]
    medicine_lower = medicine.lower().strip()
    available = [p for p in pharmacies if medicine_lower in p["medicines"]]
    not_available = [p for p in pharmacies if medicine_lower not in p["medicines"]]
    return {"medicine": medicine, "available_count": len(available), "available": available, "not_available": not_available}

@app.get("/substitutes")
def get_substitutes(medicine: str):
    substitutes_db = {
        "dolo 650": [{"brand": "Crocin 650", "generic": "Paracetamol 650mg", "price": "Rs 30", "company": "GSK"}, {"brand": "Calpol 650", "generic": "Paracetamol 650mg", "price": "Rs 28", "company": "GSK"}, {"brand": "Pacimol 650", "generic": "Paracetamol 650mg", "price": "Rs 25", "company": "Ipca"}],
        "crocin": [{"brand": "Dolo 650", "generic": "Paracetamol 650mg", "price": "Rs 30", "company": "Micro Labs"}, {"brand": "Calpol", "generic": "Paracetamol 500mg", "price": "Rs 20", "company": "GSK"}],
        "meftal spas": [{"brand": "Mefkind Spas", "generic": "Mefenamic Acid + Dicyclomine", "price": "Rs 45", "company": "Mankind"}, {"brand": "Cyclopam", "generic": "Mefenamic Acid + Dicyclomine", "price": "Rs 40", "company": "Indoco"}],
        "combiflam": [{"brand": "Brufen Plus", "generic": "Ibuprofen + Paracetamol", "price": "Rs 35", "company": "Abbott"}, {"brand": "Ibugesic Plus", "generic": "Ibuprofen + Paracetamol", "price": "Rs 30", "company": "Cipla"}],
        "pan 40": [{"brand": "Pantocid 40", "generic": "Pantoprazole 40mg", "price": "Rs 65", "company": "Sun Pharma"}, {"brand": "Pantodac 40", "generic": "Pantoprazole 40mg", "price": "Rs 60", "company": "Zydus"}],
        "omez": [{"brand": "Omeprazole 20", "generic": "Omeprazole 20mg", "price": "Rs 35", "company": "Generic"}, {"brand": "Ocid", "generic": "Omeprazole 20mg", "price": "Rs 30", "company": "Cipla"}],
        "allegra": [{"brand": "Fexofast 120", "generic": "Fexofenadine 120mg", "price": "Rs 55", "company": "Sun Pharma"}, {"brand": "Telfast 120", "generic": "Fexofenadine 120mg", "price": "Rs 60", "company": "Sanofi"}],
        "telma": [{"brand": "Telsartan 40", "generic": "Telmisartan 40mg", "price": "Rs 75", "company": "Ipca"}, {"brand": "Telvas 40", "generic": "Telmisartan 40mg", "price": "Rs 70", "company": "Emcure"}],
    }
    medicine_lower = medicine.lower().strip()
    subs = substitutes_db.get(medicine_lower, [])
    if subs:
        return {"medicine": medicine, "found": True, "count": len(subs), "substitutes": subs, "message": f"{len(subs)} substitutes mile"}
    else:
        return {"medicine": medicine, "found": False, "count": 0, "substitutes": [], "message": "Koi substitute nahi mila"}

@app.post("/report-adr")
def report_adr(adr: ADRCreate, current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    new_adr = ADRReport(user_id=current_user.id, patient_age=adr.patient_age, patient_gender=adr.patient_gender, medicine=adr.medicine, side_effect=adr.side_effect, severity=adr.severity, description=adr.description)
    db.add(new_adr)
    db.commit()
    db.close()
    return {"message": "ADR Report submitted!"}

@app.get("/adr-reports")
def get_adr_reports(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    reports = db.query(ADRReport).order_by(ADRReport.reported_at.desc()).all()
    db.close()
    return [{"id": r.id, "patient_age": r.patient_age, "patient_gender": r.patient_gender, "medicine": r.medicine, "side_effect": r.side_effect, "severity": r.severity, "description": r.description, "reported_at": r.reported_at.strftime("%d %b %Y, %I:%M %p")} for r in reports]

@app.get("/adr-stats")
def get_adr_stats(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    reports = db.query(ADRReport).all()
    db.close()
    total = len(reports)
    severe = len([r for r in reports if r.severity == "Severe"])
    moderate = len([r for r in reports if r.severity == "Moderate"])
    mild = len([r for r in reports if r.severity == "Mild"])
    medicine_counts = {}
    for r in reports:
        medicine_counts[r.medicine] = medicine_counts.get(r.medicine, 0) + 1
    top_medicines = sorted(medicine_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    return {"total": total, "severe": severe, "moderate": moderate, "mild": mild, "top_medicines": [{"medicine": m, "count": c} for m, c in top_medicines]}

@app.post("/medicines")
def add_medicine(med: MedicineCreate, current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    new_med = Medicine(user_id=current_user.id, name=med.name, generic_name=med.generic_name, quantity=med.quantity, price=med.price, expiry_date=med.expiry_date, low_stock_threshold=med.low_stock_threshold)
    db.add(new_med)
    db.commit()
    db.close()
    return {"message": "Medicine added!"}

@app.get("/medicines")
def get_medicines(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    medicines = db.query(Medicine).filter(Medicine.user_id == current_user.id).all()
    db.close()
    return [{"id": m.id, "name": m.name, "generic_name": m.generic_name, "quantity": m.quantity, "price": m.price, "expiry_date": m.expiry_date, "low_stock_threshold": m.low_stock_threshold, "status": "low" if m.quantity <= m.low_stock_threshold else "ok"} for m in medicines]

@app.delete("/medicines/{medicine_id}")
def delete_medicine(medicine_id: int, current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    med = db.query(Medicine).filter(Medicine.id == medicine_id, Medicine.user_id == current_user.id).first()
    if med:
        db.delete(med)
        db.commit()
    db.close()
    return {"message": "Deleted!"}

@app.get("/analytics")
def get_analytics(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    medicines = db.query(Medicine).filter(Medicine.user_id == current_user.id).all()
    sales = db.query(Sale).filter(Sale.user_id == current_user.id).all()
    db.close()
    from datetime import date
    today = date.today()
    total_stock_value = sum(m.quantity * m.price for m in medicines)
    low_stock = [m for m in medicines if m.quantity <= m.low_stock_threshold]
    expiring_soon = []
    for m in medicines:
        try:
            exp = datetime.strptime(m.expiry_date, "%Y-%m-%d").date()
            days_left = (exp - today).days
            if days_left <= 90:
                expiring_soon.append({"name": m.name, "expiry_date": m.expiry_date, "days_left": days_left, "quantity": m.quantity})
        except:
            pass
    today_sales = sum(s.total_amount for s in sales if s.created_at.date() == today)
    total_sales = sum(s.total_amount for s in sales)
    return {
        "total_medicines": len(medicines),
        "total_stock_value": total_stock_value,
        "low_stock_count": len(low_stock),
        "expiring_soon_count": len(expiring_soon),
        "low_stock": [{"name": m.name, "quantity": m.quantity, "threshold": m.low_stock_threshold} for m in low_stock],
        "expiring_soon": sorted(expiring_soon, key=lambda x: x["days_left"]),
        "today_sales": today_sales,
        "total_sales": total_sales,
        "total_bills": len(sales)
    }

@app.post("/sales")
def create_sale(sale: SaleCreate, current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    total = sum(item.quantity * item.price for item in sale.items)
    new_sale = Sale(user_id=current_user.id, customer_name=sale.customer_name, total_amount=total)
    db.add(new_sale)
    db.flush()
    for item in sale.items:
        sale_item = SaleItem(sale_id=new_sale.id, medicine_name=item.medicine_name, quantity=item.quantity, price=item.price, total=item.quantity * item.price)
        db.add(sale_item)
        med = db.query(Medicine).filter(Medicine.user_id == current_user.id, Medicine.name.ilike(item.medicine_name)).first()
        if med:
            med.quantity = max(0, med.quantity - item.quantity)
    db.commit()
    sale_id = new_sale.id
    db.close()
    return {"message": "Bill bana gaya!", "sale_id": sale_id, "total": total}

@app.get("/sales")
def get_sales(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    sales = db.query(Sale).filter(Sale.user_id == current_user.id).order_by(Sale.created_at.desc()).limit(20).all()
    result = []
    for s in sales:
        items = db.query(SaleItem).filter(SaleItem.sale_id == s.id).all()
        result.append({"id": s.id, "customer_name": s.customer_name, "total_amount": s.total_amount, "created_at": s.created_at.strftime("%d %b %Y, %I:%M %p"), "items": [{"medicine_name": i.medicine_name, "quantity": i.quantity, "price": i.price, "total": i.total} for i in items]})
    db.close()
    return result
@app.get("/check-counterfeit")
def check_counterfeit(batch_number: str = None, medicine_name: str = None):
    results = {}
    
    # Check FDA Drug Recalls
    if medicine_name:
        try:
            url = f"https://api.fda.gov/drug/enforcement.json?search=product_description:{medicine_name}&limit=3"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                total = data["meta"]["results"]["total"]
                recalls = []
                for item in data.get("results", []):
                    recalls.append({
                        "recall_number": item.get("recall_number", "N/A"),
                        "reason": item.get("reason_for_recall", "N/A")[:100],
                        "status": item.get("status", "N/A"),
                        "date": item.get("recall_initiation_date", "N/A"),
                        "company": item.get("recalling_firm", "N/A"),
                        "classification": item.get("classification", "N/A")
                    })
                results["recall_check"] = {
                    "total_recalls": total,
                    "recalls": recalls,
                    "status": "DANGER - Recalls Found!" if total > 0 else "SAFE - No Recalls Found"
                }
            else:
                results["recall_check"] = {"total_recalls": 0, "recalls": [], "status": "SAFE - No Recalls Found"}
        except:
            results["recall_check"] = {"total_recalls": 0, "recalls": [], "status": "Could not check"}

    # Verification Checklist
    results["verification_checklist"] = [
        {"check": "Hologram present on packaging", "importance": "High"},
        {"check": "Batch number clearly printed", "importance": "High"},
        {"check": "Manufacturing date visible", "importance": "High"},
        {"check": "Expiry date clearly printed", "importance": "High"},
        {"check": "FSSAI/CDSCO license number present", "importance": "High"},
        {"check": "Manufacturer address complete", "importance": "Medium"},
        {"check": "Medicine color/smell is normal", "importance": "Medium"},
        {"check": "Packaging is not tampered", "importance": "High"},
        {"check": "Barcode scans correctly", "importance": "Medium"},
        {"check": "Price matches MRP on packaging", "importance": "Medium"},
    ]

    results["medicine_name"] = medicine_name
    results["batch_number"] = batch_number
    return results

@app.post("/report-counterfeit")
def report_counterfeit(
    medicine_name: str,
    batch_number: str,
    manufacturer: str,
    issue: str,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": "Counterfeit report submitted!",
        "report_id": f"CF-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "medicine": medicine_name,
        "status": "Under Review",
        "next_step": "CDSCO aur local drug inspector ko bhi report karein: 1800-180-4000"
    }