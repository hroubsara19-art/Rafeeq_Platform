"""
attention_engine.py — نسخة محسّنة
═══════════════════════════════════════════════════════════════
تجمع بين:
  - منطق FocusBuddy: MediaPipe Pose لنسبة الأنف/الأذن الأفقية (0.65–1.35)
  - EAR فوري < 0.20 من Face Mesh (كالنموذج المرجعي)
  - Face Mesh احتياطي: نسبة أنف/أذن + نظر + نعاس متتابع
  - توقيت تحذير ~2 ث ثم تشتت ملحوظ ~4 ث (مناسب لإطارات الويب المنخفضة)
═══════════════════════════════════════════════════════════════
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import math
import random
import base64
import threading
from io import BytesIO
from dataclasses import dataclass, asdict
from typing import Optional
from PIL import Image


# ══════════════════════════════════════════════════════════════
# ثوابت
# ══════════════════════════════════════════════════════════════

# نسبة الأنف/الأذن — Face Mesh (احتياطي إذا لم يظهر الجسم في الإطار)
NOSE_EAR_RATIO_MIN  = 0.62   # أقل = التفات يمين (أوسع للويب)
NOSE_EAR_RATIO_MAX  = 1.38

# FocusBuddy: Pose أفقي (نطاق أوسع قليلاً للويب/كاميرا أمامية)
POSE_HEAD_RATIO_MIN = 0.62
POSE_HEAD_RATIO_MAX = 1.38

# EAR — نسبة انفتاح العين (ويب: JPEG منخفض + ~3 إطارات/ث → تنعيم مطلوب)
EAR_THRESHOLD       = 0.22   # للمسار التدريجي (مع عدّ الإطارات)
FOCUSBUDDY_EAR_THRESHOLD = 0.22  # عتبة صارمة سريعة
EAR_SOFT_THRESHOLD  = 0.30   # مع streak يُفعّل «وضع نعاس» للتنبيهات
EAR_CLOSED_STREAK   = 3      # إطارات متتالية منخفضة EAR → تفعيل وضع النعاس
EAR_OPEN_STREAK     = 3      # إطارات مفتوحة لتصفير وضع النعاس
EAR_CONSEC_FRAMES   = 12     # إطار متتالي تحت الحد → نعاس (مسار دقّة إضافي)

# Gaze — موقع البؤبؤ داخل العين
GAZE_LEFT_RATIO     = 0.33
GAZE_RIGHT_RATIO    = 0.67

# توقيت التنبيهات (ويب ~3 إطارات/ث → أقصر قليلاً من سطح المكتب حتى تصل الرسائل)
FOCUS_REQUIRED_SECONDS = 0.8
DISTRACTION_WARNING_SECONDS = 2.0
DISTRACTION_THRESHOLD_SECONDS = 4.0
DISTRACTION_SECONDS = DISTRACTION_THRESHOLD_SECONDS
ALERT_COOLDOWN = DISTRACTION_THRESHOLD_SECONDS

# لا يُصفّر مؤقت التشتت إلا بعد عدة إطارات «منتبه» متتالية (يمنع وميض الإطارات)
ATTENTIVE_RESET_STREAK = 5

# نقاط Face Mesh
LEFT_EYE   = [362, 385, 387, 263, 373, 380]
RIGHT_EYE  = [33,  160, 158, 133, 153, 144]
LEFT_IRIS  = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

# نقاط Face Mesh للأنف/الأذن (احتياطي)
NOSE_IDX      = 0
LEFT_EAR_IDX  = 234
RIGHT_EAR_IDX = 454


# ══════════════════════════════════════════════════════════════
# هيكل البيانات
# ══════════════════════════════════════════════════════════════

@dataclass
class AttentionState:
    timestamp:         float
    student_name:      str
    attention_score:   int        # 0–100
    is_attentive:      bool
    ear_value:         float
    is_drowsy:         bool
    nose_ear_ratio:    float      # من الكود القديم
    gaze_zone:         str        # center | left | right | unknown
    distraction_cause: str        # head_turn | drowsy | gaze | none
    alert_message:     Optional[str]
    session_minutes:   float
    inattention_count: int
    distraction_seconds: float
    is_warning_distraction: bool
    is_significant_distraction: bool
    focus_status: str
    distraction_level: str        # none | low | medium | high
    eye_closure_duration: float
    eye_closure_count: int
    should_force_stop: bool


# ══════════════════════════════════════════════════════════════
# دوال الحساب
# ══════════════════════════════════════════════════════════════

def _dist(p1, p2) -> float:
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)


def compute_ear(lm, indices: list, w: int, h: int) -> float:
    """Eye Aspect Ratio — كلما صغر كلما أغمض الطالب عينه."""
    pts = [(int(lm[i].x * w), int(lm[i].y * h)) for i in indices]
    A = _dist(pts[1], pts[5])
    B = _dist(pts[2], pts[4])
    C = _dist(pts[0], pts[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def compute_nose_ear_ratio(lm, w: int, h: int) -> float:
    """
    نسبة المسافة (أنف←أذن يسرى) / (أنف←أذن يمنى).
    مأخوذة من الكود القديم — تكشف الالتفات بشكل موثوق.
    قيمة طبيعية ≈ 1.0 ± 0.25
    """
    nose  = (lm[NOSE_IDX].x * w,      lm[NOSE_IDX].y * h)
    l_ear = (lm[LEFT_EAR_IDX].x * w,  lm[LEFT_EAR_IDX].y * h)
    r_ear = (lm[RIGHT_EAR_IDX].x * w, lm[RIGHT_EAR_IDX].y * h)

    left_dist  = _dist(nose, l_ear)
    right_dist = _dist(nose, r_ear)

    return left_dist / right_dist if right_dist > 0 else 1.0


def compute_pose_focusbuddy_ratio(pose_results) -> tuple[Optional[float], bool]:
    """
    نفس منطق FocusBuddy: |nose.x−left_ear.x| / |nose.x−right_ear.x| على Pose.
    يعيد (النسبة، هل_التشتت_بالوضعية).
    """
    if not pose_results or not pose_results.pose_landmarks:
        return None, False
    lm = pose_results.pose_landmarks.landmark
    nose, le, re = lm[0], lm[3], lm[4]
    left_dist = abs(nose.x - le.x)
    right_dist = abs(nose.x - re.x)
    if right_dist <= 1e-9:
        return None, False
    r = left_dist / right_dist
    bad = r < POSE_HEAD_RATIO_MIN or r > POSE_HEAD_RATIO_MAX
    return r, bad


def compute_gaze(lm, w: int, h: int) -> str:
    """يحسب اتجاه نظر العين من موقع البؤبؤ."""
    try:
        iris  = [(lm[i].x * w, lm[i].y * h) for i in LEFT_IRIS]
        eye   = [lm[i] for i in LEFT_EYE]
        cx    = np.mean([p[0] for p in iris])
        e_l   = lm[LEFT_EYE[0]].x * w
        e_r   = lm[LEFT_EYE[3]].x * w
        width = e_r - e_l
        if width <= 0:
            return "unknown"
        ratio = (cx - e_l) / width
        if ratio < GAZE_LEFT_RATIO:
            return "left"
        if ratio > GAZE_RIGHT_RATIO:
            return "right"
        return "center"
    except Exception:
        return "unknown"


def compute_score(ear: float, ratio: float, gaze: str, drowsy: bool) -> tuple[int, str]:
    """
    يحسب درجة الانتباه 0–100 وسبب التشتت.
    الأوزان: EAR 30% | Nose/Ear ratio 40% | Gaze 30%
    """
    score = 100
    cause = "none"

    # ── نعاس (30 نقطة) ────────────────────────────────────────
    if drowsy:
        score -= 30
        cause  = "drowsy"
    elif ear < EAR_THRESHOLD + 0.04:
        score -= 12

    # ── التفات الرأس (40 نقطة) — نسبة الأنف/الأذن ────────────
    if ratio < NOSE_EAR_RATIO_MIN or ratio > NOSE_EAR_RATIO_MAX:
        deviation = max(
            abs(ratio - NOSE_EAR_RATIO_MIN),
            abs(ratio - NOSE_EAR_RATIO_MAX)
        )
        penalty = min(40, int(deviation * 60))
        score  -= penalty
        if cause == "none":
            cause = "head_turn"

    # ── اتجاه النظر (30 نقطة) ────────────────────────────────
    if gaze in ("left", "right"):
        score -= 30
        if cause == "none":
            cause = "gaze"
    elif gaze == "unknown":
        score -= 10

    return max(0, min(100, score)), cause


def build_warning_nudge(name: str, cause: str) -> str:
    """تنبيه لطيف باسم الطالب عند أول بلوغ مرحلة التحذير (قبل احتساب التشتت الملحوظ)."""
    first = name.split()[0] if (name and name.strip()) else "صديقي"
    lines = {
        "drowsy": f"{first}، لاحظنا إنك قد تكون متعب — حاول تفتح عينيك وتتابع الدرس.",
        "head_turn": f"{first}، ثبّت رأسك أمام الشاشة شوي عشان تستفيد من الجلسة.",
        "gaze": f"{first}، رجّع نظرك لمحتوى الدرس اللي قدامك.",
        "no_face": f"{first}، ما ظهر وجهك للكاميرا — قدّم شوي أو عدّل الإضاءة.",
    }
    return lines.get(cause, f"{first}، ركّز معنا شوي على الدرس.")


def build_alert(name: str, cause: str, score: int) -> Optional[str]:
    """Arabic encouragement used after a counted distraction period."""
    if score >= 70:
        return None

    first = name.split()[0] if name else "صديقي"
    alerts = {
        "drowsy": [
            f"{first}، افتح عينيك قليلًا وخذ نفسًا عميقًا.",
            f"هيا {first}، لنرجع للدرس خطوة بخطوة.",
            f"{first}، استيقظ قليلًا، أنت قادر على الإنجاز.",
        ],
        "head_turn": [
            f"{first}، ثبّت نظرك على الشاشة قليلًا.",
            f"هيا {first}، الدرس هنا وينتظرك.",
            f"{first}، لحظة تركيز صغيرة تكفي.",
        ],
        "gaze": [
            f"{first}، الدرس على الشاشة أمامك.",
            f"{first}، أعد نظرك هنا بهدوء.",
            f"ركّز معنا {first}، الدرس مهم.",
        ],
        "no_face": [
            f"{first}، اقترب من الكاميرا قليلًا.",
            f"{first}، نحتاج أن يظهر وجهك حتى يستمر التتبع.",
        ],
    }
    return random.choice(alerts.get(cause, [f"{first}، نحتاج تركيزك قليلًا."]))


# ══════════════════════════════════════════════════════════════
# الكلاس الرئيسي
# ══════════════════════════════════════════════════════════════

class AttentionTracker:
    """
    الاستخدام:
        tracker = AttentionTracker(student_name="محمد خالد")
        tracker.start(callback=my_fn)   # my_fn(state_dict)
        tracker.stop()
    """

    # ✅ تم دمج __init__ بشكل صحيح في process_frame سابقاً — بدون تكرار

    def _track_distraction(self, attentive: bool, cause: str,
                           score: int, now: float) -> tuple[Optional[str], float, bool, bool]:
        """
        لا يُصفّر مؤقت التشتت عند إطار «منتبه» واحد؛ يحتاج عدة إطارات متتالية
        حتى لا يُلغى التحذير بسبب وميض النموذج أو ضغط JPEG.
        """
        if attentive:
            self._attentive_streak += 1
            if self._attentive_streak >= ATTENTIVE_RESET_STREAK:
                self._distract_start = None
                self._warning_nudge_sent = False
                self._attentive_streak = 0
                return None, 0.0, False, False
            # منتبه مؤقتاً لكن المؤلم لا يُصفّر بعد — لا تنبيهات حتى يثبت التركيز
            if self._distract_start is None:
                return None, 0.0, False, False
            distract_dur = now - self._distract_start
            return None, distract_dur, False, False

        self._attentive_streak = 0

        if self._distract_start is None:
            self._distract_start = now

        distract_dur = now - self._distract_start
        warning = distract_dur >= DISTRACTION_WARNING_SECONDS
        significant = distract_dur >= DISTRACTION_THRESHOLD_SECONDS

        alert = None
        if significant and now - self._last_alert >= ALERT_COOLDOWN:
            alert = build_alert(self.student_name, cause, score)
            if alert:
                self._last_alert = now
                self._inattention_count += 1
                self._distract_start = now
                self._warning_nudge_sent = False
        elif warning and not significant and not self._warning_nudge_sent:
            alert = build_warning_nudge(self.student_name, cause)
            self._warning_nudge_sent = True

        return alert, distract_dur, warning, significant

    def _process_focusbuddy(
        self,
        pose_results,
        face_lm,
        w: int,
        h: int,
    ) -> AttentionState:
        """
        دمج منطق FocusBuddy (Pose + EAR فوري) مع مسار دقّة إضافي عند الوجه المستقر.
        """
        now = time.time()
        ratio_pose, pose_distracted = compute_pose_focusbuddy_ratio(pose_results)

        ear = 0.35
        face_ratio = 1.0
        gaze_zone = "unknown"
        if face_lm is not None:
            ear_l = compute_ear(face_lm, LEFT_EYE, w, h)
            ear_r = compute_ear(face_lm, RIGHT_EYE, w, h)
            ear = (ear_l + ear_r) / 2.0
            face_ratio = compute_nose_ear_ratio(face_lm, w, h)
            gaze_zone = compute_gaze(face_lm, w, h)
            self._last_face_seen = time.time()  # ✅ تحديث وقت آخر مرة رأينا فيها الوجه

            if ear < EAR_SOFT_THRESHOLD:
                self._closed_ear_streak = min(self._closed_ear_streak + 1, 30)
                self._open_ear_streak = 0
            else:
                self._open_ear_streak = min(self._open_ear_streak + 1, 30)
                self._closed_ear_streak = max(0, self._closed_ear_streak - 1)

            if ear < FOCUSBUDDY_EAR_THRESHOLD or self._closed_ear_streak >= EAR_CLOSED_STREAK:
                self._drowse_active = True
                # ✅ نظام إغماض العينين
                if self._eye_closure_start is None:
                    self._eye_closure_start = time.time()
            if self._open_ear_streak >= EAR_OPEN_STREAK:
                self._drowse_active = False
                # ✅ إعادة تعيين عداد إغماض العينين عند فتح العينين
                if self._eye_closure_start is not None:
                    closure_duration = time.time() - self._eye_closure_start
                    if closure_duration >= self._eye_closure_threshold:
                        self._eye_closure_count += 1
                    self._eye_closure_start = None

            drowsy_instant = self._drowse_active
        else:
            self._closed_ear_streak = 0
            self._open_ear_streak = 0
            self._drowse_active = False
            drowsy_instant = False

        if pose_distracted:
            display_ratio = ratio_pose if ratio_pose is not None else face_ratio
            score = 25
            cause = "head_turn"
            attentive = False
            if ear < EAR_THRESHOLD:
                self._ear_counter += 1
            else:
                self._ear_counter = 0
            drowsy_long = self._ear_counter >= EAR_CONSEC_FRAMES
            drowsy = drowsy_long or drowsy_instant
        elif face_lm is not None and drowsy_instant:
            display_ratio = face_ratio
            score = 25
            cause = "drowsy"
            attentive = False
            self._ear_counter = min(self._ear_counter + 1, EAR_CONSEC_FRAMES + 5)
            drowsy = True
        elif face_lm is None:
            display_ratio = ratio_pose if ratio_pose is not None else 1.0
            # ✅ منطق احتفاظ: إذا اختفى الوجه لأقل من 2 ثانية، نعتبره منتبه
            if time.time() - self._last_face_seen < 2.0:
                score, cause, attentive = 78, "none", True
                self._ear_counter = 0
                drowsy = False
            elif ratio_pose is not None:
                score, cause, attentive = 78, "none", True
                self._ear_counter = 0
                drowsy = False
            else:
                score, cause, attentive = 0, "no_face", False
                self._ear_counter = 0
                drowsy = False
        else:
            if ear < EAR_THRESHOLD:
                self._ear_counter += 1
            else:
                self._ear_counter = 0
            drowsy_long = self._ear_counter >= EAR_CONSEC_FRAMES
            score, cause = compute_score(ear, face_ratio, gaze_zone, drowsy_long)
            attentive = score >= 68
            display_ratio = face_ratio
            drowsy = drowsy_long

        alert, distract_dur, warning, significant = self._track_distraction(
            attentive, cause, score, now
        )

        session_min = (now - self._session_start) / 60.0 if self._session_start else 0.0

        self._score_buffer.append(score)
        if len(self._score_buffer) > 500:
            self._score_buffer.pop(0)

        # تحديد مستوى التشتت بناءً على الثواني
        dist_level = "none"
        if not attentive:
            if distract_dur >= 7.0:
                dist_level = "high"
            elif distract_dur >= 3.0:
                dist_level = "medium"
            elif distract_dur >= 1.0:
                dist_level = "low"

        eye_dur = 0.0
        if self._eye_closure_start:
            eye_dur = now - self._eye_closure_start

        return AttentionState(
            timestamp=now,
            student_name=self.student_name,
            attention_score=score,
            is_attentive=attentive,
            ear_value=round(ear, 3),
            is_drowsy=drowsy,
            nose_ear_ratio=round(display_ratio, 3),
            gaze_zone=gaze_zone,
            distraction_cause=cause,
            alert_message=alert,
            session_minutes=round(session_min, 2),
            inattention_count=self._inattention_count,
            distraction_seconds=round(distract_dur, 1),
            is_warning_distraction=warning,
            is_significant_distraction=significant,
            focus_status="focused" if attentive else (
                "distracted" if significant else ("warning" if warning else "drifting")
            ),
            distraction_level=dist_level,
            eye_closure_duration=round(eye_dur, 1),
            eye_closure_count=self._eye_closure_count,
            should_force_stop=self._eye_closure_count >= self._max_eye_closures
        )

    def _process(self, lm, w: int, h: int) -> AttentionState:
        """مسار الكاميرا المحلية (بدون Pose) — نفس منطق الوجه فقط."""
        return self._process_focusbuddy(None, lm, w, h)

    def __init__(self, student_name: str = "الطالب",
                 camera_index: int = 0,
                 target_fps: int = 15):
        self.student_name  = student_name
        self.camera_index  = camera_index
        self.target_fps    = target_fps
        self._running      = False
        self.last_error    = None
        self._face_mesh    = None  # FaceMesh أو False عند التعطيل
        self._pose         = None  # Pose أو False
        self._face_detector = None

        # حالة داخلية
        self._ear_counter       = 0
        self._distract_start    = None   # وقت بداية التشتت
        self._last_alert        = 0.0
        self._warning_nudge_sent = False  # تنبيه تحذيري واحد لكل فترة تشتت قبل «الملحوظ»
        self._inattention_count = 0
        self._session_start     = None
        self._score_buffer      = []     # لحساب المتوسط
        self._attentive_streak  = 0      # إطارات منتبه متتالية لتصفير المؤقت
        self._closed_ear_streak = 0
        self._open_ear_streak   = 0
        self._drowse_active     = False
        self._mp_lock           = threading.Lock()  # ✅ حماية MediaPipe من multi-threading
        self._last_face_seen    = time.time()  # ✅ لتجنب وميض no_face
        # ✅ نظام إغماض العينين
        self._eye_closure_start = None  # وقت بداية إغماض العينين
        self._eye_closure_count = 0     # عدد مرات إغماض العينين
        self._eye_closure_threshold = 3.0  # 3 ثواني
        self._max_eye_closures = 3      # توقف بعد 3 مرات

    def _init_face_mesh(self):
        """✅ تهيئة face_mesh مرة واحدة فقط."""
        if self._face_mesh is False:
            return None

        if self._face_mesh is None:
            if not hasattr(mp, "solutions"):
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._face_detector = cv2.CascadeClassifier(cascade_path)
                self._face_mesh = False
                return None

            mp_mesh = mp.solutions.face_mesh
            self._face_mesh = mp_mesh.FaceMesh(
                max_num_faces        = 1,
                refine_landmarks     = True,
                min_detection_confidence = 0.45,  # ✅ تخفيف الحساسية للكاميرا المضغوطة
                min_tracking_confidence  = 0.45,  # ✅ تخفيف الحساسية للكاميرا المضغوطة
            )
            try:
                mp_pose = mp.solutions.pose
                self._pose = mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=1,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.6,
                )
            except Exception:
                self._pose = False
        return self._face_mesh

    def _process_basic_frame(self, rgb, w: int, h: int) -> Optional[dict]:
        """Fallback خفيف عندما لا تتوفر MediaPipe FaceMesh في البيئة الحالية."""
        if self._face_detector is None:
            return None

        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if len(rgb.shape) == 3 else rgb
        faces = self._face_detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )

        now = time.time()
        session_min = (now - self._session_start) / 60.0 if self._session_start else 0.0
        if len(faces) == 0:
            score = 0
            attentive = False
            cause = "no_face"
        else:
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            face_center = (x + fw / 2) / max(w, 1)
            centered = 0.25 <= face_center <= 0.75
            score = 90 if centered else 60
            attentive = score >= 70
            cause = "none" if attentive else "head_turn"

        alert, distract_dur, warning, significant = self._track_distraction(
            attentive, cause, score, now
        )

        self._score_buffer.append(score)
        if len(self._score_buffer) > 500:
            self._score_buffer.pop(0)

        return asdict(AttentionState(
            timestamp=now,
            student_name=self.student_name,
            attention_score=score,
            is_attentive=attentive,
            ear_value=0.0,
            is_drowsy=False,
            nose_ear_ratio=1.0,
            gaze_zone="unknown",
            distraction_cause=cause,
            alert_message=alert,
            session_minutes=round(session_min, 2),
            inattention_count=self._inattention_count,
            distraction_seconds=round(distract_dur, 1),
            is_warning_distraction=warning,
            is_significant_distraction=significant,
            focus_status="focused" if attentive else ("distracted" if significant else ("warning" if warning else "drifting")),
        ))

    def process_frame(self, frame_bytes) -> Optional[dict]:
        """✅ معالجة single frame من الـ WebSocket (Base64 أو bytes).
        
        Args:
            frame_bytes: صورة مشفرة Base64 أو numpy array
            
        Returns:
            asdict(AttentionState) أو None إذا فشلت المعالجة
        """
        try:
            if self._session_start is None:
                self._session_start = time.time()

            # تحويل Base64 إلى numpy array
            if isinstance(frame_bytes, str):
                # Base64 string
                img_data = base64.b64decode(frame_bytes)
                img = Image.open(BytesIO(img_data)).convert("RGB")
                frame = np.array(img)
            else:
                # numpy array مباشرة
                frame = np.array(frame_bytes)
            
            if frame is None or frame.size == 0:
                return None
            
            h, w = frame.shape[:2]
            if w == 0 or h == 0:
                return None
                
            # Browser Canvas/PIL frames arrive as RGB, which is what MediaPipe expects.
            if len(frame.shape) == 3 and frame.shape[2] >= 3:
                rgb = frame[:, :, :3]
                if rgb.dtype != np.uint8:
                    rgb = rgb.astype(np.uint8)
            else:
                rgb = frame

            # تهيئة Face Mesh + Pose (منطق FocusBuddy المرجعي)
            face_mesh = self._init_face_mesh()
            if face_mesh is None:
                return self._process_basic_frame(rgb, w, h)

            # ✅ حماية MediaPipe من multi-threading
            with self._mp_lock:
                pose_results = None
                if self._pose is not None and self._pose is not False:
                    try:
                        pose_results = self._pose.process(rgb)
                    except Exception:
                        pose_results = None

                face_results = face_mesh.process(rgb)
                face_lm = None
                if face_results.multi_face_landmarks:
                    face_lm = face_results.multi_face_landmarks[0].landmark

            state = self._process_focusbuddy(pose_results, face_lm, w, h)
            return asdict(state)
        
        except Exception as e:
            self.last_error = str(e)
            return None

    def start(self, callback=None, max_seconds: int = 0):
        """⚠️ هذه النسخة لا تُستخدم في بيئة الويب — تُترك للتوافقية مع النسخ القديمة."""
        mp_mesh  = mp.solutions.face_mesh
        face_mesh = mp_mesh.FaceMesh(
            max_num_faces        = 1,
            refine_landmarks     = True,
            min_detection_confidence = 0.6,
            min_tracking_confidence  = 0.5,
        )

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"لا يمكن فتح الكاميرا {self.camera_index}")

        self._running       = True
        self._session_start = time.time()
        delay = 1.0 / self.target_fps

        try:
            while self._running:
                t0 = time.time()
                ret, frame = cap.read()
                if not ret:
                    continue

                h, w = frame.shape[:2]
                rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res  = face_mesh.process(rgb)

                if res.multi_face_landmarks:
                    lm    = res.multi_face_landmarks[0].landmark
                    state = self._process(lm, w, h)
                    if callback:
                        callback(asdict(state))

                if max_seconds and (time.time() - self._session_start) >= max_seconds:
                    break

                sleep_t = delay - (time.time() - t0)
                if sleep_t > 0:
                    time.sleep(sleep_t)
        finally:
            cap.release()
            face_mesh.close()
            self._running = False

    def stop(self):
        self._running = False
        # ✅ إغلاق MediaPipe لتجنب تسرب الموارد
        with self._mp_lock:
            if self._face_mesh and self._face_mesh is not False:
                try:
                    self._face_mesh.close()
                except Exception:
                    pass
                self._face_mesh = None
            if self._pose and self._pose is not False:
                try:
                    self._pose.close()
                except Exception:
                    pass
                self._pose = None

    def get_summary(self) -> dict:
        buf = self._score_buffer
        dur = (time.time() - self._session_start) / 60.0 if self._session_start else 0
        return {
            "student_name":      self.student_name,
            "session_minutes":   round(dur, 2),
            "inattention_count": self._inattention_count,
            "avg_attention":     round(sum(buf)/len(buf), 1) if buf else 0,
        }
