"""
J.A.R.V.I.S HUD Overlay
========================
PyQt6 always-on-top transparent desktop overlay.

Features:
  - Arc-reactor status ring (idle / listening / thinking / speaking)
  - Live transcript + response feed (last 4 exchanges)
  - Real-time system stats: CPU, RAM, GPU (via pynvml if available)
  - WebSocket client — receives events from the JARVIS FastAPI backend
  - System tray icon with show/hide/quit menu
  - Draggable — click-drag anywhere to reposition
  - Snaps to bottom-right on first launch
"""

import sys
import json
import time
import math
import threading

import psutil
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QRectF,
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont,
    QRadialGradient, QPainterPath, QIcon, QAction,
    QPixmap, QLinearGradient, QFontDatabase,
)

# ── Optional GPU stats via pynvml ────────────────────────────────────────────
try:
    import pynvml
    pynvml.nvmlInit()
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    _GPU_AVAILABLE = True
except Exception:
    _GPU_AVAILABLE = False

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG          = QColor(8,   10,  24,  210)   # deep navy, mostly opaque
C_BORDER      = QColor(0,   180, 255,  80)   # cyan border, subtle
C_ACCENT      = QColor(0,   212, 255, 255)   # bright cyan
C_AMBER       = QColor(255, 160,  20, 255)   # thinking / active
C_GREEN       = QColor( 50, 255, 120, 255)   # speaking
C_DIM         = QColor( 60,  70, 100, 180)   # idle dim
C_TEXT        = QColor(200, 220, 255, 255)   # primary text
C_SUBTEXT     = QColor(100, 130, 170, 200)   # secondary text
C_USER_BUBBLE = QColor( 30,  40,  80, 160)
C_BOT_BUBBLE  = QColor( 15,  25,  50, 160)

HUD_W, HUD_H = 400, 310
RING_R        = 22   # status ring radius


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket worker thread
# ─────────────────────────────────────────────────────────────────────────────
class WSWorker(QThread):
    """Connects to the JARVIS backend WebSocket and emits Qt signals."""
    event_received = pyqtSignal(dict)
    connection_status = pyqtSignal(str)   # "connected" | "disconnected"

    def __init__(self, url="ws://localhost:8000/ws"):
        super().__init__()
        self.url = url
        self._running = True

    def run(self):
        import asyncio, websockets

        async def listen():
            while self._running:
                try:
                    self.connection_status.emit("connecting")
                    async with websockets.connect(self.url, ping_interval=20) as ws:
                        self.connection_status.emit("connected")
                        while self._running:
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                                data = json.loads(raw)
                                self.event_received.emit(data)
                            except asyncio.TimeoutError:
                                continue
                except Exception:
                    self.connection_status.emit("disconnected")
                    await asyncio.sleep(3)   # retry in 3s

        asyncio.run(listen())

    def stop(self):
        self._running = False


# ─────────────────────────────────────────────────────────────────────────────
# Stats poller thread
# ─────────────────────────────────────────────────────────────────────────────
class StatsWorker(QThread):
    stats_ready = pyqtSignal(dict)

    def run(self):
        while True:
            cpu  = psutil.cpu_percent(interval=1)
            ram  = psutil.virtual_memory().percent
            gpu  = self._gpu()
            self.stats_ready.emit({"cpu": cpu, "ram": ram, "gpu": gpu})

    def _gpu(self):
        if not _GPU_AVAILABLE:
            return None
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE)
            return util.gpu
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Arc Reactor ring widget
# ─────────────────────────────────────────────────────────────────────────────
class ReactorRing(QWidget):
    """Animated arc-reactor style status indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(RING_R * 2 + 16, RING_R * 2 + 16)
        self.state  = "idle"       # idle | listening | thinking | speaking
        self._angle = 0
        self._pulse = 0.0
        self._pulse_dir = 1

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_state(self, state: str):
        self.state = state
        self.update()

    def _tick(self):
        self._angle = (self._angle + 4) % 360
        self._pulse += 0.06 * self._pulse_dir
        if self._pulse >= 1.0 or self._pulse <= 0.0:
            self._pulse_dir *= -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width()  // 2
        cy = self.height() // 2
        r  = RING_R

        # State colour
        if self.state == "listening":
            base_col = C_ACCENT
        elif self.state == "thinking":
            base_col = C_AMBER
        elif self.state == "speaking":
            base_col = C_GREEN
        else:
            base_col = C_DIM

        # Outer glow radial gradient
        glow = QRadialGradient(cx, cy, r + 8)
        gc   = QColor(base_col)
        gc.setAlpha(int(60 + 50 * self._pulse))
        glow.setColorAt(0, gc)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - r - 8, cy - r - 8, (r + 8) * 2, (r + 8) * 2)

        # Background circle
        p.setBrush(QBrush(QColor(10, 15, 30, 200)))
        p.setPen(QPen(QColor(base_col.red(), base_col.green(), base_col.blue(), 60), 1.5))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Spinning arc (hidden when idle)
        if self.state != "idle":
            arc_col = QColor(base_col)
            arc_col.setAlpha(220)
            pen = QPen(arc_col, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            span  = 240 if self.state == "thinking" else 120
            rect  = QRectF(cx - r + 2, cy - r + 2, (r - 2) * 2, (r - 2) * 2)
            p.drawArc(rect, -self._angle * 16, -span * 16)

        # Inner dot
        inner_col = QColor(base_col)
        inner_col.setAlpha(int(160 + 80 * self._pulse))
        p.setBrush(QBrush(inner_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - 5, cy - 5, 10, 10)


# ─────────────────────────────────────────────────────────────────────────────
# Main HUD Window
# ─────────────────────────────────────────────────────────────────────────────
class JarvisHUD(QWidget):

    def __init__(self, ws_url="ws://localhost:8000/ws"):
        super().__init__()

        # Window flags: frameless, transparent, always on top, tool window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(HUD_W, HUD_H)

        # ── State ──────────────────────────────────────────────────────────
        self._drag_pos    = QPoint()
        self._state       = "idle"
        self._status_text = "System ready."
        self._transcript  = []      # list of {"role": "user"|"jarvis", "text": str}
        self._tool_step   = ""
        self._ws_status   = "disconnected"
        self._stats       = {"cpu": 0.0, "ram": 0.0, "gpu": None}

        # ── Build UI ───────────────────────────────────────────────────────
        self._build_ui()
        self._snap_to_corner()
        self._setup_tray()

        # ── Workers ────────────────────────────────────────────────────────
        self._ws = WSWorker(ws_url)
        self._ws.event_received.connect(self._on_event)
        self._ws.connection_status.connect(self._on_ws_status)
        self._ws.start()

        self._stats_worker = StatsWorker()
        self._stats_worker.stats_ready.connect(self._on_stats)
        self._stats_worker.start()

    # ── Snap to bottom-right ───────────────────────────────────────────────
    def _snap_to_corner(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - HUD_W - 16, screen.bottom() - HUD_H - 16)

    # ── UI construction ────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # ── Header row ──────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)

        self._ring = ReactorRing(self)
        header.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._title_lbl = QLabel("J.A.R.V.I.S")
        self._title_lbl.setStyleSheet(
            "color: #00d4ff; font-size: 15px; font-weight: 700; "
            "letter-spacing: 3px; background: transparent;"
        )
        self._ws_lbl = QLabel("◉ CONNECTING...")
        self._ws_lbl.setStyleSheet(
            "color: #404870; font-size: 9px; letter-spacing: 2px; background: transparent;"
        )
        title_col.addWidget(self._title_lbl)
        title_col.addWidget(self._ws_lbl)
        header.addLayout(title_col)

        header.addStretch()

        # System stats (vertical stack, right-aligned)
        stats_col = QVBoxLayout()
        stats_col.setSpacing(1)
        self._cpu_lbl = self._stat_label("CPU 0%")
        self._ram_lbl = self._stat_label("RAM 0%")
        self._gpu_lbl = self._stat_label("GPU --")
        stats_col.addWidget(self._cpu_lbl)
        stats_col.addWidget(self._ram_lbl)
        stats_col.addWidget(self._gpu_lbl)
        header.addLayout(stats_col)

        layout.addLayout(header)

        # ── Divider ──────────────────────────────────────────────────────
        layout.addWidget(self._divider())

        # ── Status line ──────────────────────────────────────────────────
        self._status_lbl = QLabel("System ready.")
        self._status_lbl.setStyleSheet(
            "color: #64a0d0; font-size: 10px; letter-spacing: 1px; background: transparent;"
        )
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        # ── Divider ──────────────────────────────────────────────────────
        layout.addWidget(self._divider())

        # ── Transcript feed ───────────────────────────────────────────────
        self._transcript_labels = []
        for _ in range(4):
            lbl = QLabel("")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "color: #c8dcff; font-size: 10px; background: transparent;"
            )
            lbl.setMaximumWidth(HUD_W - 36)
            layout.addWidget(lbl)
            self._transcript_labels.append(lbl)

        # ── Divider ──────────────────────────────────────────────────────
        layout.addWidget(self._divider())

        # ── Tool step ────────────────────────────────────────────────────
        self._tool_lbl = QLabel("")
        self._tool_lbl.setStyleSheet(
            "color: #ffa020; font-size: 9px; letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(self._tool_lbl)

        layout.addStretch()

    def _stat_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #405060; font-size: 9px; letter-spacing: 1px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        return lbl

    def _divider(self):
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(0, 180, 255, 40);")
        return line

    # ── Custom paint — glass background + border ───────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer border glow
        pen = QPen(C_BORDER, 1.5)
        p.setPen(pen)
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 12, 12)

        # Background gradient
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(10, 14, 32, 215))
        grad.setColorAt(1.0, QColor( 6,  8, 18, 215))
        p.fillPath(path, QBrush(grad))
        p.drawPath(path)

        # Subtle top-edge highlight
        highlight = QPen(QColor(0, 200, 255, 50), 1)
        p.setPen(highlight)
        p.drawLine(14, 1, self.width() - 14, 1)

    # ── Drag support ────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseDoubleClickEvent(self, e):
        self._snap_to_corner()

    # ── System tray ────────────────────────────────────────────────────────
    def _setup_tray(self):
        # Create a small cyan circle icon programmatically
        px = QPixmap(32, 32)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(C_ACCENT))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()

        self._tray = QSystemTrayIcon(QIcon(px), self)
        menu = QMenu()

        show_act   = QAction("Show HUD",    self)
        hide_act   = QAction("Hide HUD",    self)
        corner_act = QAction("Snap to Corner", self)
        quit_act   = QAction("Quit HUD",    self)

        show_act.triggered.connect(self.show)
        hide_act.triggered.connect(self.hide)
        corner_act.triggered.connect(self._snap_to_corner)
        quit_act.triggered.connect(QApplication.quit)

        menu.addAction(show_act)
        menu.addAction(hide_act)
        menu.addAction(corner_act)
        menu.addSeparator()
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("J.A.R.V.I.S HUD")
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.setVisible(not self.isVisible())

    # ── WebSocket event handler ─────────────────────────────────────────────
    def _on_event(self, data: dict):
        t = data.get("type", "")

        if t == "state":
            raw_status = data.get("status", "idle")
            # Map backend status strings to ring states
            if "speaking" in raw_status:
                self._set_state("speaking")
            elif "listening" in raw_status or "transcrib" in raw_status:
                self._set_state("listening")
            elif "think" in raw_status.lower() or "processing" in raw_status.lower():
                self._set_state("thinking")
            else:
                self._set_state("idle")
            self._status_lbl.setText(data.get("text", "")[:80])

        elif t == "transcription":
            self._push_transcript("you", data.get("text", ""))
            self._set_state("thinking")

        elif t == "llm_response":
            self._push_transcript("jarvis", data.get("text", ""))
            self._set_state("speaking")

        elif t in ("agent_event", "agent_tool"):
            event = data.get("event", data)
            etype = event.get("type", "")
            if etype == "AGENT_THOUGHT":
                self._status_lbl.setText(f"⟳ {event.get('text','')[:75]}")
                self._set_state("thinking")
            elif etype == "AGENT_TOOL_CALL":
                action = event.get("action", "tool")
                self._tool_lbl.setText(f"▶ {action}({json.dumps(event.get('args', {}))[:40]})")
            elif etype == "AGENT_TOOL_RESULT":
                obs = event.get("observation", "")[:60]
                self._tool_lbl.setText(f"✓ {obs}")

        elif t == "audio_level":
            pass  # could animate waveform here later

    def _on_ws_status(self, status: str):
        self._ws_status = status
        colours = {
            "connected":    ("#00ff80", "◉ ONLINE"),
            "connecting":   ("#ffa020", "◎ CONNECTING..."),
            "disconnected": ("#ff4040", "○ OFFLINE"),
        }
        col, label = colours.get(status, ("#404870", status.upper()))
        self._ws_lbl.setText(label)
        self._ws_lbl.setStyleSheet(
            f"color: {col}; font-size: 9px; letter-spacing: 2px; background: transparent;"
        )

    # ── Helpers ────────────────────────────────────────────────────────────
    def _set_state(self, state: str):
        self._state = state
        self._ring.set_state(state)

    def _push_transcript(self, role: str, text: str):
        self._transcript.append({"role": role, "text": text})
        self._transcript = self._transcript[-4:]  # keep last 4
        for i, lbl in enumerate(self._transcript_labels):
            if i < len(self._transcript):
                entry = self._transcript[i]
                prefix = "YOU  " if entry["role"] == "you" else "J.A.R"
                col    = "#a0c8ff" if entry["role"] == "you" else "#00d4ff"
                lbl.setStyleSheet(
                    f"color: {col}; font-size: 10px; background: transparent;"
                )
                lbl.setText(f"{prefix}  {entry['text'][:52]}{'…' if len(entry['text'])>52 else ''}")
            else:
                lbl.setText("")

    def _on_stats(self, stats: dict):
        self._stats = stats
        cpu = stats["cpu"]
        ram = stats["ram"]
        gpu = stats["gpu"]

        def col(pct):
            if pct is None: return "#405060"
            if pct > 85: return "#ff4040"
            if pct > 60: return "#ffa020"
            return "#3a9060"

        self._cpu_lbl.setText(f"CPU {cpu:.0f}%")
        self._cpu_lbl.setStyleSheet(
            f"color: {col(cpu)}; font-size: 9px; letter-spacing: 1px; background: transparent;"
        )
        self._ram_lbl.setText(f"RAM {ram:.0f}%")
        self._ram_lbl.setStyleSheet(
            f"color: {col(ram)}; font-size: 9px; letter-spacing: 1px; background: transparent;"
        )
        if gpu is not None:
            self._gpu_lbl.setText(f"GPU {gpu:.0f}%")
            self._gpu_lbl.setStyleSheet(
                f"color: {col(gpu)}; font-size: 9px; letter-spacing: 1px; background: transparent;"
            )

    # ── Close == hide (stays in tray) ──────────────────────────────────────
    def closeEvent(self, e):
        e.ignore()
        self.hide()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def launch(ws_url: str = "ws://localhost:8000/ws"):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    hud = JarvisHUD(ws_url=ws_url)
    hud.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(launch())
