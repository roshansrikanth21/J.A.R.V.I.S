"""
J.A.R.V.I.S Voice HUD — Side Panel
====================================
Slides in from the right edge when JARVIS activates.
Auto-hides after 5s of idle. Lives in system tray.
"""
import sys, json, random
import psutil

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint,
    QPropertyAnimation, QEasingCurve, QRectF,
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QIcon, QAction, QPixmap,
)

try:
    import pynvml; pynvml.nvmlInit()
    _GPU = pynvml.nvmlDeviceGetHandleByIndex(0); _GPU_OK = True
except Exception:
    _GPU_OK = False

# ── Palette ──────────────────────────────────────────────────────────────────
C_BG       = QColor( 6,  9, 22, 225)
C_ACCENT   = QColor( 0,210,255,255)
C_AMBER    = QColor(255,160, 20,255)
C_GREEN    = QColor( 40,220,100,255)
C_DIM      = QColor( 50, 65,100,180)
C_BORDER   = QColor( 0,180,255, 55)
C_TEXT     = QColor(200,220,255,255)
C_SUB      = QColor( 90,120,160,200)

W, H       = 380, 600
RING_R     = 18
AUTO_HIDE  = 6000   # ms before panel slides out


# ── WebSocket worker ─────────────────────────────────────────────────────────
class WSWorker(QThread):
    ev   = pyqtSignal(dict)
    conn = pyqtSignal(str)

    def __init__(self, url):
        super().__init__(); self.url = url; self._go = True

    def run(self):
        import asyncio, websockets
        async def _loop():
            while self._go:
                try:
                    self.conn.emit("connecting")
                    async with websockets.connect(self.url, ping_interval=20) as ws:
                        self.conn.emit("connected")
                        while self._go:
                            try:
                                self.ev.emit(json.loads(await asyncio.wait_for(ws.recv(), 2)))
                            except asyncio.TimeoutError:
                                pass
                except Exception:
                    self.conn.emit("disconnected")
                    await asyncio.sleep(3)
        asyncio.run(_loop())

    def stop(self): self._go = False


# ── Stats worker ─────────────────────────────────────────────────────────────
class StatsWorker(QThread):
    ready = pyqtSignal(dict)
    def run(self):
        prev_net = psutil.net_io_counters()
        while True:
            gpu = None
            if _GPU_OK:
                try: gpu = pynvml.nvmlDeviceGetUtilizationRates(_GPU).gpu
                except: pass
            
            # Calculate net speed
            curr_net = psutil.net_io_counters()
            sent = (curr_net.bytes_sent - prev_net.bytes_sent) / 1024
            recv = (curr_net.bytes_recv - prev_net.bytes_recv) / 1024
            prev_net = curr_net
            
            # Battery
            batt = psutil.sensors_battery()
            batt_pct = batt.percent if batt else None
            
            self.ready.emit({
                "cpu": psutil.cpu_percent(interval=1),
                "ram": psutil.virtual_memory().percent,
                "gpu": gpu,
                "net": (sent, recv),
                "batt": batt_pct
            })


# ── Waveform widget ───────────────────────────────────────────────────────────
class Waveform(QWidget):
    N = 28
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedHeight(50)
        self._bars    = [0.05] * self.N
        self._targets = [0.05] * self.N
        self._active  = False
        t = QTimer(self); t.timeout.connect(self._tick); t.start(45)

    def set_active(self, v):
        self._active = v

    def _tick(self):
        for i in range(self.N):
            self._targets[i] = random.uniform(0.15, 1.0) if self._active else 0.04
            self._bars[i] += (self._targets[i] - self._bars[i]) * 0.28
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bw  = (self.width() - (self.N - 1) * 3) / self.N
        h   = self.height()
        for i, v in enumerate(self._bars):
            bh  = max(3, v * h * 0.88)
            x   = i * (bw + 3)
            y   = (h - bh) / 2
            col = QColor(C_ACCENT if self._active else C_DIM)
            col.setAlpha(int(80 + 170 * v) if self._active else 60)
            p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, y, bw, bh), bw / 2, bw / 2)


# ── Reactor ring ─────────────────────────────────────────────────────────────
class Ring(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(RING_R*2+14, RING_R*2+14)
        self.state = "idle"; self._a = 0; self._p = 0.0; self._pd = 1
        t = QTimer(self); t.timeout.connect(self._tick); t.start(28)

    def set_state(self, s): self.state = s

    def _tick(self):
        self._a  = (self._a + 5) % 360
        self._p += 0.07 * self._pd
        if self._p >= 1 or self._p <= 0: self._pd *= -1
        self.update()

    def paintEvent(self, _):
        p  = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width()  // 2
        cy = self.height() // 2
        r  = RING_R
        col = {"listening": C_ACCENT, "thinking": C_AMBER,
               "speaking":  C_GREEN,  "idle":     C_DIM}[self.state]

        g = QRadialGradient(cx, cy, r + 6)
        gc = QColor(col); gc.setAlpha(int(50 + 40 * self._p))
        g.setColorAt(0, gc); g.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx-r-6, cy-r-6, (r+6)*2, (r+6)*2)

        p.setBrush(QBrush(QColor(8,12,28,200)))
        p.setPen(QPen(QColor(col.red(),col.green(),col.blue(),50), 1.2))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)

        if self.state != "idle":
            pen = QPen(QColor(col), 2.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            span = 260 if self.state == "thinking" else 130
            p.drawArc(QRectF(cx-r+2, cy-r+2, (r-2)*2, (r-2)*2),
                      -self._a*16, -span*16)

        dc = QColor(col); dc.setAlpha(int(140+100*self._p))
        p.setBrush(QBrush(dc)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx-4, cy-4, 8, 8)


# ── Main HUD panel ────────────────────────────────────────────────────────────
class JarvisHUD(QWidget):
    def __init__(self, ws_url="ws://localhost:8000/ws"):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(W, H)

        self._pinned       = False
        self._state        = "idle"
        self._trace        = []        # agent steps
        self._tasks        = []        # mission board
        self._session_start = __import__("time").time()
        self._step_count   = 0
        self._mem_count    = 0
        self._model_name   = "llama3.1:8b"
        self._stats        = {}
        self._drag_pos     = QPoint()
        self._visible_out  = True      # starts shown, slides in on first event

        # ── auto-hide timer ──────────────────────────────────────────────────
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._slide_out)

        # ── slide animation ──────────────────────────────────────────────────
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._build_ui()
        self._setup_tray()
        self._position_offscreen()
        self.show()
        self._slide_in()

        # workers
        self._ws = WSWorker(ws_url)
        self._ws.ev.connect(self._on_event)
        self._ws.conn.connect(self._on_conn)
        self._ws.start()

        self._sw = StatsWorker()
        self._sw.ready.connect(self._on_stats)
        self._sw.start()

        # session clock
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_session_label)
        self._clock.start(1000)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(0)

        # — Header ————————————————————————————————————————————————————————
        hdr = QHBoxLayout(); hdr.setSpacing(10)
        self._ring = Ring(self)
        hdr.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout(); title_col.setSpacing(1)
        t = QLabel("J·A·R·V·I·S")
        t.setStyleSheet("color:#00d4ff;font-size:13px;font-weight:700;"
                        "letter-spacing:3px;background:transparent;")
        self._conn_lbl = QLabel("○ CONNECTING")
        self._conn_lbl.setStyleSheet("color:#404870;font-size:8px;"
                                     "letter-spacing:2px;background:transparent;")
        title_col.addWidget(t); title_col.addWidget(self._conn_lbl)
        hdr.addLayout(title_col)
        hdr.addStretch()

        # pin button
        self._pin_btn = QLabel("📌")
        self._pin_btn.setStyleSheet("color:#303850;font-size:14px;"
                                    "background:transparent;cursor:pointer;")
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.mousePressEvent = lambda _: self._toggle_pin()
        hdr.addWidget(self._pin_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(hdr)
        root.addSpacing(10)
        root.addWidget(self._hr())

        # — Waveform ——————————————————————————————————————————————————————
        root.addSpacing(6)
        self._wave = Waveform()
        root.addWidget(self._wave)

        # — Transcript ————————————————————————————————————————————————————
        root.addSpacing(6)
        self._user_lbl = QLabel("")
        self._user_lbl.setWordWrap(True)
        self._user_lbl.setStyleSheet(
            "color:#c0d8ff;font-size:14px;font-weight:600;background:transparent;"
        )
        self._user_lbl.setMaximumWidth(W - 36)
        root.addWidget(self._user_lbl)
        root.addSpacing(4)
        root.addWidget(self._hr())
        root.addSpacing(4)

        # — Agent trace ———————————————————————————————————————————————————
        trace_hdr = QLabel("  AGENT TRACE")
        trace_hdr.setStyleSheet("color:#2a4060;font-size:8px;letter-spacing:2px;"
                                "background:transparent;")
        root.addWidget(trace_hdr)
        root.addSpacing(2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(120)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:4px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#1a3050;border-radius:2px;}"
        )
        self._trace_inner = QWidget()
        self._trace_inner.setStyleSheet("background:transparent;")
        self._trace_layout = QVBoxLayout(self._trace_inner)
        self._trace_layout.setContentsMargins(0, 0, 0, 0)
        self._trace_layout.setSpacing(2)
        self._trace_layout.addStretch()
        scroll.setWidget(self._trace_inner)
        root.addWidget(scroll)
        self._trace_scroll = scroll

        root.addSpacing(4)
        root.addWidget(self._hr())
        root.addSpacing(4)

        # — Mission Board (Tasks) —————————————————————————————————————————
        mission_hdr = QLabel("  MISSION STATUS")
        mission_hdr.setStyleSheet("color:#2a4060;font-size:8px;letter-spacing:2px;"
                                   "background:transparent;")
        root.addWidget(mission_hdr)
        root.addSpacing(2)

        self._task_container = QWidget()
        self._task_container.setStyleSheet("background:transparent;")
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(0, 0, 0, 0)
        self._task_layout.setSpacing(3)
        root.addWidget(self._task_container)

        root.addSpacing(4)
        root.addWidget(self._hr())
        root.addSpacing(4)

        # — Response ——————————————————————————————————————————————————————
        resp_hdr = QLabel("  RESPONSE")
        resp_hdr.setStyleSheet("color:#2a4060;font-size:8px;letter-spacing:2px;"
                               "background:transparent;")
        root.addWidget(resp_hdr)
        root.addSpacing(2)
        self._resp_lbl = QLabel("")
        self._resp_lbl.setWordWrap(True)
        self._resp_lbl.setStyleSheet(
            "color:#00d4ff;font-size:11px;line-height:150%;background:transparent;"
        )
        self._resp_lbl.setMaximumWidth(W - 36)
        root.addWidget(self._resp_lbl)

        root.addStretch()
        root.addWidget(self._hr())
        root.addSpacing(4)

        # — Footer: model info + stats ————————————————————————————————————
        self._model_lbl = QLabel(f"⬡ {self._model_name}  ·  0 memories  ·  0 steps")
        self._model_lbl.setStyleSheet(
            "color:#2a4a6a;font-size:8px;letter-spacing:1px;background:transparent;"
        )
        root.addWidget(self._model_lbl)
        root.addSpacing(2)
        self._stats_lbl = QLabel("CPU --%  ·  RAM --%  ·  GPU --")
        self._stats_lbl.setStyleSheet(
            "color:#1e3a50;font-size:8px;letter-spacing:1px;background:transparent;"
        )
        root.addWidget(self._stats_lbl)
        root.addSpacing(2)
        self._session_lbl = QLabel("Session: 0s")
        self._session_lbl.setStyleSheet(
            "color:#1a3040;font-size:8px;letter-spacing:1px;background:transparent;"
        )
        root.addWidget(self._session_lbl)

    def _hr(self):
        l = QLabel(); l.setFixedHeight(1)
        l.setStyleSheet("background:rgba(0,180,255,30);")
        return l

    # ── Glass paint ───────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, W-2, H-2), 14, 14)
        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.0, QColor(10,14,34,225))
        grad.setColorAt(1.0, QColor( 5, 7,16,225))
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(C_BORDER, 1.5)); p.drawPath(path)
        # top highlight
        p.setPen(QPen(QColor(0,200,255,40), 1))
        p.drawLine(16, 1, W-16, 1)

    # ── Drag ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseDoubleClickEvent(self, _):
        self._slide_in()

    # ── Slide animation ───────────────────────────────────────────────────────
    def _screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()

    def _position_offscreen(self):
        sc = self._screen_rect()
        self.move(sc.right() + 4, sc.center().y() - H // 2)

    def _slide_in(self):
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        sc   = self._screen_rect()
        dest = QPoint(sc.right() - W - 4, sc.center().y() - H // 2)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(dest)
        try: self._anim.finished.disconnect()
        except: pass
        self.show()
        self._anim.start()
        self._visible_out = False
        self._restart_hide_timer()

    def _slide_out(self):
        if self._pinned or self._visible_out:
            return
        sc   = self._screen_rect()
        dest = QPoint(sc.right() + 4, self.y())
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(dest)
        try: self._anim.finished.disconnect()
        except: pass
        self._anim.finished.connect(self.hide)
        self._anim.start()
        self._visible_out = True

    def _restart_hide_timer(self):
        self._hide_timer.stop()
        if not self._pinned:
            self._hide_timer.start(AUTO_HIDE)

    # ── Pin ───────────────────────────────────────────────────────────────────
    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._pin_btn.setStyleSheet(
            f"color:{'#00d4ff' if self._pinned else '#303850'};"
            "font-size:14px;background:transparent;cursor:pointer;"
        )
        if not self._pinned:
            self._restart_hide_timer()
        else:
            self._hide_timer.stop()

    # ── Tray ─────────────────────────────────────────────────────────────────
    def _setup_tray(self):
        px = QPixmap(32, 32); px.fill(Qt.GlobalColor.transparent)
        qp = QPainter(px)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setBrush(QBrush(C_ACCENT)); qp.setPen(Qt.PenStyle.NoPen)
        qp.drawEllipse(4, 4, 24, 24); qp.end()

        self._tray = QSystemTrayIcon(QIcon(px), self)
        menu = QMenu()
        for label, fn in [
            ("Show", self._slide_in),
            ("Hide", self._slide_out),
            ("Pin / Unpin", self._toggle_pin),
            ("Quit", QApplication.quit),
        ]:
            act = QAction(label, self)
            act.triggered.connect(fn)
            if label == "Quit":
                menu.addSeparator()
            menu.addAction(act)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("J.A.R.V.I.S")
        self._tray.activated.connect(
            lambda r: self._slide_in() if r == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self._tray.show()

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_event(self, data: dict):
        t = data.get("type", "")
        self._slide_in()   # any event wakes the panel

        if t == "state":
            raw = data.get("status", "idle")
            if "speaking" in raw:   self._set_state("speaking")
            elif raw in ("idle", ""):  self._set_state("idle")
            elif any(k in raw for k in ("listening", "transcrib", "waiting")):
                self._set_state("listening")
            else:                   self._set_state("thinking")

        elif t == "transcription":
            txt = data.get("text", "")
            self._user_lbl.setText(f'\u201c{txt}\u201d')
            self._set_state("thinking")
            self._resp_lbl.setText("")

        elif t == "llm_response":
            self._resp_lbl.setText(data.get("text", "")[:320])
            self._set_state("speaking")

        elif t == "tasks":
            self._update_tasks(data.get("message", []))

        elif t == "proactive_event":
            msg = data.get("message", {})
            txt = msg.get("text", "")
            self._resp_lbl.setText(f"PROACTIVE: {txt}")
            self._push_trace("✧", f"Proactive Suggestion: {txt[:60]}", "#c080ff")
            self._slide_in()

        elif t == "memory_stats":
            stats = data.get("message", {}) # data is {"type": "memory_stats", "message": {...}}
            self._mem_count = stats.get("total_entries", 0)
            self._update_model_label()

        elif t in ("agent_event",):
            ev    = data.get("event", {})
            etype = ev.get("type", "")
            if etype == "AGENT_THOUGHT":
                self._push_trace("⟳", ev.get("text", "")[:80], "#ffa020")
            elif etype == "AGENT_TOOL_CALL":
                args_str = json.dumps(ev.get("args", {}))[:48]
                self._push_trace("▶", f"{ev.get('action')}({args_str})", "#00d4ff")
                self._step_count += 1
            elif etype == "AGENT_TOOL_RESULT":
                obs = ev.get("observation", "")
                self._push_trace("✓", str(obs)[:80], "#40e080")
            self._update_model_label()

    def _on_conn(self, status: str):
        cfg = {
            "connected":    ("#00ff80", "◉ ONLINE"),
            "connecting":   ("#ffa020", "◎ CONNECTING..."),
            "disconnected": ("#ff4040", "○ OFFLINE"),
        }
        col, txt = cfg.get(status, ("#404870", status.upper()))
        self._conn_lbl.setText(txt)
        self._conn_lbl.setStyleSheet(
            f"color:{col};font-size:8px;letter-spacing:2px;background:transparent;"
        )

    def _on_stats(self, s: dict):
        self._stats = s
        def c(v):
            if v is None: return "#1e3a50"
            return "#ff4040" if v>85 else "#ffa020" if v>60 else "#2a6040"
        cpu, ram, gpu = s.get("cpu"), s.get("ram"), s.get("gpu")
        net = s.get("net", (0,0))
        batt = s.get("batt")
        
        gpu_txt = f"GPU {gpu:.0f}%" if gpu is not None else "GPU n/a"
        net_txt = f"⇅ {net[1]:.0f}/{net[0]:.0f} KB/s"
        batt_txt = f" | ⚡ {batt:.0f}%" if batt is not None else ""
        
        self._stats_lbl.setText(
            f"CPU {cpu:.0f}%  ·  RAM {ram:.0f}%  ·  {gpu_txt}  ·  {net_txt}{batt_txt}"
        )
        # colour worst metric
        worst = max(v for v in [cpu, ram] if v is not None)
        self._stats_lbl.setStyleSheet(
            f"color:{c(worst)};font-size:8px;letter-spacing:1px;background:transparent;"
        )

    def _update_session_label(self):
        elapsed = int(__import__("time").time() - self._session_start)
        h, rem  = divmod(elapsed, 3600)
        m, s    = divmod(rem, 60)
        fmt = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"
        self._session_lbl.setText(f"Session: {fmt}")

    def _update_model_label(self):
        self._model_lbl.setText(
            f"⬡ {self._model_name}  ·  {self._mem_count} memories  ·  {self._step_count} steps"
        )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_state(self, state: str):
        self._state = state
        self._ring.set_state(state)
        self._wave.set_active(state == "listening")

    def _update_tasks(self, tasks):
        """Refreshes the Mission Status section."""
        # Clear current tasks
        while self._task_layout.count():
            item = self._task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._tasks = tasks[:3] # Show only top 3 tasks
        for task in self._tasks:
            t_box = QWidget()
            t_lay = QHBoxLayout(t_box)
            t_lay.setContentsMargins(4, 0, 4, 0)
            
            icon = "▣" if task.get("status") == "active" else "□"
            col = "#00d4ff" if task.get("status") == "active" else "#3a5070"
            
            lbl = QLabel(f"<span style='color:{col}'>{icon}</span>  {task.get('t', '')[:40]}")
            lbl.setStyleSheet("color:#8090b0; font-size:9px; background:transparent;")
            
            t_lay.addWidget(lbl)
            t_lay.addStretch()
            
            eta = task.get("eta", "")
            if eta:
                eta_lbl = QLabel(eta)
                eta_lbl.setStyleSheet("color:#3a5070; font-size:8px; background:transparent;")
                t_lay.addWidget(eta_lbl)
                
            self._task_layout.addWidget(t_box)

    def _push_trace(self, icon: str, text: str, colour: str):
        """Appends a step to the agent trace scroll area."""
        lbl = QLabel(f"<span style='color:{colour}'>{icon}</span>  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:#8090b0;font-size:9px;padding:1px 2px;background:transparent;"
        )
        lbl.setMaximumWidth(W - 52)
        # insert before the stretch
        count = self._trace_layout.count()
        self._trace_layout.insertWidget(count - 1, lbl)
        self._trace.append(lbl)

        # keep max 20 rows
        if len(self._trace) > 20:
            old = self._trace.pop(0)
            self._trace_layout.removeWidget(old)
            old.deleteLater()

        # auto-scroll to bottom
        QTimer.singleShot(10, lambda: self._trace_scroll.verticalScrollBar().setValue(
            self._trace_scroll.verticalScrollBar().maximum()
        ))

    def closeEvent(self, e):
        e.ignore(); self._slide_out()


# ── Entry point ───────────────────────────────────────────────────────────────
def launch(ws_url="ws://localhost:8000/ws"):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    hud = JarvisHUD(ws_url=ws_url)
    return app.exec()

if __name__ == "__main__":
    sys.exit(launch())
