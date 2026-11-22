import sys, os, json, time, threading, urllib.parse, re
from pathlib import Path
from dataclasses import dataclass
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTabWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QSplitter, QScrollArea,
    QProgressBar, QAbstractItemView
)

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "Fish Macro"
APP_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DIR / "settings.json"
RODS_FILE = APP_DIR / "rods.json"
TEMPLATE_FILE = APP_DIR / "bite_template.png"
FISH_TEMPLATE_FILE = APP_DIR / "fish_marker_template.png"
CATALOG_URL = "https://bloxguidesgg.com/games/fisch/wiki/rods"
WIKI_API = "https://fischipedia.org/api.php"

DEFAULT_SETTINGS = {
    "hotkey": "f12", "cast_x": 0, "cast_y": 0, "bite_x": 0, "bite_y": 0,
    "region_x": 0, "region_y": 0, "region_w": 900, "region_h": 600,
    "scan_interval": 0.12, "bite_threshold": 0.82, "reel_click_ms": 120,
    "recast_delay": 1.4, "selected_rod": "Flimsy Rod", "auto_recast": True
}
SEED_RODS = [
    {"name":"Flimsy Rod","area":"Moosewood","luck":"0%","lure":"0%","control":"0","resilience":"0%","max_weight":"10.4 kg","obtainable":True},
    {"name":"Training Rod","area":"Moosewood","luck":"-70%","lure":"10%","control":"0.2","resilience":"20%","max_weight":"9 kg","obtainable":True},
    {"name":"Plastic Rod","area":"Moosewood","luck":"15%","lure":"20%","control":"0","resilience":"10%","max_weight":"100 kg","obtainable":True},
    {"name":"Carbon Rod","area":"Moosewood","luck":"25%","lure":"15%","control":"0.05","resilience":"10%","max_weight":"600 kg","obtainable":True},
    {"name":"Long Rod","area":"Moosewood","luck":"80%","lure":"20%","control":"-0.1","resilience":"20%","max_weight":"250 kg","obtainable":True},
    {"name":"Fast Rod","area":"Moosewood","luck":"10%","lure":"70%","control":"0.05","resilience":"-5%","max_weight":"175 kg","obtainable":True},
    {"name":"Lucky Rod","area":"Moosewood","luck":"177%","lure":"20%","control":"0.07","resilience":"7%","max_weight":"175 kg","obtainable":True},
    {"name":"Fortune Rod","area":"Roslit Bay","luck":"200%","lure":"30%","control":"0.05","resilience":"10%","max_weight":"3,000 kg","obtainable":True},
    {"name":"Trident Rod","area":"Desolate Deep","luck":"150%","lure":"35%","control":"0.05","resilience":"0%","max_weight":"6,000 kg","obtainable":True},
    {"name":"Destiny Rod","area":"The Arch","luck":"250%","lure":"45%","control":"0.2","resilience":"10%","max_weight":"177,777 kg","obtainable":True},
    {"name":"Rod Of The Depths","area":"The Depths","luck":"130%","lure":"75%","control":"0.15","resilience":"10%","max_weight":"30,000 kg","obtainable":True},
    {"name":"Fangsplitter","area":"Underground Music Venue","luck":"222%","lure":"222%","control":"0.22","resilience":"22%","max_weight":"∞","obtainable":True},
    {"name":"Hammyshork","area":"Ocean","luck":"170%","lure":"70%","control":"0.15","resilience":"15%","max_weight":"∞","obtainable":True}
]

def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

class CatalogWorker(QThread):
    finished_data = Signal(list, str)
    def run(self):
        try:
            import requests
            from bs4 import BeautifulSoup
            response = requests.get(CATALOG_URL, timeout=18, headers={"User-Agent":"FishMacro/1.0"})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            table = None
            for candidate in soup.find_all("table"):
                headers = " ".join(th.get_text(" ", strip=True).lower() for th in candidate.find_all("th"))
                if "luck" in headers and "lure" in headers and "rod" in headers:
                    table = candidate
                    break
            if table is None:
                raise RuntimeError("Rod table was not found on the catalog page.")
            rods = []
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td","th"])]
                if len(cells) < 10 or cells[1].lower() in ("rod","name"):
                    continue
                name = re.sub(r"\s+", " ", cells[0]).strip()
                if not name or name.lower() in ("own / compare", "rod"):
                    continue
                # The catalog table columns are name, location, luck, lure, control, resilience, max weight, stage, version, source, obtainable.
                if len(cells) >= 10:
                    rods.append({
                        "name":name, "area":cells[1], "luck":cells[2], "lure":cells[3],
                        "control":cells[4], "resilience":cells[5], "max_weight":cells[6],
                        "stage":cells[7], "version":cells[8], "source":cells[9],
                        "obtainable": (cells[10].lower() == "yes") if len(cells)>10 else None
                    })
            if not rods:
                raise RuntimeError("The rod catalog returned no usable entries.")
            unique = {}
            for rod in rods:
                unique[rod["name"].casefold()] = rod
            self.finished_data.emit(list(unique.values()), f"Loaded {len(unique)} rods from the catalog.")
        except Exception as exc:
            self.finished_data.emit([], f"Catalog update unavailable: {exc}")

class ImageWorker(QThread):
    loaded = Signal(str, str)
    def __init__(self, rod_name):
        super().__init__()
        self.rod_name = rod_name
    def run(self):
        try:
            import requests
            params = {
                "action":"query", "generator":"search", "gsrsearch":f'file:"{self.rod_name}"',
                "gsrnamespace":"6", "gsrlimit":"1", "prop":"imageinfo", "iiprop":"url",
                "iiurlwidth":"220", "format":"json"
            }
            data = requests.get(WIKI_API, params=params, timeout=12, headers={"User-Agent":"FishMacro/1.0"}).json()
            pages = data.get("query", {}).get("pages", {})
            url = ""
            if pages:
                page = next(iter(pages.values()))
                info = page.get("imageinfo", [])
                if info:
                    url = info[0].get("thumburl") or info[0].get("url", "")
            self.loaded.emit(self.rod_name, url)
        except Exception:
            self.loaded.emit(self.rod_name, "")

class FishingWorker(QThread):
    status = Signal(str)
    stopped = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.running = True

    def stop(self):
        self.running = False

    def _match(self, gray, template, cv2, threshold=None):
        th, tw = template.shape[:2]
        if gray.shape[0] < th or gray.shape[1] < tw:
            return None
        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)
        if score < (float(self.settings.get("bite_threshold", 0.78)) if threshold is None else threshold):
            return None
        return (location[0] + tw // 2, location[1] + th // 2, float(score))

    def _slider_center(self, frame, fish_y, cv2, np):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        _, mask = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        height, width = gray.shape
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            ratio = w / max(1, h)
            if 18 <= w <= width * 0.72 and 5 <= h <= min(55, height * 0.12) and ratio >= 2.8:
                center_y = y + h // 2
                if abs(center_y - fish_y) <= max(35, h * 2):
                    candidates.append((cv2.contourArea(contour), x + w // 2, w))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        _, center, bar_width = candidates[0]
        return center, bar_width

    def run(self):
        import pyautogui
        import cv2
        import numpy as np
        import mss

        mouse_held = False
        try:
            if not TEMPLATE_FILE.exists():
                self.status.emit("Capture the SHAKE prompt template first.")
                return
            if not FISH_TEMPLATE_FILE.exists():
                self.status.emit("Capture the moving fish marker template first.")
                return
            bite_template = cv2.imread(str(TEMPLATE_FILE), cv2.IMREAD_GRAYSCALE)
            fish_template = cv2.imread(str(FISH_TEMPLATE_FILE), cv2.IMREAD_GRAYSCALE)
            if bite_template is None or fish_template is None:
                self.status.emit("A visual template is invalid. Recapture both templates.")
                return

            region = {
                "left": int(self.settings["region_x"]),
                "top": int(self.settings["region_y"]),
                "width": max(1, int(self.settings["region_w"])),
                "height": max(1, int(self.settings["region_h"]))
            }
            if bite_template.shape[0] >= region["height"] or bite_template.shape[1] >= region["width"]:
                self.status.emit("The SHAKE template is too large. Recapture it using the crop selector.")
                return
            if fish_template.shape[0] >= region["height"] or fish_template.shape[1] >= region["width"]:
                self.status.emit("The fish marker template is too large. Recapture it using the crop selector.")
                return

            cast_x = int(self.settings["cast_x"])
            cast_y = int(self.settings["cast_y"])
            if cast_x <= 0 or cast_y <= 0:
                self.status.emit("Set the cast click position in Settings first.")
                return

            scan_delay = max(0.035, float(self.settings.get("scan_interval", 0.08)))
            threshold = float(self.settings.get("bite_threshold", 0.78))
            self.status.emit("Automation running: cast → detect SHAKE → track fish → steer reel bar.")
            with mss.mss() as sct:
                while self.running:
                    pyautogui.mouseUp()
                    mouse_held = False
                    pyautogui.moveTo(cast_x, cast_y)
                    pyautogui.mouseDown()
                    time.sleep(0.55)
                    pyautogui.mouseUp()
                    self.status.emit("Cast sent. Scanning for the moving SHAKE prompt…")

                    shake_time = time.monotonic()
                    reel_started = False
                    last_shake = 0.0
                    while self.running and time.monotonic() - shake_time < 90:
                        frame = np.array(sct.grab(region))
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                        fish_hit = self._match(gray, fish_template, cv2, 0.68)
                        if fish_hit:
                            reel_started = True
                            break
                        bite_hit = self._match(gray, bite_template, cv2)
                        if bite_hit and time.monotonic() - last_shake > 0.35:
                            bx = region["left"] + bite_hit[0]
                            by = region["top"] + bite_hit[1]
                            pyautogui.click(bx, by)
                            last_shake = time.monotonic()
                            self.status.emit(f"SHAKE prompt detected ({bite_hit[2]:.2f}); clicked.")
                        time.sleep(scan_delay)

                    if not self.running:
                        break
                    if not reel_started:
                        self.status.emit("No reel minigame detected this cast. Stopping safely.")
                        break

                    self.status.emit("Fish detected. Adaptive reel tracking active.")
                    previous_x = None
                    previous_t = time.monotonic()
                    filtered_velocity = 0.0
                    missing_since = None
                    last_report = 0.0
                    while self.running:
                        now = time.monotonic()
                        frame = np.array(sct.grab(region))
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                        fish_hit = self._match(gray, fish_template, cv2, 0.68)
                        if fish_hit is None:
                            if missing_since is None:
                                missing_since = now
                            if now - missing_since >= 1.8:
                                break
                            time.sleep(scan_delay)
                            continue

                        missing_since = None
                        fish_x, fish_y, score = fish_hit
                        slider = self._slider_center(frame, fish_y, cv2, np)
                        if slider is None:
                            if mouse_held:
                                pyautogui.mouseUp()
                                mouse_held = False
                            self.status.emit("Fish visible; locating the white reel slider…")
                            time.sleep(scan_delay)
                            continue

                        slider_x, slider_width = slider
                        dt = max(0.02, now - previous_t)
                        if previous_x is not None:
                            instant_velocity = (fish_x - previous_x) / dt
                            instant_velocity = max(-900.0, min(900.0, instant_velocity))
                            filtered_velocity = 0.65 * filtered_velocity + 0.35 * instant_velocity
                        previous_x = fish_x
                        previous_t = now

                        predicted_x = fish_x + max(-45.0, min(45.0, filtered_velocity * 0.13))
                        deadband = max(5.0, slider_width * 0.16)
                        error = predicted_x - slider_x
                        if error > deadband and not mouse_held:
                            pyautogui.mouseDown()
                            mouse_held = True
                        elif error < -deadband and mouse_held:
                            pyautogui.mouseUp()
                            mouse_held = False

                        if now - last_report > 0.6:
                            direction = "HOLD →" if mouse_held else "RELEASE ←"
                            self.status.emit(
                                f"Tracking fish ({score:.2f}) · {direction} · offset {int(error)} px"
                            )
                            last_report = now
                        time.sleep(scan_delay)

                    if mouse_held:
                        pyautogui.mouseUp()
                        mouse_held = False
                    if not self.running:
                        break
                    self.status.emit("Reel marker disappeared. Waiting for the catch screen…")
                    time.sleep(float(self.settings.get("recast_delay", 1.4)))
                    if not self.settings.get("auto_recast", True):
                        break

            self.status.emit("Automation stopped.")
        except Exception as exc:
            self.status.emit(f"Automation error: {exc}")
        finally:
            try:
                pyautogui.mouseUp()
            except Exception:
                pass
            self.stopped.emit()


class StatCard(QFrame):
    def __init__(self, label, value):
        super().__init__()
        self.setObjectName("statCard")
        lay = QVBoxLayout(self)
        small = QLabel(label.upper())
        small.setObjectName("muted")
        val = QLabel(str(value))
        val.setObjectName("statValue")
        lay.addWidget(small)
        lay.addWidget(val)

class MainWindow(QMainWindow):
    hotkey_signal = Signal()
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fish Macro")
        self.resize(1180, 760)
        self.setMinimumSize(940, 620)
        self.settings = read_json(SETTINGS_FILE, DEFAULT_SETTINGS.copy())
        self.rods = read_json(RODS_FILE, SEED_RODS.copy())
        self.worker = None
        self.catalog_worker = None
        self.image_worker = None
        self.current_image_name = ""
        self.hotkey_signal.connect(self.toggle_macro)
        self.build_ui()
        self.apply_style()
        self.refresh_rod_table()
        self.select_rod(self.settings.get("selected_rod", "Flimsy Rod"))
        self.refresh_status()
        self.register_hotkey()

    def build_ui(self):
        root = QWidget()
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(22,18,22,18)
        header = QHBoxLayout()
        title = QLabel("Fish Macro")
        title.setObjectName("appTitle")
        subtitle = QLabel("Windows desktop automation")
        subtitle.setObjectName("muted")
        title_stack = QVBoxLayout()
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()
        self.status_badge = QLabel("IDLE")
        self.status_badge.setObjectName("statusBadge")
        header.addWidget(self.status_badge)
        root_lay.addLayout(header)
        self.tabs = QTabWidget()
        root_lay.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.build_dashboard()
        self.build_rods()
        self.build_automation()
        self.build_settings()

    def build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.selected_rod_card = QFrame()
        self.selected_rod_card.setObjectName("panel")
        card = QHBoxLayout(self.selected_rod_card)
        self.rod_image = QLabel("No image")
        self.rod_image.setFixedSize(116,116)
        self.rod_image.setAlignment(Qt.AlignCenter)
        self.rod_image.setObjectName("rodImage")
        card.addWidget(self.rod_image)
        info = QVBoxLayout()
        self.dashboard_rod_name = QLabel("Flimsy Rod")
        self.dashboard_rod_name.setObjectName("sectionTitle")
        self.dashboard_rod_area = QLabel("Moosewood")
        self.dashboard_rod_area.setObjectName("muted")
        self.dashboard_rod_stats = QLabel("Select a rod from the Rods tab.")
        self.dashboard_rod_stats.setWordWrap(True)
        info.addWidget(self.dashboard_rod_name)
        info.addWidget(self.dashboard_rod_area)
        info.addWidget(self.dashboard_rod_stats)
        info.addStretch()
        card.addLayout(info, 1)
        top.addWidget(self.selected_rod_card, 3)
        quick = QFrame()
        quick.setObjectName("panel")
        ql = QVBoxLayout(quick)
        ql.addWidget(QLabel("AUTOMATION"))
        self.quick_state = QLabel("Stopped")
        self.quick_state.setObjectName("sectionTitle")
        self.quick_start = QPushButton("Start")
        self.quick_start.clicked.connect(self.toggle_macro)
        ql.addWidget(self.quick_state)
        ql.addWidget(self.quick_start)
        top.addWidget(quick, 1)
        layout.addLayout(top)
        stats = QGridLayout()
        self.card_lure = StatCard("Lure speed", "—")
        self.card_luck = StatCard("Luck", "—")
        self.card_control = StatCard("Control", "—")
        self.card_resilience = StatCard("Resilience", "—")
        for i, card in enumerate([self.card_lure,self.card_luck,self.card_control,self.card_resilience]):
            stats.addWidget(card,0,i)
        layout.addLayout(stats)
        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.addWidget(QLabel("ACTIVITY"))
        self.activity = QLabel("Ready. Configure a bite prompt template and screen coordinates in Settings.")
        self.activity.setObjectName("muted")
        self.activity.setWordWrap(True)
        pl.addWidget(self.activity)
        layout.addWidget(panel, 1)
        self.tabs.addTab(page, "Overview")

    def build_rods(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        self.rod_search = QLineEdit()
        self.rod_search.setPlaceholderText("Search rods, locations or acquisition method…")
        self.rod_search.textChanged.connect(self.filter_rods)
        self.obtainable_filter = QComboBox()
        self.obtainable_filter.addItems(["All rods","Obtainable","Limited / unavailable"])
        self.obtainable_filter.currentIndexChanged.connect(self.filter_rods)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name","Luck","Lure speed","Control","Resilience"])
        self.sort_combo.currentIndexChanged.connect(self.sort_rods)
        self.update_catalog_btn = QPushButton("Update catalog")
        self.update_catalog_btn.clicked.connect(self.update_catalog)
        bar.addWidget(self.rod_search, 1)
        bar.addWidget(self.obtainable_filter)
        bar.addWidget(self.sort_combo)
        bar.addWidget(self.update_catalog_btn)
        layout.addLayout(bar)
        split = QSplitter()
        self.rod_table = QTableWidget(0,7)
        self.rod_table.setHorizontalHeaderLabels(["Rod","Location","Luck","Lure","Control","Resilience","Max weight"])
        self.rod_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rod_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rod_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rod_table.verticalHeader().setVisible(False)
        self.rod_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for i in range(1,7):
            self.rod_table.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeToContents)
        self.rod_table.itemSelectionChanged.connect(self.rod_selected)
        split.addWidget(self.rod_table)
        detail = QFrame()
        detail.setObjectName("panel")
        detail.setMinimumWidth(250)
        dl = QVBoxLayout(detail)
        self.detail_image = QLabel("Rod image")
        self.detail_image.setObjectName("rodImage")
        self.detail_image.setAlignment(Qt.AlignCenter)
        self.detail_image.setMinimumHeight(190)
        self.detail_name = QLabel("Select a rod")
        self.detail_name.setObjectName("sectionTitle")
        self.detail_area = QLabel("")
        self.detail_area.setObjectName("muted")
        self.detail_stats = QLabel("")
        self.detail_stats.setWordWrap(True)
        self.detail_source = QLabel("")
        self.detail_source.setWordWrap(True)
        self.detail_source.setObjectName("muted")
        self.select_rod_btn = QPushButton("Use selected rod")
        self.select_rod_btn.clicked.connect(self.apply_selected_rod)
        dl.addWidget(self.detail_image)
        dl.addWidget(self.detail_name)
        dl.addWidget(self.detail_area)
        dl.addWidget(self.detail_stats)
        dl.addWidget(self.detail_source)
        dl.addStretch()
        dl.addWidget(self.select_rod_btn)
        split.addWidget(detail)
        split.setSizes([780,300])
        layout.addWidget(split,1)
        self.rod_count = QLabel(f"{len(self.rods)} rods")
        self.rod_count.setObjectName("muted")
        layout.addWidget(self.rod_count)
        self.tabs.addTab(page, "Rods")

    def build_automation(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel("Automation uses screen capture and simulated mouse input only. It does not read Roblox memory or inject into the game.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.auto_state = QLabel("Stopped")
        self.auto_state.setObjectName("sectionTitle")
        self.start_btn = QPushButton("Start automation")
        self.start_btn.clicked.connect(self.toggle_macro)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self.stop_macro)
        row.addWidget(self.auto_state)
        row.addStretch()
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        layout.addLayout(row)
        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.addWidget(QLabel("LIVE STATUS"))
        self.automation_log = QLabel("Idle")
        self.automation_log.setWordWrap(True)
        self.automation_log.setObjectName("muted")
        pl.addWidget(self.automation_log)
        layout.addWidget(panel,1)
        self.tabs.addTab(page, "Automation")

    def build_settings(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        outer = QVBoxLayout(inner)
        hot = QGroupBox("Hotkey")
        hf = QFormLayout(hot)
        self.hotkey_input = QLineEdit(self.settings["hotkey"])
        self.hotkey_input.setPlaceholderText("F12")
        hf.addRow("Start / stop key", self.hotkey_input)
        outer.addWidget(hot)
        coords = QGroupBox("Screen positions")
        cf = QFormLayout(coords)
        self.cast_x = self.spin(0,10000,self.settings["cast_x"])
        self.cast_y = self.spin(0,10000,self.settings["cast_y"])
        self.rx = self.spin(0,10000,self.settings["region_x"])
        self.ry = self.spin(0,10000,self.settings["region_y"])
        self.rw = self.spin(1,10000,self.settings["region_w"])
        self.rh = self.spin(1,10000,self.settings["region_h"])
        cf.addRow("Cast click X",self.cast_x); cf.addRow("Cast click Y",self.cast_y)
        cf.addRow("Bite scan region X",self.rx); cf.addRow("Bite scan region Y",self.ry)
        cf.addRow("Bite scan width",self.rw); cf.addRow("Bite scan height",self.rh)
        outer.addWidget(coords)
        timing = QGroupBox("Detection and timing")
        tf = QFormLayout(timing)
        self.scan_interval = QDoubleSpinBox(); self.scan_interval.setRange(0.05,2); self.scan_interval.setSingleStep(0.05); self.scan_interval.setValue(float(self.settings["scan_interval"]))
        self.threshold = QDoubleSpinBox(); self.threshold.setRange(0.5,0.99); self.threshold.setSingleStep(0.01); self.threshold.setValue(float(self.settings["bite_threshold"]))
        self.reel_ms = self.spin(50,2000,self.settings["reel_click_ms"])
        self.recast_delay = QDoubleSpinBox(); self.recast_delay.setRange(0.2,30); self.recast_delay.setSingleStep(0.2); self.recast_delay.setValue(float(self.settings["recast_delay"]))
        self.auto_recast = QCheckBox("Automatically cast again after a detected prompt"); self.auto_recast.setChecked(bool(self.settings["auto_recast"]))
        tf.addRow("Screen scan interval (s)",self.scan_interval)
        tf.addRow("Image match threshold",self.threshold)
        tf.addRow("Click duration (ms)",self.reel_ms)
        tf.addRow("Recast delay (s)",self.recast_delay)
        tf.addRow(self.auto_recast)
        outer.addWidget(timing)
        template = QGroupBox("Visual fishing markers")
        tl = QVBoxLayout(template)
        self.template_status = QLabel("SHAKE prompt: " + ("ready" if TEMPLATE_FILE.exists() else "not captured") + " · Fish marker: " + ("ready" if FISH_TEMPLATE_FILE.exists() else "not captured"))
        self.capture_template_btn = QPushButton("Capture SHAKE prompt")
        self.capture_template_btn.clicked.connect(lambda: self.capture_template("bite"))
        self.capture_fish_btn = QPushButton("Capture moving fish marker")
        self.capture_fish_btn.clicked.connect(lambda: self.capture_template("fish"))
        tl.addWidget(self.template_status)
        tl.addWidget(self.capture_template_btn)
        tl.addWidget(self.capture_fish_btn)
        outer.addWidget(template)
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_settings)
        outer.addWidget(save)
        outer.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.tabs.addTab(page, "Settings")

    def spin(self, minimum, maximum, value):
        widget = QSpinBox()
        widget.setRange(minimum,maximum)
        widget.setValue(int(value))
        return widget

    def apply_style(self):
        self.setStyleSheet("""
        QWidget { background:#101114; color:#e8e9ed; font-family:Segoe UI; font-size:13px; }
        QMainWindow { background:#101114; }
        #appTitle { font-size:25px; font-weight:700; color:#ffffff; }
        #muted { color:#9297a3; }
        #sectionTitle { font-size:19px; font-weight:650; color:#ffffff; }
        QTabWidget::pane { border:1px solid #292c33; border-radius:10px; top:-1px; }
        QTabBar::tab { background:#17191e; color:#9da2ad; padding:12px 20px; margin-right:5px; border-radius:8px; }
        QTabBar::tab:selected { background:#292d36; color:#ffffff; }
        QFrame#panel, QFrame#statCard { background:#181a20; border:1px solid #292c33; border-radius:12px; }
        QFrame#statCard { padding:8px; }
        QLabel#statValue { font-size:21px; font-weight:700; }
        QLabel#statusBadge { background:#252a30; color:#b8c1ca; padding:7px 13px; border-radius:10px; font-weight:700; }
        QLabel#rodImage { background:#20232a; border:1px solid #343944; border-radius:10px; color:#818794; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background:#1b1e24; border:1px solid #343944; border-radius:7px; padding:9px; min-height:18px; }
        QComboBox QAbstractItemView { background:#1b1e24; selection-background-color:#3c4658; }
        QPushButton { background:#d7e0ee; color:#14171c; border:0; border-radius:8px; padding:10px 15px; font-weight:650; }
        QPushButton:hover { background:#ffffff; }
        QPushButton#dangerButton { background:#5a3036; color:#ffe6e8; }
        QTableWidget { background:#15171c; alternate-background-color:#1a1d23; border:1px solid #292c33; border-radius:8px; gridline-color:#292c33; selection-background-color:#34445b; }
        QHeaderView::section { background:#20232a; color:#aeb4c0; padding:9px; border:0; }
        QGroupBox { border:1px solid #30343d; border-radius:9px; margin-top:12px; padding:12px; font-weight:650; }
        QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; }
        QScrollArea { border:0; }
        """)
        self.rod_table.setAlternatingRowColors(True)

    def refresh_rod_table(self):
        self.rod_table.setRowCount(len(self.rods))
        for row, rod in enumerate(self.rods):
            vals = [rod.get("name",""),rod.get("area",""),rod.get("luck","—"),rod.get("lure","—"),rod.get("control","—"),rod.get("resilience","—"),rod.get("max_weight","—")]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, rod.get("name",""))
                self.rod_table.setItem(row,col,item)
        self.filter_rods()

    def filter_rods(self):
        term = self.rod_search.text().casefold() if hasattr(self,"rod_search") else ""
        mode = self.obtainable_filter.currentIndex() if hasattr(self,"obtainable_filter") else 0
        visible = 0
        for row, rod in enumerate(self.rods):
            searchable = " ".join(str(v) for v in rod.values()).casefold()
            ok = term in searchable
            if mode == 1 and rod.get("obtainable") is False: ok = False
            if mode == 2 and rod.get("obtainable") is True: ok = False
            self.rod_table.setRowHidden(row,not ok)
            visible += int(ok)
        if hasattr(self,"rod_count"):
            self.rod_count.setText(f"Showing {visible} of {len(self.rods)} rods")

    def sort_rods(self):
        if not hasattr(self,"rod_table"): return
        col = self.sort_combo.currentIndex()
        key = ["name","luck","lure","control","resilience"][col]
        def number(v):
            m = re.search(r"-?[\d,.]+",str(v))
            return float(m.group(0).replace(",","")) if m else -1e30
        self.rods.sort(key=(lambda r:r.get(key,"").casefold()) if key=="name" else (lambda r:number(r.get(key,""))), reverse=(key!="name"))
        self.refresh_rod_table()

    def rod_selected(self):
        rows = self.rod_table.selectionModel().selectedRows()
        if not rows: return
        name = self.rod_table.item(rows[0].row(),0).text()
        self.select_rod(name)

    def select_rod(self,name):
        rod = next((r for r in self.rods if r.get("name")==name),None)
        if not rod: return
        self.current_rod = rod
        self.detail_name.setText(rod.get("name",""))
        self.detail_area.setText(rod.get("area",""))
        self.detail_stats.setText(
            f"Lure speed: {rod.get('lure','—')}\\nLuck: {rod.get('luck','—')}\\n"
            f"Control: {rod.get('control','—')}\\nResilience: {rod.get('resilience','—')}\\n"
            f"Max weight: {rod.get('max_weight','—')}"
        )
        self.detail_source.setText(rod.get("source",""))
        self.dashboard_rod_name.setText(rod.get("name",""))
        self.dashboard_rod_area.setText(rod.get("area",""))
        self.dashboard_rod_stats.setText(f"Lure {rod.get('lure','—')}  ·  Luck {rod.get('luck','—')}  ·  Control {rod.get('control','—')}  ·  Resilience {rod.get('resilience','—')}")
        self.card_lure.findChild(QLabel,"statValue").setText(rod.get("lure","—"))
        self.card_luck.findChild(QLabel,"statValue").setText(rod.get("luck","—"))
        self.card_control.findChild(QLabel,"statValue").setText(rod.get("control","—"))
        self.card_resilience.findChild(QLabel,"statValue").setText(rod.get("resilience","—"))
        self.load_rod_image(name)

    def load_rod_image(self,name):
        self.current_image_name = name
        self.detail_image.setPixmap(QPixmap())
        self.detail_image.setText("Loading image…")
        self.rod_image.setPixmap(QPixmap())
        self.rod_image.setText("Loading image…")
        self.image_worker = ImageWorker(name)
        self.image_worker.loaded.connect(self.image_loaded)
        self.image_worker.start()

    def image_loaded(self,name,url):
        if name != self.current_image_name: return
        if not url:
            self.detail_image.setText("Image unavailable")
            self.rod_image.setText("Image unavailable")
            return
        try:
            import requests
            from PySide6.QtGui import QImage
            data = requests.get(url,timeout=10).content
            pix = QPixmap()
            pix.loadFromData(data)
            if pix.isNull(): raise ValueError("Invalid image")
            self.detail_image.setPixmap(pix.scaled(220,190,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            self.rod_image.setPixmap(pix.scaled(116,116,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        except Exception:
            self.detail_image.setText("Image unavailable")
            self.rod_image.setText("Image unavailable")

    def apply_selected_rod(self):
        if not hasattr(self,"current_rod"): return
        self.settings["selected_rod"] = self.current_rod["name"]
        self.save_settings()
        self.activity.setText(f"Selected profile: {self.current_rod['name']}")
        self.tabs.setCurrentIndex(0)

    def update_catalog(self):
        self.update_catalog_btn.setEnabled(False)
        self.update_catalog_btn.setText("Updating…")
        self.catalog_worker = CatalogWorker()
        self.catalog_worker.finished_data.connect(self.catalog_updated)
        self.catalog_worker.start()

    def catalog_updated(self,rods,message):
        self.update_catalog_btn.setEnabled(True)
        self.update_catalog_btn.setText("Update catalog")
        if rods:
            self.rods = rods
            save_json(RODS_FILE,self.rods)
            self.refresh_rod_table()
            self.activity.setText(message)
        else:
            self.activity.setText(message)
            QMessageBox.information(self,"Catalog update",message)

    def capture_template(self, kind="bite"):
        try:
            import pyautogui
            import cv2
            import numpy as np
            x, y = self.rx.value(), self.ry.value()
            w, h = self.rw.value(), self.rh.value()
            if w < 40 or h < 40:
                raise ValueError("The scan region is too small.")
            label = "SHAKE prompt" if kind == "bite" else "moving fish marker"
            QMessageBox.information(
                self, "Capture " + label,
                "Put Fisch on the screen with the " + label + " clearly visible. "
                "After closing this message, switch to the game within 3 seconds. "
                "A crop selector will open; drag a tight box around only the " + label + "."
            )
            time.sleep(3)
            shot = pyautogui.screenshot(region=(x, y, w, h))
            frame = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
            roi = cv2.selectROI("Select " + label, frame, showCrosshair=True, fromCenter=False)
            cv2.destroyAllWindows()
            rx, ry, rw, rh = [int(v) for v in roi]
            if rw < 5 or rh < 5:
                return
            crop = cv2.cvtColor(frame[ry:ry+rh, rx:rx+rw], cv2.COLOR_BGR2GRAY)
            target = TEMPLATE_FILE if kind == "bite" else FISH_TEMPLATE_FILE
            if not cv2.imwrite(str(target), crop):
                raise ValueError("Could not save the selected marker.")
            self.template_status.setText(
                "SHAKE prompt: " + ("ready" if TEMPLATE_FILE.exists() else "not captured") +
                " · Fish marker: " + ("ready" if FISH_TEMPLATE_FILE.exists() else "not captured")
            )
            self.activity.setText(label.capitalize() + " template captured.")
        except Exception as exc:
            try:
                import cv2
                cv2.destroyAllWindows()
            except Exception:
                pass
            QMessageBox.warning(self, "Capture failed", str(exc))

    def save_settings(self):
        self.settings.update({
            "hotkey":self.hotkey_input.text().strip().lower() or "f12",
            "cast_x":self.cast_x.value(),"cast_y":self.cast_y.value(),
            "region_x":self.rx.value(),"region_y":self.ry.value(),"region_w":self.rw.value(),"region_h":self.rh.value(),
            "scan_interval":self.scan_interval.value(),"bite_threshold":self.threshold.value(),
            "reel_click_ms":self.reel_ms.value(),"recast_delay":self.recast_delay.value(),
            "auto_recast":self.auto_recast.isChecked()
        })
        save_json(SETTINGS_FILE,self.settings)
        self.register_hotkey()
        self.activity.setText("Settings saved.")
        QMessageBox.information(self,"Settings","Settings saved.")

    def register_hotkey(self):
        try:
            import keyboard
            if hasattr(self,"hotkey_handle") and self.hotkey_handle:
                keyboard.remove_hotkey(self.hotkey_handle)
            self.hotkey_handle = keyboard.add_hotkey(self.settings.get("hotkey","f12"),lambda: self.hotkey_signal.emit())
        except Exception as exc:
            self.activity.setText(f"Hotkey unavailable: {exc}")

    def toggle_macro(self):
        if self.worker and self.worker.isRunning():
            self.stop_macro()
        else:
            self.start_macro()

    def start_macro(self):
        self.save_settings_silent()
        self.worker = FishingWorker(self.settings.copy())
        self.worker.status.connect(self.set_macro_status)
        self.worker.stopped.connect(self.macro_stopped)
        self.worker.start()
        self.set_macro_status("Starting automation…")

    def stop_macro(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.set_macro_status("Stopping…")

    def macro_stopped(self):
        self.quick_start.setText("Start")
        self.quick_state.setText("Stopped")
        self.auto_state.setText("Stopped")
        self.status_badge.setText("IDLE")

    def set_macro_status(self,text):
        self.activity.setText(text)
        self.automation_log.setText(text)
        running = self.worker is not None and self.worker.isRunning()
        self.quick_state.setText("Running" if running else "Stopped")
        self.auto_state.setText("Running" if running else "Stopped")
        self.quick_start.setText("Stop" if running else "Start")
        self.start_btn.setText("Stop automation" if running else "Start automation")
        self.status_badge.setText("RUNNING" if running else "IDLE")

    def save_settings_silent(self):
        self.settings.update({
            "hotkey":self.hotkey_input.text().strip().lower() or "f12",
            "cast_x":self.cast_x.value(),"cast_y":self.cast_y.value(),
            "region_x":self.rx.value(),"region_y":self.ry.value(),"region_w":self.rw.value(),"region_h":self.rh.value(),
            "scan_interval":self.scan_interval.value(),"bite_threshold":self.threshold.value(),
            "reel_click_ms":self.reel_ms.value(),"recast_delay":self.recast_delay.value(),
            "auto_recast":self.auto_recast.isChecked()
        })
        save_json(SETTINGS_FILE,self.settings)

    def refresh_status(self):
        self.template_status.setText("SHAKE prompt: " + ("ready" if TEMPLATE_FILE.exists() else "not captured") + " · Fish marker: " + ("ready" if FISH_TEMPLATE_FILE.exists() else "not captured"))

    def closeEvent(self,event):
        self.stop_macro()
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Fish Macro")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
