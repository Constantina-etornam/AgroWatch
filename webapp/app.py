
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sys
from pathlib import Path
from datetime import datetime
import uuid
import sqlite3
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

app.config["SECRET_KEY"] = "agrowatch-secret-key-2026"
app.config["UPLOAD_FOLDER"] = str(PROJECT_ROOT / "results" / "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["DATABASE"] = str(PROJECT_ROOT / "agrowatch.db")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn



def score_crop_models(image_path):
    """
    Run all three crop models and return scores.
    Higher score = more likely that crop is in the image.
    """
    from ultralytics import YOLO
    import numpy as np

    model_paths = {
        "tomato": PROJECT_ROOT / "models" / "tomato_yolov8n" / "weights" / "best.pt",
        "maize": PROJECT_ROOT / "models" / "maize_yolov8n" / "weights" / "best.pt",
        "pineapple": PROJECT_ROOT / "models" / "pineapple_yolov8n" / "weights" / "best.pt",
    }
    scores = {}
    for crop_name, path in model_paths.items():
        if not path.exists():
            scores[crop_name] = 0.0
            continue
        model = YOLO(str(path))
        results = model.predict(source=str(image_path), conf=0.35, verbose=False)
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            scores[crop_name] = 0.0
        else:
            confs = r.boxes.conf.cpu().numpy()
            # Score = number of detections * mean confidence
            scores[crop_name] = float(len(confs) * confs.mean())
    return scores


def best_matching_crop(image_path, selected_crop, margin=0.10):
    """
    Stricter crop vs image check.
    - Selected crop should be the top-scoring model
    - Must reach a minimum score
    - If everything is weak, reject instead of guessing
    """
    scores = score_crop_models(image_path)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    predicted, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    selected_score = scores.get(selected_crop, 0.0)

    MIN_SCORE = 0.35          # below this = "not confident"
    CLEAR_LEAD = 0.08         # selected should not lose by much

    # Nothing confident → ask user to use a clearer crop photo
    if best_score < MIN_SCORE:
        msg = (
            "Could not confidently recognise the crop in this image. "
            "Please use a clear photo of the selected crop (leaf/plant close-up works best) "
            f"and make sure you selected the correct crop ({selected_crop})."
        )
        return False, predicted, scores, msg

    # Selected must be best, or very close to best
    if predicted != selected_crop:
        # Allow only if selected is almost as high as best
        if selected_score < best_score - CLEAR_LEAD:
            msg = (
                f"This image looks more like {predicted.upper()} than {selected_crop.upper()}. "
                f"Please change the crop selection to {predicted.upper()} (or upload a {selected_crop} image)."
            )
            return False, predicted, scores, msg

    # Selected is best (or close) but still too weak
    if selected_score < MIN_SCORE:
        msg = (
            f"Weak match for {selected_crop.upper()}. "
            "Try a clearer image of that crop, or select the crop that matches the photo."
        )
        return False, predicted, scores, msg

    return True, selected_crop, scores, None



def ensure_default_farm():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM Users WHERE phone_number = ?", ("0000000000",))
    row = cur.fetchone()
    if row:
        user_id = row["user_id"]
    else:
        cur.execute(
            "INSERT INTO Users (full_name, phone_number, password_hash, user_role, region) VALUES (?, ?, ?, ?, ?)",
            ("Default Farmer", "0000000000", generate_password_hash("default"), "farmer", "Volta")
        )
        user_id = cur.lastrowid

    cur.execute("SELECT farm_id FROM Farms WHERE user_id = ? AND farm_name = ?", (user_id, "Default Demo Farm"))
    row = cur.fetchone()
    if row:
        farm_id = row["farm_id"]
    else:
        cur.execute(
            "INSERT INTO Farms (user_id, farm_name, crop_type, area_hectares, district) VALUES (?, ?, ?, ?, ?)",
            (user_id, "Default Demo Farm", "tomato", 1.0, "Ho")
        )
        farm_id = cur.lastrowid
    conn.commit()
    conn.close()
    return farm_id


# -------------------------------------------------
# Public Pages
# -------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/app")
def main_app():
    """Main application (scan, market, resources, dashboard)"""
    return render_template("index.html")


# -------------------------------------------------
# Auth API
# -------------------------------------------------
@app.route("/api/auth/register", methods=["POST"])
def register():
    try:
        data = request.get_json(force=True)
        full_name = data.get("full_name", "").strip()
        phone = data.get("phone_number", "").strip()
        password = data.get("password", "")
        role = data.get("user_role", "").strip()
        region = data.get("region", "").strip()

        if not all([full_name, phone, password, role, region]):
            return jsonify({"status": "error", "message": "All fields are required"}), 400

        if role not in ["farmer", "buyer", "expert", "admin"]:
            return jsonify({"status": "error", "message": "Invalid role"}), 400

        conn = get_db()
        cur = conn.cursor()

        # Check if phone already exists
        cur.execute("SELECT user_id FROM Users WHERE phone_number = ?", (phone,))
        if cur.fetchone():
            conn.close()
            return jsonify({"status": "error", "message": "Phone number already registered"}), 400

        password_hash = generate_password_hash(password)
        cur.execute(
            """INSERT INTO Users (full_name, phone_number, password_hash, user_role, region)
               VALUES (?, ?, ?, ?, ?)""",
            (full_name, phone, password_hash, role, region)
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Account created successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True)
        phone = data.get("phone_number", "").strip()
        password = data.get("password", "")

        if not phone or not password:
            return jsonify({"status": "error", "message": "Phone and password required"}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM Users WHERE phone_number = ?", (phone,))
        user = cur.fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"status": "error", "message": "Invalid phone number or password"}), 401

        user_data = {
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "phone_number": user["phone_number"],
            "user_role": user["user_role"],
            "region": user["region"]
        }
        return jsonify({"status": "success", "user": user_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -------------------------------------------------
# Health & Crops
# -------------------------------------------------
@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


@app.route("/api/crops")
def list_crops():
    return jsonify({
        "crops": {
            "tomato": ["healthy", "late_blight", "leaf_curl_virus", "septoria_leaf_spot", "bacterial_spot"],
            "maize": ["healthy", "northern_leaf_blight", "common_rust", "gray_leaf_spot"],
            "pineapple": ["healthy", "mealybug_wilt", "heart_rot"]
        }
    })


# -------------------------------------------------
# Scan Endpoint (with DB save)
# -------------------------------------------------
@app.route("/api/scan", methods=["POST"])
def scan_field():
    """
    Single image OR multiple images (sequence).
    - 1 image  → detect + diagnose (simple track IDs)
    - 2+ images → detect each frame + Modified SORT for consistent track IDs
    """
    try:
        import numpy as np
        import cv2
        import importlib.util

        crop = request.form.get("crop", "").lower().strip()
        if crop not in ["tomato", "maize", "pineapple"]:
            return jsonify({"status": "error", "message": "Invalid crop"}), 400

        # Collect uploaded images (support both "image" and "images")
        files = request.files.getlist("images") or request.files.getlist("image")
        if not files or files[0].filename == "":
            return jsonify({"status": "error", "message": "No image file provided"}), 400

        # Load YOLO model
        from ultralytics import YOLO
        model_paths = {
            "tomato": PROJECT_ROOT / "models" / "tomato_yolov8n" / "weights" / "best.pt",
            "maize": PROJECT_ROOT / "models" / "maize_yolov8n" / "weights" / "best.pt",
            "pineapple": PROJECT_ROOT / "models" / "pineapple_yolov8n" / "weights" / "best.pt",
        }
        model_path = model_paths[crop]
        if not model_path.exists():
            return jsonify({"status": "error", "message": f"Model not found: {model_path}"}), 500
        model = YOLO(str(model_path))

        # Load Expert System
        expert_path = PROJECT_ROOT / "utils" / "expert_system.py"
        spec = importlib.util.spec_from_file_location("expert_system", expert_path)
        expert_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(expert_module)
        engine = expert_module.ExpertSystem()

        # Load Modified SORT
        sort_path = PROJECT_ROOT / "utils" / "modified_sort.py"
        spec2 = importlib.util.spec_from_file_location("modified_sort", sort_path)
        sort_module = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(sort_module)
        ModifiedSORT = sort_module.ModifiedSORT
        tracker = ModifiedSORT(max_age=30, min_hits=1, iou_threshold=0.3)

        all_frame_results = []
        saved_paths = []
        total_disease_flags = 0

        for idx, file in enumerate(files):
            ext = Path(file.filename).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png"]:
                continue

            filename = f"{uuid.uuid4().hex}{ext}"
            save_path = Path(app.config["UPLOAD_FOLDER"]) / filename
            file.save(save_path)
            saved_paths.append(str(save_path))

            # Check crop match on the first image only
            if len(saved_paths) == 1:
                ok, predicted_crop, crop_scores, mismatch_msg = best_matching_crop(str(save_path), crop)
                if not ok:
                    return jsonify({
                        "status": "error",
                        "message": mismatch_msg,
                        "selected_crop": crop,
                        "predicted_crop": predicted_crop,
                        "scores": crop_scores
                    }), 400

            # Read frame for ORB compensation
            frame = cv2.imread(str(save_path))

            # Detect
            results = model.predict(source=str(save_path), conf=0.5, verbose=False)
            result = results[0]

            dets = []
            raw_dets = []  # keep class + conf aligned with boxes
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                clss = result.boxes.cls.cpu().numpy().astype(int)
                names = result.names
                for box, conf, cls_id in zip(boxes, confs, clss):
                    dets.append([box[0], box[1], box[2], box[3], float(conf)])
                    raw_dets.append({
                        "class": names[cls_id],
                        "confidence": float(conf),
                        "bbox": [float(x) for x in box]
                    })

            dets = np.array(dets) if len(dets) else np.empty((0, 5))

            # Update tracker (works for 1 or many frames)
            tracks = tracker.update(dets, frame=frame)

            # Match tracks back to detections (by IoU) for class/diagnosis
            frame_detections = []
            for trk in tracks:
                x1, y1, x2, y2, track_id = trk
                # Find best matching raw detection
                best_iou, best_raw = 0, None
                for raw in raw_dets:
                    bx = raw["bbox"]
                    # simple IoU
                    xx1 = max(x1, bx[0]); yy1 = max(y1, bx[1])
                    xx2 = min(x2, bx[2]); yy2 = min(y2, bx[3])
                    w = max(0, xx2 - xx1); h = max(0, yy2 - yy1)
                    inter = w * h
                    area1 = (x2 - x1) * (y2 - y1)
                    area2 = (bx[2] - bx[0]) * (bx[3] - bx[1])
                    iou = inter / (area1 + area2 - inter + 1e-6)
                    if iou > best_iou:
                        best_iou, best_raw = iou, raw

                class_name = best_raw["class"] if best_raw else "unknown"
                conf = best_raw["confidence"] if best_raw else 0.0
                diagnosis = engine.diagnose(crop, class_name, conf) if class_name != "unknown" else {}
                if diagnosis.get("diagnosed_condition") and diagnosis.get("diagnosed_condition") != "healthy":
                    total_disease_flags += 1

                frame_detections.append({
                    "track_id": int(track_id),
                    "class": class_name,
                    "confidence": round(conf, 3),
                    "bbox": [round(float(x1), 1), round(float(y1), 1),
                             round(float(x2), 1), round(float(y2), 1)],
                    "diagnosis": diagnosis
                })

            all_frame_results.append({
                "frame_index": idx,
                "image_path": str(save_path),
                "detections": frame_detections
            })

        # Flatten for response + DB (use last frame as primary summary)
        primary = all_frame_results[-1]["detections"] if all_frame_results else []
        total_plants = len(primary)

        # Save to DB
        farm_id = ensure_default_farm()
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO Scans (farm_id, total_plants_detected, disease_flags_raised, image_path, crop_type)
               VALUES (?, ?, ?, ?, ?)""",
            (farm_id, total_plants, total_disease_flags, saved_paths[-1] if saved_paths else "", crop)
        )
        scan_id = cur.lastrowid

        for det in primary:
            box = det["bbox"]
            x1, y1, x2, y2 = box
            cur.execute(
                """INSERT INTO DetectedPlants
                   (scan_id, track_id, bbox_x, bbox_y, bbox_width, bbox_height, confidence_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (scan_id, det["track_id"], x1, y1, x2 - x1, y2 - y1, det["confidence"])
            )
            detection_db_id = cur.lastrowid
            diag = det.get("diagnosis", {})
            if diag.get("status") == "success":
                cur.execute(
                    """INSERT INTO DiseaseRecords
                       (detection_id, crop_type, diagnosed_condition, confidence, recommendation_text)
                       VALUES (?, ?, ?, ?, ?)""",
                    (detection_db_id, crop, diag.get("diagnosed_condition"),
                     diag.get("confidence"), diag.get("recommendation"))
                )
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "crop": crop,
            "scan_id": scan_id,
            "frames_processed": len(all_frame_results),
            "tracking_enabled": len(all_frame_results) >= 1,
            "total_plants_detected": total_plants,
            "disease_flags_raised": total_disease_flags,
            "detections": primary,
            "message": "Tracking applied (Modified SORT)" if len(files) >= 1 else "Detection complete"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -------------------------------------------------
# Market Endpoints
# -------------------------------------------------
@app.route("/api/market/listings", methods=["GET"])
def get_listings():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT listing_id, farmer_id, crop_type, quantity_kg, 
                   asking_price_ghs, harvest_date, listing_status, created_at
            FROM MarketListings WHERE listing_status = 'active'
            ORDER BY created_at DESC
        """)
        listings = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify({"status": "success", "listings": listings})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/market/listings", methods=["POST"])
def create_listing():
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        crop_type = str(data.get("crop_type", "")).lower().strip()
        quantity_kg = data.get("quantity_kg")
        asking_price_ghs = data.get("asking_price_ghs")
        harvest_date = data.get("harvest_date")

        if crop_type not in ["tomato", "maize", "pineapple"]:
            return jsonify({"status": "error", "message": "Invalid crop_type"}), 400
        if not quantity_kg or not asking_price_ghs or not harvest_date:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        farm_id = ensure_default_farm()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM Farms WHERE farm_id = ?", (farm_id,))
        row = cur.fetchone()
        farmer_id = row["user_id"] if row else 1

        cur.execute("""
            INSERT INTO MarketListings 
            (farmer_id, crop_type, quantity_kg, asking_price_ghs, harvest_date, listing_status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (farmer_id, crop_type, float(quantity_kg), float(asking_price_ghs), harvest_date))
        listing_id = cur.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "listing_id": listing_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/market/local-markets")
def get_local_markets():
    markets = [
        {"name": "Ho Central Market", "location": "Ho, Volta Region", "type": "General / Foodstuffs",
         "notes": "Main market in Ho. Good for tomato, maize, vegetables.", "maps": "https://maps.google.com/?q=Ho+Central+Market+Volta+Region"},
        {"name": "Ahoe Market", "location": "Ahoe, Ho", "type": "Foodstuffs",
         "notes": "Busy local market for smallholder sales.", "maps": "https://maps.google.com/?q=Ahoe+Market+Ho"},
        {"name": "Hohoe Market", "location": "Hohoe, Volta Region", "type": "General",
         "notes": "Important market in northern Volta.", "maps": "https://maps.google.com/?q=Hohoe+Market+Volta"},
        {"name": "Keta Market", "location": "Keta, Volta Region", "type": "Foodstuffs & Fish",
         "notes": "Coastal market for southern Volta farmers.", "maps": "https://maps.google.com/?q=Keta+Market+Volta+Region"},
        {"name": "Denu Market", "location": "Denu, Volta Region", "type": "Border / General",
         "notes": "Near Togo border. Active trading centre.", "maps": "https://maps.google.com/?q=Denu+Market+Volta"},
        {"name": "Makola Market (Accra)", "location": "Accra", "type": "Major wholesale / retail",
         "notes": "One of the largest markets in Ghana.", "maps": "https://maps.google.com/?q=Makola+Market+Accra"},
        {"name": "Kumasi Central Market (Kejetia)", "location": "Kumasi", "type": "Major market",
         "notes": "Key outlet for maize and staples.", "maps": "https://maps.google.com/?q=Kejetia+Market+Kumasi"},
    ]
    return jsonify({"status": "success", "markets": markets,
                    "note": "Confirm market days and transport costs before travelling."})


# -------------------------------------------------
# Resources Endpoints
# -------------------------------------------------
@app.route("/api/resources/news")
def get_news():
    import feedparser
    news_items = []
    feeds = ["https://www.modernghana.com/rss/", "https://www.ghanaweb.com/GhanaHomePage/business/rss.xml"]
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                keywords = ["agric", "farm", "crop", "food", "mofa", "maize", "tomato", "pineapple", "fertilizer", "pest"]
                if any(k in title.lower() for k in keywords) or len(news_items) < 3:
                    news_items.append({"title": title, "link": link, "source": "Ghana News", "published": entry.get("published", "")[:16]})
            if len(news_items) >= 8:
                break
        except Exception:
            continue
    if len(news_items) < 4:
        news_items = [
            {"title": "MoFA advances Feed Ghana programme to boost food security", "link": "https://www.modernghana.com", "source": "Modern Ghana", "published": "Recent"},
            {"title": "Agriculture remains backbone of Ghana’s economy – Minister", "link": "https://www.ghanaweb.com", "source": "GhanaWeb", "published": "Recent"},
            {"title": "Farmers advised to adopt smart and sustainable practices", "link": "https://www.modernghana.com", "source": "Modern Ghana", "published": "Recent"},
            {"title": "Youth in Agriculture programmes open for applications", "link": "https://mofa.gov.gh", "source": "MoFA", "published": "Recent"},
        ]
    return jsonify({"status": "success", "news": news_items[:10]})


@app.route("/api/resources/opportunities")
def get_opportunities():
    opportunities = [
        {"title": "Youth in Agriculture Programme", "description": "Support for young people to start or expand agribusinesses.", "link": "https://mofa.gov.gh"},
        {"title": "Planting for Food and Jobs related schemes", "description": "Input support and extension services for registered farmers.", "link": "https://mofa.gov.gh"},
        {"title": "Agricultural training – Volta Region", "description": "Contact your District Agricultural Extension Officer for training.", "link": ""},
        {"title": "SME / agribusiness funding windows", "description": "MASLOC, GEA and banks periodically open agribusiness support windows.", "link": ""},
    ]
    return jsonify({"status": "success", "opportunities": opportunities})


@app.route("/api/resources/pesticides")
def get_pesticide_education():
    education = [
        {"title": "General Safe Use Principles", "points": ["Always read the label before use", "Wear protective clothing", "Do not spray against the wind", "Keep pesticides locked away from children", "Wash hands and equipment after use", "Observe pre-harvest intervals"]},
        {"title": "Tomato – Common Issues", "points": ["Late blight: Copper-based or systemic fungicides", "Bacterial spot: Copper formulations + field hygiene", "Leaf curl virus: Whitefly control + resistant varieties"]},
        {"title": "Maize – Common Issues", "points": ["Fall armyworm: Early detection is critical", "Northern leaf blight & Gray leaf spot: Fungicides before tasseling when needed"]},
        {"title": "Pineapple – Common Issues", "points": ["Mealybug wilt: Control mealybugs and ants", "Heart rot: Improve drainage, avoid waterlogging"]},
    ]
    return jsonify({"status": "success", "education": education})


@app.route("/api/resources/shops")
def get_agro_shops():
    shops = [
        {"name": "Ho Agricultural Input Dealers", "location": "Ho, Volta Region", "contact": "Ask District Agric Office", "notes": "Seeds, fertilizers, pesticides", "maps": "https://maps.google.com/?q=Ho+Volta+Region+agro+chemical"},
        {"name": "Volta Region Agricultural Input Dealers", "location": "Ho Municipality & districts", "contact": "District Agricultural Development Unit", "notes": "Extension officers can recommend certified dealers", "maps": "https://maps.google.com/?q=Ho+Volta+Ghana"},
        {"name": "Local agro-chemical shops – Ho market area", "location": "Ho Central / Ahoe", "contact": "Visit in person", "notes": "Compare prices and check expiry dates", "maps": "https://maps.google.com/?q=Ho+market+Volta+Region"},
        {"name": "District Agricultural Extension Office", "location": "Ho and district capitals", "contact": "Ask for verified suppliers", "notes": "Best starting point for recommendations", "maps": ""},
    ]
    return jsonify({"status": "success", "shops": shops, "note": "Buy from certified dealers. Ask your extension officer for the latest list."})


# -------------------------------------------------
# Dashboard
# -------------------------------------------------
@app.route("/api/dashboard")
def dashboard():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM Scans")
        total_scans = cur.fetchone()["total"]
        cur.execute("SELECT COALESCE(SUM(disease_flags_raised), 0) AS total FROM Scans")
        total_diseases = cur.fetchone()["total"]
        cur.execute("SELECT COALESCE(SUM(total_plants_detected), 0) AS total FROM Scans")
        total_plants = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM MarketListings WHERE listing_status = 'active'")
        active_listings = cur.fetchone()["total"]
        cur.execute("SELECT scan_id, scan_date, total_plants_detected, disease_flags_raised FROM Scans ORDER BY scan_id DESC LIMIT 5")
        recent = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT diagnosed_condition, COUNT(*) AS count FROM DiseaseRecords GROUP BY diagnosed_condition ORDER BY count DESC LIMIT 5")
        disease_breakdown = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify({
            "status": "success",
            "summary": {
                "total_scans": total_scans,
                "total_plants_detected": total_plants,
                "total_disease_flags": total_diseases,
                "active_listings": active_listings
            },
            "recent_scans": recent,
            "disease_breakdown": disease_breakdown
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@app.route("/api/history")
def scan_history():
    """Return recent scan history (for farmers and admin)"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.scan_id, s.scan_date, s.total_plants_detected, 
                   s.disease_flags_raised, s.image_path,
                   COALESCE(s.crop_type, f.crop_type, 'unknown') AS crop_type,
                   f.farm_name
            FROM Scans s
            LEFT JOIN Farms f ON s.farm_id = f.farm_id
            ORDER BY s.scan_id DESC
            LIMIT 20
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"status": "success", "history": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("Starting AgroWatch server...")
    app.run(host="0.0.0.0", port=5000, debug=False)
