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
CATALOG_URL = "https://fisch.wiki/wiki/fishing-rods/"
WIKI_API = "https://fisch.wiki/api.php"

DEFAULT_SETTINGS = {
    "hotkey": "f12", "cast_x": 0, "cast_y": 0, "bite_x": 0, "bite_y": 0,
    "region_x": 0, "region_y": 0, "region_w": 900, "region_h": 600,
    "scan_interval": 0.04, "cast_hold": 0.95,
    "recast_delay": 1.4, "selected_rod": "Flimsy Rod", "auto_recast": True,
    "auto_totem": False, "totem_name": "Sundial Totem", "totem_key": "3", "rod_key": "1", "totem_interval": 300
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
            rods = {}
            response = requests.get("https://oofwiki.com/fisch/rods", timeout=25, headers={"User-Agent":"FishMacro/3.0"})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            aliases = {
                "rod":"name","name":"name","rod name":"name","price":"price",
                "lure speed":"lure","lure speed (%)":"lure","luck":"luck","luck (%)":"luck",
                "control":"control","resilience":"resilience","resilience (%)":"resilience",
                "max weight":"max_weight","max kg":"max_weight","where to get it":"area",
                "location":"area","area":"area","obtainable":"obtainable","ability":"ability","passive":"ability"
            }
            for table in soup.find_all("table"):
                trs=table.find_all("tr")
                header=None
                hi=-1
                for idx,tr in enumerate(trs[:5]):
                    cells=[re.sub(r"\\s+"," ",c.get_text(" ",strip=True)).strip() for c in tr.find_all(["th","td"])]
                    norm=[re.sub(r"\\s+"," ",x.casefold()).strip(" :") for x in cells]
                    if any(x in ("rod","name","rod name") for x in norm) and any("luck" in x for x in norm):
                        header,hi=norm,idx
                        break
                if header is None:
                    continue
                keys=[aliases.get(x,next((v for k,v in aliases.items() if k in x),None)) for x in header]
                ni=next((i for i,k in enumerate(keys) if k=="name"),None)
                if ni is None:
                    continue
                for tr in trs[hi+1:]:
                    cells=[re.sub(r"\\s+"," ",c.get_text(" ",strip=True)).strip() for c in tr.find_all(["th","td"])]
                    if len(cells)<=ni or not cells[ni]:
                        continue
                    name=cells[ni]
                    item=rods.setdefault(name.casefold(),{"name":name,"source":"OofWiki"})
                    for i,key in enumerate(keys):
                        if key and i<len(cells) and cells[i]:
                            value=cells[i]
                            item[key]=value.casefold() in ("yes","true","obtainable") if key=="obtainable" else value
            try:
                data_url="https://raw.githubusercontent.com/VinnyInnit/fisch-macro/main/macro/fisch_data.json"
                data_response=requests.get(data_url,timeout=18,headers={"User-Agent":"FishMacro/3.0"})
                data_response.raise_for_status()
                for name,values in data_response.json().get("rods",{}).items():
                    if not isinstance(values,list) or len(values)<4:
                        continue
                    item=rods.setdefault(name.casefold(),{"name":name,"source":"Fisch Wiki data index"})
                    item.setdefault("control",str(values[0]))
                    item.setdefault("resilience",str(values[1])+"%")
                    item.setdefault("lure",str(values[3])+"%")
                    if values[2]:
                        item["minigame"]=str(values[2])
                    if item.get("source")=="OofWiki":
                        item["source"]="OofWiki + Fisch Wiki index"
            except Exception:
                pass
            rods.setdefault("seraphic rod",{
                "name":"Seraphic Rod","price":"No Price","lure":"0%","luck":"+225%",
                "control":"0.25","resilience":"+20%","max_weight":"Unlimited",
                "area":"Level 1,000","ability":"Blessed (35%, 8.5×); Heavenly (10%, 6×)",
                "source":"Rowikis"
            })
            result=sorted(rods.values(),key=lambda r:r.get("name","").casefold())
            if len(result)<100:
                raise RuntimeError(f"Only {len(result)} rods found; incomplete data was not saved.")
            self.finished_data.emit(result,f"Loaded {len(result)} rods from multiple public catalogs.")
        except Exception as exc:
            self.finished_data.emit([],f"Rod catalog update unavailable: {exc}")

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
    def __init__(self,settings):
        super().__init__()
        self.settings=settings
        self.running=True
    def stop(self):
        self.running=False
    def _game_focused(self,pyautogui):
        try:
            return "roblox" in (pyautogui.getActiveWindowTitle() or "").casefold()
        except Exception:
            return True
    def _runs(self,mask):
        out=[]
        start=None
        for i,v in enumerate(mask):
            if v and start is None:
                start=i
            elif not v and start is not None:
                out.append((start,i-1));start=None
        if start is not None:
            out.append((start,len(mask)-1))
        return out
    def _detect_reel(self,frame,np):
        rgb=frame[:,:,:3][:,:,::-1].astype(np.int16)
        h,w=rgb.shape[:2]
        if h<300 or w<500:return None
        track=np.array([25,25,30],dtype=np.int16)
        bar=np.array([239,238,239],dtype=np.int16)
        fish=np.array([66,74,90],dtype=np.int16)
        x1,x2=int(w*.10),int(w*.90)
        y1,y2=int(h*.52),int(h*.91)
        dark=np.max(np.abs(rgb[y1:y2,x1:x2]-track),axis=2)<=42
        best=None
        for ri,row in enumerate(dark):
            runs=self._runs(row)
            if not runs:continue
            l,r=max(runs,key=lambda p:p[1]-p[0])
            length=r-l+1
            if length<w*.20:continue
            score=length-abs((y1+ri)-h*.76)*1.8
            if best is None or score>best[0]:best=(score,l,r,y1+ri)
        if best is None:return None
        _,ll,rr,ty=best
        left,right=x1+ll,x1+rr
        tw=right-left+1
        band=rgb[max(0,ty-4):min(h,ty+5),left:right+1]
        bm=np.max(np.abs(band-bar),axis=2)<=58
        fm=np.max(np.abs(band-fish),axis=2)<=42
        br=[p for p in self._runs(np.any(bm,axis=0)) if 5<=p[1]-p[0]+1<=tw*.55]
        fr=[p for p in self._runs(np.any(fm,axis=0)) if 1<=p[1]-p[0]+1<=10]
        if not br or not fr:return None
        bl,be=max(br,key=lambda p:p[1]-p[0])
        fl,fe=max(fr,key=lambda p:(1 if p[1]-p[0]<=4 else .3)*(1-abs((p[0]+p[1])/2-tw/2)/max(1,tw)))
        return {"bar_center":left+(bl+be)/2,"bar_width":be-bl+1,"fish_x":left+(fl+fe)/2}
    def run(self):
        import pyautogui,numpy as np,mss
        held=False
        try:
            cx,cy=int(self.settings.get("cast_x",0)),int(self.settings.get("cast_y",0))
            if cx<=0 or cy<=0:
                self.status.emit("Set one fixed cast point. No movement recording or playback is used.")
                return
            delay=max(.025,float(self.settings.get("scan_interval",.04)))
            cast_hold=max(.25,float(self.settings.get("cast_hold",.95)))
            self.status.emit("Live screen detection ready. Keep Roblox in the foreground.")
            with mss.mss() as sct:
                monitor=sct.monitors[1]
                while self.running:
                    while self.running and not self._game_focused(pyautogui):
                        self.status.emit("Waiting for Roblox focus. Use F12 while the game is active.")
                        time.sleep(.25)
                    if not self.running:break
                    pyautogui.moveTo(cx,cy);pyautogui.mouseDown();time.sleep(cast_hold);pyautogui.mouseUp()
                    self.status.emit("Cast sent. Waiting for the reel UI…")
                    started=time.monotonic();reel=None
                    while self.running and time.monotonic()-started<100:
                        if not self._game_focused(pyautogui):
                            time.sleep(.2);continue
                        reel=self._detect_reel(np.array(sct.grab(monitor)),np)
                        if reel:break
                        time.sleep(delay)
                    if not self.running:break
                    if reel is None:
                        self.status.emit("Reel UI not found. Check display scale and cast point.");time.sleep(1);continue
                    self.status.emit("Reel detected. Tracking live fish and bar.")
                    px,pt=None,time.monotonic()
                    velocity=accel=0.0
                    missing=None
                    report=0.0
                    while self.running:
                        if not self._game_focused(pyautogui):
                            if held:pyautogui.mouseUp();held=False
                            self.status.emit("Paused until Roblox is focused.")
                            time.sleep(.2);continue
                        now=time.monotonic()
                        reel=self._detect_reel(np.array(sct.grab(monitor)),np)
                        if reel is None:
                            if missing is None:missing=now
                            if now-missing>.9:break
                            time.sleep(delay);continue
                        missing=None
                        fx,bc=reel["fish_x"],reel["bar_center"]
                        half=max(3.0,reel["bar_width"]*.5)
                        margin=max(3.0,min(12.0,reel["bar_width"]*.12))
                        left,right=bc-half+margin,bc+half-margin
                        dt=max(.02,min(.2,now-pt))
                        if px is not None:
                            v=max(-1800.0,min(1800.0,(fx-px)/dt))
                            av=(v-velocity)/dt
                            accel=.7*accel+.3*max(-6500.0,min(6500.0,av))
                            velocity=.55*velocity+.45*v
                        px,pt=fx,now
                        lead=.075 if abs(accel)<1800 else .04
                        predicted=fx+velocity*lead+.5*accel*lead*lead
                        if predicted>right and not held:pyautogui.mouseDown();held=True
                        elif predicted<left and held:pyautogui.mouseUp();held=False
                        if now-report>.6:
                            self.status.emit(f"Fish {int(fx)} · Bar {reel['bar_width']}px · {'HOLD' if held else 'RELEASE'}")
                            report=now
                        time.sleep(delay)
                    if held:pyautogui.mouseUp();held=False
                    if not self.running:break
                    self.status.emit("Catch cycle ended. Recasting…")
                    time.sleep(float(self.settings.get("recast_delay",1.4)))
                    if not self.settings.get("auto_recast",True):break
            self.status.emit("Automation stopped.")
        except Exception as exc:
            self.status.emit(f"Automation error: {exc}")
        finally:
            try:pyautogui.mouseUp()
            except Exception:pass
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
        self.macro_active = False
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
        self.rod_table = QTableWidget(0,10)
        self.rod_table.setHorizontalHeaderLabels(["Rod","Location","Luck","Lure","Control","Resilience","Max weight","Price","Ability","Source"])
        self.rod_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rod_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rod_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rod_table.verticalHeader().setVisible(False)
        self.rod_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for i in range(1,10):
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
        self.scan_interval = QDoubleSpinBox(); self.scan_interval.setRange(0.035,2); self.scan_interval.setSingleStep(0.01); self.scan_interval.setValue(float(self.settings["scan_interval"]))
        self.cast_hold_input = QDoubleSpinBox(); self.cast_hold_input.setRange(0.25,3.0); self.cast_hold_input.setSingleStep(0.05); self.cast_hold_input.setValue(float(self.settings.get("cast_hold",0.95)))
        self.recast_delay = QDoubleSpinBox(); self.recast_delay.setRange(0.2,30); self.recast_delay.setSingleStep(0.2); self.recast_delay.setValue(float(self.settings["recast_delay"]))
        self.auto_recast = QCheckBox("Automatically cast again after a detected prompt"); self.auto_recast.setChecked(bool(self.settings["auto_recast"]))
        tf.addRow("Screen scan interval (s)",self.scan_interval)
        tf.addRow("Cast hold duration (s)",self.cast_hold_input)
        tf.addRow("Recast delay (s)",self.recast_delay)
        tf.addRow(self.auto_recast)
        outer.addWidget(timing)
        detection = QGroupBox("Automatic detection")
        detection_layout = QVBoxLayout(detection)
        self.template_status = QLabel("Live screen detection. No templates or recorded movement required.")
        self.template_status.setObjectName("muted")
        self.template_status.setWordWrap(True)
        detection_layout.addWidget(self.template_status)
        outer.addWidget(detection)
        totems = QGroupBox("Auto totem")
        tof = QFormLayout(totems)
        self.auto_totem = QCheckBox("Use a totem automatically between fishing cycles")
        self.auto_totem.setChecked(bool(self.settings.get("auto_totem", False)))
        self.totem_select = QComboBox()
        self.totem_data = [
            ("Sundial Totem","Advances the day/night cycle","2,000 C$"),
            ("Tempest Totem","Forces rainy weather","Weather"),
            ("Windset Totem","Forces windy weather","Weather"),
            ("Smokescreen Totem","Forces foggy weather","Weather"),
            ("Meteor Totem","Starts a meteor event","75,000 C$"),
            ("Avalanche Totem","Starts an avalanche","150,000 C$"),
            ("Eclipse Totem","Starts an eclipse event","200,000 C$"),
            ("Blizzard Totem","Starts a blizzard","150,000 C$"),
            ("Aurora Totem","Starts Aurora Borealis","500,000 C$ (varies)"),
            ("Cursed Storm Totem","Starts a cursed storm","600,000 C$"),
            ("Zeus Storm Totem","Starts Zeus's Storm","150,000 C$ (varies)"),
            ("Poseidon's Wrath Totem","Starts Poseidon's Wrath","150,000 C$ (varies)"),
            ("Blue Moon Totem","Starts the Blue Moon event","120,000 C$"),
            ("Mutation Totem","Starts a Mutation Surge","250,000 C$"),
            ("Shiny Totem","Starts a Shiny Surge","1,250,000 C$ (varies)"),
            ("Sparkling Totem","Starts Night of the Luminous","1,500,000 C$ (varies)"),
            ("Starfall Totem","Starts Starfall weather","Drop / event"),
            ("Megalodon Hunt Totem","Starts a Megalodon hunt","80,000 C$ (varies)"),
            ("Kraken Hunt Totem","Starts a Kraken hunt","90,000 C$ (varies)"),
            ("Scylla Hunt Totem","Starts a Scylla hunt","100,000 C$ (varies)"),
            ("Colossal Dragon Hunt Totem","Starts a Colossal Dragon hunt","90,000 C$ (varies)"),
            ("Rainbow Totem","Starts Rainbow weather","1,000 S$ (varies)"),
            ("Clearcast Totem","Forces clear weather","Shop / varies"),
            ("Brine Storm Totem","Starts a Brine Storm","Limited / varies"),
            ("Tropical Squall Totem","Forces Tropical Squall weather","800,000 C$"),
            ("Raging Squall Totem","Forces Raging Squall weather","Quest"),
            ("Dripstone Collapse Totem","Starts Dripstone Collapse","7,500,000 C$"),
            ("Bloom Totem","Resets Living Garden flower spawns","Quest / exchange")
        ]
        self.totem_select.addItems([x[0] for x in self.totem_data])
        self.totem_select.setCurrentText(self.settings.get("totem_name", "Sundial Totem"))
        self.totem_info = QLabel()
        self.totem_info.setObjectName("muted")
        self.totem_info.setWordWrap(True)
        self.totem_select.currentIndexChanged.connect(self.update_totem_info)
        self.update_totem_info()
        self.totem_key_input = QLineEdit(str(self.settings.get("totem_key", "3")))
        self.rod_key_input = QLineEdit(str(self.settings.get("rod_key", "1")))
        self.totem_interval_input = QSpinBox()
        self.totem_interval_input.setRange(30, 86400)
        self.totem_interval_input.setValue(int(self.settings.get("totem_interval", 300)))
        tof.addRow(self.auto_totem)
        tof.addRow("Totem metadata", self.totem_select)
        tof.addRow(self.totem_info)
        tof.addRow("Totem inventory slot key", self.totem_key_input)
        tof.addRow("Fishing rod slot key", self.rod_key_input)
        tof.addRow("Use interval (seconds)", self.totem_interval_input)
        note = QLabel("Keep Fisch active. Press the global hotkey while Fisch is focused; this does not bypass the game's AFK rules.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        tof.addRow(note)
        outer.addWidget(totems)
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_settings)
        outer.addWidget(save)
        outer.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.tabs.addTab(page, "Settings")

    def update_totem_info(self):
        idx = self.totem_select.currentIndex()
        if 0 <= idx < len(self.totem_data):
            name, effect, price = self.totem_data[idx]
            self.totem_info.setText(f"{effect} · Listed price/source: {price}. Prices and availability may change.")

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
            vals = [rod.get("name",""),rod.get("area",""),rod.get("luck","—"),rod.get("lure","—"),rod.get("control","—"),rod.get("resilience","—"),rod.get("max_weight","—"),rod.get("price","—"),rod.get("ability","—"),rod.get("source","Fisch Wiki")]
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
            f"Max weight: {rod.get('max_weight','—')}\\nPrice: {rod.get('price','—')}\\n"
            f"Ability: {rod.get('ability','—')}\\n"
            "Luck is a modifier, not a fixed catch percentage. Actual fish odds depend on the fish pool, location, bait, weather and other effects."
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

    def save_settings(self):
        self.settings.update({
            "hotkey":self.hotkey_input.text().strip().lower() or "f12",
            "cast_x":self.cast_x.value(),"cast_y":self.cast_y.value(),
            "scan_interval":self.scan_interval.value(),"cast_hold":self.cast_hold_input.value(),
            "recast_delay":self.recast_delay.value(),
            "auto_recast":self.auto_recast.isChecked(),
            "auto_totem":self.auto_totem.isChecked(),
            "totem_name":self.totem_select.currentText(),
            "totem_key":self.totem_key_input.text().strip(),
            "rod_key":self.rod_key_input.text().strip(),
            "totem_interval":self.totem_interval_input.value()
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
        if self.macro_active:
            self.stop_macro()
        else:
            self.start_macro()

    def start_macro(self):
        self.save_settings_silent()
        self.macro_active = True
        self.worker = FishingWorker(self.settings.copy())
        self.worker.status.connect(self.set_macro_status)
        self.worker.stopped.connect(self.macro_stopped)
        self.quick_state.setText("Starting")
        self.auto_state.setText("Starting")
        self.quick_start.setText("Stop")
        self.start_btn.setText("Stop automation")
        self.status_badge.setText("STARTING")
        self.worker.start()
        self.set_macro_status("Starting automation…")

    def stop_macro(self):
        if self.worker is not None:
            self.worker.stop()
            self.set_macro_status("Stopping…")
            if not self.worker.isRunning():
                self.macro_active = False
                self.macro_stopped()

    def macro_stopped(self):
        self.macro_active = False
        self.quick_start.setText("Start")
        self.quick_state.setText("Stopped")
        self.auto_state.setText("Stopped")
        self.status_badge.setText("IDLE")

    def set_macro_status(self,text):
        self.activity.setText(text)
        self.automation_log.setText(text)
        running = self.macro_active
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
            "auto_recast":self.auto_recast.isChecked(),
            "auto_totem":self.auto_totem.isChecked(),
            "totem_name":self.totem_select.currentText(),
            "totem_key":self.totem_key_input.text().strip(),
            "rod_key":self.rod_key_input.text().strip(),
            "totem_interval":self.totem_interval_input.value()
        })
        save_json(SETTINGS_FILE,self.settings)

    def refresh_status(self):
        if hasattr(self,"template_status"):
            self.template_status.setText("Live screen detection. No templates or recorded movement required.")

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
