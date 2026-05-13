"""
flask_server.py
═══════════════════════════════════════════════════════════════
خادم Flask مستقل يشغّل خوارزمية الانتباه ويبثّ النتائج
عبر WebSocket و REST API لتطبيق Django.

المنافذ:
    Flask  : http://localhost:5050
    WS     : ws://localhost:5050/ws/attention/<session_id>

نقاط الـ API:
    POST /api/start   → يبدأ جلسة تتبع
    POST /api/stop    → يوقف الجلسة
    GET  /api/summary → ملخص الجلسة
    GET  /api/status  → حالة الخادم
═══════════════════════════════════════════════════════════════
"""

import json
import threading
import time
import logging
import numpy as np
import base64
from io import BytesIO
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock
from attention_engine import AttentionTracker
try:
    from PIL import Image
    import cv2
except ImportError as e:
    logger_init = logging.getLogger(__name__)
    logger_init.warning(f"تنبيه استيراد: {e}")

# تهيئة logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app  = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]}})
sock = Sock(app)

# ── مخزن الجلسات النشطة ─────────────────────────────────────
_sessions: dict[str, dict] = {}
_lock = threading.Lock()


def _make_session(session_id: str, student_name: str,
                  camera_index: int = 0) -> dict:
    tracker     = AttentionTracker(student_name=student_name,
                                   camera_index=camera_index)
    ws_clients  = []      # قائمة WebSocket المتصلة بهذه الجلسة
    state_buffer = []     # آخر 300 حالة لحساب المتوسط
    frame_client = None   # client الذي يرسل frames

    return {
        "tracker":       tracker,
        "ws_clients":    ws_clients,
        "frame_client":  frame_client,
        "state_buffer":  state_buffer,
        "thread":        None,
        "running":       False,
    }


def _tracker_callback(session_id: str):
    """دالة تُمرَّر للـ tracker — تبثّ الحالة لكل WebSocket متصل."""
    def _cb(state_dict: dict):
        with _lock:
            session = _sessions.get(session_id)
            if not session:
                return
            session["state_buffer"].append(state_dict["attention_score"])
            if len(session["state_buffer"]) > 300:
                session["state_buffer"].pop(0)
            clients = list(session["ws_clients"])

        payload = json.dumps(state_dict, ensure_ascii=False)
        dead = []
        for ws in clients:
            try:
                ws.send(payload)
            except Exception:
                dead.append(ws)

        if dead:
            with _lock:
                for ws in dead:
                    if ws in session["ws_clients"]:
                        session["ws_clients"].remove(ws)

    return _cb


# ══════════════════════════════════════════════════════════════
# REST API
# ══════════════════════════════════════════════════════════════

@app.route("/api/status", methods=["GET"])
def api_status():
    active = [sid for sid, s in _sessions.items() if s["running"]]
    return jsonify({"status": "ok", "active_sessions": active})


@app.route("/api/start", methods=["POST"])
def api_start():
    """
    Body JSON:
        {
            "session_id":   "lesson_42_student_7",
            "student_name": "محمد خالد",
            "camera_index": 0
        }
    """
    data         = request.get_json(force=True)
    session_id   = data.get("session_id",   "default")
    student_name = data.get("student_name", "الطالب")
    camera_index = int(data.get("camera_index", 0))

    # قفل واحد من الفحص حتى اكتمال التهيئة يمنع طلبين متزامنين لنفس session_id
    # من تجاوز الفحص واستبدال الجلسة الأولى بجلسة يتيمة.
    with _lock:
        if session_id in _sessions and _sessions[session_id]["running"]:
            return jsonify({"error": "الجلسة نشطة بالفعل"}), 400

        session = _make_session(session_id, student_name, camera_index)
        _sessions[session_id] = session

        # تهيئة tracker بدون فتح كاميرا الخادم؛ frames تصل من المتصفح عبر WebSocket.
        session["running"] = True
        try:
            session["tracker"]._running = True
            session["tracker"]._session_start = time.time()
            session["tracker"]._init_face_mesh()
        except Exception as e:
            logger.error(f"خطأ في تهيئة tracker: {e}")
            session["running"] = False
            _sessions.pop(session_id, None)
            return jsonify({"error": "تعذّر تهيئة تتبع الانتباه"}), 500

    return jsonify({
        "ok":        True,
        "session_id": session_id,
        "ws_url":    f"ws://localhost:5050/ws/attention/{session_id}",
    })


@app.route("/api/stop", methods=["POST"])
def api_stop():
    data       = request.get_json(force=True)
    session_id = data.get("session_id", "default")

    with _lock:
        session = _sessions.get(session_id)
        if not session:
            return jsonify({"error": "جلسة غير موجودة"}), 404
        # حلقة WebSocket تفحص session["running"]؛ بدون هذا تبقى حتى انتهاء مهلة receive.
        session["running"] = False

    session["tracker"].stop()

    # انتظر توقف الـ thread
    if session["thread"]:
        session["thread"].join(timeout=3)

    summary = session["tracker"].get_summary()
    buf     = session["state_buffer"]
    summary["avg_attention"] = round(sum(buf) / len(buf), 1) if buf else 0

    with _lock:
        del _sessions[session_id]

    return jsonify({"ok": True, "summary": summary})


@app.route("/api/summary/<session_id>", methods=["GET"])
def api_summary(session_id):
    with _lock:
        session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "جلسة غير موجودة"}), 404

    buf     = session["state_buffer"]
    summary = session["tracker"].get_summary()
    summary["avg_attention"] = round(sum(buf) / len(buf), 1) if buf else 0
    summary["running"]       = session["running"]
    return jsonify(summary)


# ══════════════════════════════════════════════════════════════
# WebSocket
# ══════════════════════════════════════════════════════════════

@sock.route("/ws/attention/<session_id>")
def ws_attention(ws, session_id):
    """
    ✅ الـ Frontend يتصل هنا ويرسل frames من الكاميرا عبر WebSocket.
    يتوقع messages بصيغة JSON:
        {
            "type": "frame",
            "data": "base64_encoded_image..."
        }
    """
    with _lock:
        session = _sessions.get(session_id)

    if not session:
        try:
            ws.send(json.dumps({"error": "جلسة غير موجودة"}))
        except:
            pass
        return

    with _lock:
        session["ws_clients"].append(ws)
        session["frame_client"] = ws  # هذا الـ client يرسل frames

    try:
        while session.get("running", False):
            try:
                msg = ws.receive(timeout=5)
                if not msg:
                    continue
                
                # معالجة ping/pong
                if msg == "ping":
                    ws.send(json.dumps({"pong": True}))
                    continue
                
                # معالجة frame data
                try:
                    data = json.loads(msg)
                except:
                    continue
                
                if not isinstance(data, dict) or data.get("type") != "frame":
                    continue
                
                frame_b64 = data.get("data")
                if not frame_b64:
                    continue
                
                # ✅ معالجة الـ frame
                try:
                    # تحويل Base64 إلى صورة
                    img_data = base64.b64decode(frame_b64)
                    img = Image.open(BytesIO(img_data))
                    frame = np.array(img)
                    
                    # معالجة عبر الـ tracker
                    tracker = session["tracker"]
                    state_dict = tracker.process_frame(frame)
                    
                    if state_dict:
                        with _lock:
                            session["state_buffer"].append(state_dict.get("attention_score", 0))
                            if len(session["state_buffer"]) > 300:
                                session["state_buffer"].pop(0)
                            clients = list(session["ws_clients"])
                        
                        payload = json.dumps(state_dict, ensure_ascii=False)
                        dead = []
                        for client in clients:
                            try:
                                client.send(payload)
                            except Exception:
                                dead.append(client)
                        
                        if dead:
                            with _lock:
                                for client in dead:
                                    if client in session.get("ws_clients", []):
                                        session["ws_clients"].remove(client)
                
                except Exception as e:
                    logger.error(f"خطأ معالجة frame: {e}")
                    continue
            
            except Exception as e:
                if "timeout" not in str(e).lower():
                    logger.error(f"خطأ استقبال: {e}")
                break
    
    finally:
        with _lock:
            if ws in session.get("ws_clients", []):
                session["ws_clients"].remove(ws)
            if session.get("frame_client") is ws:
                session["frame_client"] = None


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🚀 خادم تتبع الانتباه يعمل على http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
