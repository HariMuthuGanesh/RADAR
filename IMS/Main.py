import sys, os, time, struct, threading
import numpy as np
import serial
import serial.tools.list_ports
from collections import deque

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QGroupBox, QGridLayout,
    QTextEdit, QFrame, QScrollArea, QDoubleSpinBox, QSplitter,
    QTabWidget, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QMutex
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QFontDatabase

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.pyplot as plt

# ══════════════════════════════════════════════════════════════════
#  PROTOCOL CONSTANTS
# ══════════════════════════════════════════════════════════════════
MAGIC_WORD      = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
HEADER_SIZE     = 40          # bytes
CLI_BAUD        = 115200
DATA_BAUD       = 921600
FALL_THRESHOLD  = 0.5         # metres
DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "AOP_6m_default.cfg")

# TI People Tracking SDK TLV IDs
TLV_POINT_CLOUD      = 1   # Detected points (x,y,z,doppler) Cartesian
TLV_POINT_CLOUD_SIDE = 4   # Side-info per point (snr, noise)
TLV_TARGET_LIST      = 6   # Tracked targets — People Tracking SDK primary
TLV_TARGET_IDX       = 7   # Point-to-target index array
TLV_TARGET_LIST_ALT  = 12  # Alternate target list ID (OOB / SDK 3.x fallback)

# ══════════════════════════════════════════════════════════════════
#  COLOUR PALETTE  — Phosphor-terminal industrial dark
# ══════════════════════════════════════════════════════════════════
BG          = "#0b0e0b"
PANEL       = "#0f130f"
BORDER      = "#1a2a1a"
PHOSPHOR    = "#39ff14"       # classic radar green
DIM_GREEN   = "#1f6b10"
AMBER       = "#ffb300"
RED_ALERT   = "#ff2020"
CYAN_INFO   = "#00e5cc"
WHITE_TEXT  = "#d4e8d4"
SUBTEXT     = "#4a6b4a"
GRID_COL    = "#14201a"

# ══════════════════════════════════════════════════════════════════
#  TLV FRAME PARSER  —  TI People Tracking SDK
# ══════════════════════════════════════════════════════════════════
class RadarFrame:
    __slots__ = ["frame_num", "points", "targets"]
    def __init__(self):
        self.frame_num = 0
        self.points    = np.empty((0, 4), dtype=np.float32)   # x,y,z,doppler
        self.targets   = []                                     # list of dicts

class RadarParser:
    """
    Robust TLV parser for IWR6843AOP People Tracking SDK.

    Point cloud  — TLV type 1:
        Each point: x(f32), y(f32), z(f32), doppler(f32)  → 16 bytes

    Target list  — TLV type 6  (primary, People Tracking SDK)
                   TLV type 12 (fallback, OOB / SDK 3.x):
        Each target: tid(u32), x(f32), y(f32), z(f32),
                     vx(f32), vy(f32), vz(f32), ax(f32), ay(f32), az(f32),
                     ec[16](f32), g(f32), confidenceLevel(f32)
        → 4 + 9*4 + 16*4 + 4 + 4 = 112 bytes  (SDK 3.x)
        OR simpler:  tid(u32) + x,y,z,vx,vy,vz,ax,ay,az (9×f32) = 40 bytes
    Parser auto-detects stride from TLV length / num_targets.
    """

    def parse_buffer(self, buf: bytes):
        frames = []
        while True:
            idx = buf.find(MAGIC_WORD)
            if idx < 0:
                # Keep last 7 bytes — a magic word might be split across reads
                buf = buf[-7:] if len(buf) >= 7 else buf
                break
            if idx > 0:
                buf = buf[idx:]
            if len(buf) < HEADER_SIZE:
                break
            # total_len is at byte offset 12 in the header
            if len(buf) < 16:
                break
            total_len = struct.unpack_from("<I", buf, 12)[0]
            # Sanity-check: TI frames are typically 50–5000 bytes
            if total_len < HEADER_SIZE or total_len > 65536:
                # Bad sync — skip 1 byte and re-search
                buf = buf[1:]
                continue
            if len(buf) < total_len:
                break
            frame = self._parse_frame(buf[:total_len])
            if frame is not None:
                frames.append(frame)
            buf = buf[total_len:]
        return frames, buf

    def _parse_frame(self, data: bytes):
        if data[:8] != MAGIC_WORD:
            return None
        f = RadarFrame()
        off = 8
        try:
            _ver        = struct.unpack_from("<I", data, off)[0]; off += 4
            _total_len  = struct.unpack_from("<I", data, off)[0]; off += 4
            _plat       = struct.unpack_from("<I", data, off)[0]; off += 4
            f.frame_num = struct.unpack_from("<I", data, off)[0]; off += 4
            _cpu_time   = struct.unpack_from("<I", data, off)[0]; off += 4
            num_det     = struct.unpack_from("<I", data, off)[0]; off += 4
            num_tlvs    = struct.unpack_from("<I", data, off)[0]; off += 4
            _sub        = struct.unpack_from("<I", data, off)[0]; off += 4
        except struct.error:
            return None

        for _ in range(num_tlvs):
            if off + 8 > len(data):
                break
            tlv_type = struct.unpack_from("<I", data, off)[0]; off += 4
            tlv_len  = struct.unpack_from("<I", data, off)[0]; off += 4
            if off + tlv_len > len(data):
                break
            tlv_data = data[off : off + tlv_len]; off += tlv_len

            if tlv_type == TLV_POINT_CLOUD:
                f.points = self._parse_points(tlv_data, num_det)
            elif tlv_type in (TLV_TARGET_LIST, TLV_TARGET_LIST_ALT):
                f.targets = self._parse_targets(tlv_data)

        return f

    def _parse_points(self, data: bytes, n: int):
        """
        Each point = x, y, z, doppler  (4 × float32 = 16 bytes).
        n comes from the header numDetectedObj field.
        """
        stride = 16
        if n == 0:
            n = len(data) // stride
        pts = []
        for i in range(n):
            if (i + 1) * stride > len(data):
                break
            x, y, z, d = struct.unpack_from("<ffff", data, i * stride)
            pts.append([x, y, z, d])
        return np.array(pts, dtype=np.float32) if pts else np.empty((0, 4), dtype=np.float32)

    def _parse_targets(self, data: bytes):
        """
        Auto-detects per-target stride.
        SDK lite  : 40 bytes  (tid + 9 floats)
        SDK full  : 112 bytes (tid + 9 floats + 16 ec floats + g + conf)
        """
        targets = []
        if len(data) == 0:
            return targets

        # Try to figure out stride: prefer 112 if it divides evenly, else 40
        if len(data) % 112 == 0 and len(data) // 112 >= 1:
            stride = 112
        elif len(data) % 40 == 0 and len(data) // 40 >= 1:
            stride = 40
        else:
            # Fall back: try both and use whichever gives a reasonable count
            stride = 40

        n = len(data) // stride
        for i in range(n):
            off = i * stride
            if off + 4 > len(data):
                break
            tid = struct.unpack_from("<I", data, off)[0]
            if off + 16 > len(data):
                break
            x, y, z = struct.unpack_from("<fff", data, off + 4)
            # Sanity: skip obviously garbage tracks
            if not (-20 < x < 20 and 0 < y < 20 and -1 < z < 5):
                continue
            targets.append({"id": tid, "x": float(x), "y": float(y), "z": float(z)})
        return targets

# ══════════════════════════════════════════════════════════════════
#  HAZARD ZONE
# ══════════════════════════════════════════════════════════════════
class HazardZone:
    def __init__(self, x0=-1.5, x1=1.5, y0=2.0, y1=5.0, z0=0.0, z1=3.0):
        self.update(x0, x1, y0, y1, z0, z1)

    def update(self, x0, x1, y0, y1, z0, z1):
        self.x0, self.x1 = x0, x1
        self.y0, self.y1 = y0, y1
        self.z0, self.z1 = z0, z1

    def contains(self, x, y, z):
        return (self.x0 <= x <= self.x1 and
                self.y0 <= y <= self.y1 and
                self.z0 <= z <= self.z1)

    def corners(self):
        c = np.array([
            [self.x0, self.y0, self.z0], [self.x1, self.y0, self.z0],
            [self.x1, self.y1, self.z0], [self.x0, self.y1, self.z0],
            [self.x0, self.y0, self.z1], [self.x1, self.y0, self.z1],
            [self.x1, self.y1, self.z1], [self.x0, self.y1, self.z1],
        ])
        return c

# ══════════════════════════════════════════════════════════════════
#  PERSON STATE
# ══════════════════════════════════════════════════════════════════
class PersonState:
    def __init__(self, tid):
        self.tid           = tid
        self.x = self.y = self.z = 0.0
        self.height        = 0.0
        self.in_hazard     = False
        self.fall          = False

    def update(self, x, y, z, points, zone: HazardZone):
        self.x, self.y, self.z = x, y, z
        # Height: Z-span of nearby raw points (within 0.7 m radius)
        if len(points) > 0:
            d2 = (points[:, 0] - x) ** 2 + (points[:, 1] - y) ** 2
            near = points[d2 < 0.49]           # 0.7² = 0.49
            if len(near) >= 2:
                self.height = float(np.max(near[:, 2]) - np.min(near[:, 2]))
            elif len(near) == 1:
                self.height = float(abs(near[0, 2]))
            else:
                self.height = float(abs(z))
        else:
            self.height = float(abs(z))

        self.in_hazard = zone.contains(x, y, z)
        self.fall      = 0.01 < self.height < FALL_THRESHOLD

# ══════════════════════════════════════════════════════════════════
#  SERIAL WORKER THREAD  —  robust connection + ACK handling
# ══════════════════════════════════════════════════════════════════
class WorkerSignals(QObject):
    log          = pyqtSignal(str, str)   # message, level
    config_ok    = pyqtSignal(bool)
    data_started = pyqtSignal()
    frame        = pyqtSignal(object)
    error        = pyqtSignal(str)        # fatal error string

class SerialWorker(QThread):
    def __init__(self, cli_port, data_port, config_text):
        super().__init__()
        self.sig         = WorkerSignals()
        self.cli_port    = cli_port
        self.data_port   = data_port
        self.config_text = config_text
        self._stop_evt   = threading.Event()
        self.parser      = RadarParser()
        self._ser_cli    = None
        self._ser_data   = None

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Probe both ports to find which one is CLI
    # ─────────────────────────────────────────────────────────────
    def _probe_cli(self, port) -> bool:
        """
        Open port, send 'sensorStop', wait up to 2 s for any text response.
        Returns True if sensor echoes anything (confirms it's the CLI port).
        Leaves self._ser_cli open on success.
        """
        self.sig.log.emit(f"  Probing {port} as CLI…", "info")
        try:
            s = serial.Serial(port, CLI_BAUD,
                              bytesize=serial.EIGHTBITS,
                              parity=serial.PARITY_NONE,
                              stopbits=serial.STOPBITS_ONE,
                              timeout=1, write_timeout=2)
            time.sleep(0.25)
            s.reset_input_buffer(); s.reset_output_buffer()
            s.write(b"sensorStop\n"); s.flush()
            t0 = time.time(); resp = b""
            while time.time() - t0 < 2.5:
                if s.in_waiting:
                    resp += s.read(s.in_waiting)
                    text = resp.decode("ascii", errors="ignore")
                    # Any readable text → this is the CLI port
                    if "Done" in text or "mmWave" in text or \
                       "sensorStop" in text or "Error" in text:
                        self.sig.log.emit(
                            f"  ✔ CLI confirmed on {port}: "
                            f"{text.strip().splitlines()[0][:60]}", "ok")
                        if self._ser_cli and self._ser_cli.is_open:
                            try: self._ser_cli.close()
                            except: pass
                        self._ser_cli = s
                        return True
                time.sleep(0.015)
            s.close()
            self.sig.log.emit(f"  ✗ No response on {port}", "dim")
            return False
        except serial.SerialException as e:
            self.sig.log.emit(f"  Cannot open {port}: {e}", "warn")
            return False

    # ─────────────────────────────────────────────────────────────
    # main run
    # ─────────────────────────────────────────────────────────────
    def run(self):
        try:
            if self.cli_port == self.data_port:
                self.sig.log.emit("⚠  CLI and Data ports must be different!", "error")
                self.sig.config_ok.emit(False)
                return

            # ── Auto-detect which port is CLI ─────────────────────
            self.sig.log.emit("━━━ Auto-detecting CLI port ━━━", "info")
            if self._probe_cli(self.cli_port):
                pass   # user assignment was correct
            elif self._probe_cli(self.data_port):
                # swap confirmed
                self.cli_port, self.data_port = self.data_port, self.cli_port
                self.sig.log.emit(
                    f"  Ports swapped → CLI={self.cli_port}  Data={self.data_port}", "warn")
            else:
                self.sig.log.emit("✘  No CLI response on either port. Checklist:", "error")
                self.sig.log.emit("  1. EVM powered? (green/blue LEDs on the board)", "warn")
                self.sig.log.emit("  2. People Tracking firmware flashed?", "warn")
                self.sig.log.emit("  3. Close TI Demo Visualizer if open (port conflict)", "warn")
                self.sig.log.emit("  4. Unplug USB → replug → click CONNECT again", "warn")
                self.sig.config_ok.emit(False)
                return

            # ── Flush any stale sensor output ────────────────────
            time.sleep(0.2)
            self._ser_cli.reset_input_buffer()

            # ── Send config ───────────────────────────────────────
            self.sig.log.emit("━━━ Sending AOP_6m People Tracking config ━━━", "info")
            if not self._send_config():
                return

            # ── Open data port ────────────────────────────────────
            self.sig.log.emit(f"Opening Data port {self.data_port} @ {DATA_BAUD}", "info")
            try:
                self._ser_data = serial.Serial(
                    self.data_port, DATA_BAUD,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.05)
                self._ser_data.reset_input_buffer()
            except serial.SerialException as e:
                self.sig.log.emit(f"Cannot open Data port: {e}", "error")
                self.sig.config_ok.emit(False)
                return

            # ── Sniff for magic word (up to 6 s) ─────────────────
            self.sig.log.emit("Waiting for radar data frames…", "info")
            sniff_buf = b""; magic_found = False; t0 = time.time()
            while time.time() - t0 < 6.0 and not self._stop_evt.is_set():
                c = self._ser_data.read(1024)
                if c:
                    sniff_buf += c
                    if MAGIC_WORD in sniff_buf:
                        magic_found = True
                        break

            if not magic_found:
                self.sig.log.emit("✘  No data frames on Data port after 6 s.", "error")
                self.sig.log.emit("   → Sensor may not have started correctly.", "warn")
                self.sig.log.emit("   → Try: STOP → power-cycle EVM → CONNECT", "warn")
                self.sig.config_ok.emit(False)
                return

            self.sig.log.emit(f"✔  Radar frames live on {self.data_port} ✓", "ok")
            self.sig.data_started.emit()

            # ── Read loop ─────────────────────────────────────────
            buf = sniff_buf; last_t = time.time()
            while not self._stop_evt.is_set():
                try:
                    c = self._ser_data.read(8192)
                except serial.SerialException as e:
                    self.sig.log.emit(f"Read error: {e}", "error"); break
                if c:
                    last_t = time.time()
                    buf += c
                    frames, buf = self.parser.parse_buffer(buf)
                    for fr in frames:
                        self.sig.frame.emit(fr)
                else:
                    if time.time() - last_t > 5.0:
                        self.sig.log.emit("⚠  No frames for 5 s — sensor may have stopped", "warn")
                        last_t = time.time()

        except Exception as exc:
            self.sig.log.emit(f"Unexpected error: {exc}", "error")
            self.sig.config_ok.emit(False)
        finally:
            self._close()

    # ─────────────────────────────────────────────────────────────
    # Config sender — one line at a time, tolerant ACK reading
    # ─────────────────────────────────────────────────────────────
    def _send_config(self):
        lines = [l.strip() for l in self.config_text.splitlines()
                 if l.strip() and not l.strip().startswith("%")]
        total = len(lines)
        for i, line in enumerate(lines):
            if self._stop_evt.is_set():
                return False
            try:
                self._ser_cli.write((line + "\n").encode("ascii"))
                self._ser_cli.flush()
            except serial.SerialException as e:
                self.sig.log.emit(f"Write error on '{line}': {e}", "error")
                self.sig.config_ok.emit(False)
                return False

            self.sig.log.emit(f"  [{i+1:02d}/{total}] TX ▶  {line}", "tx")
            ack = self._read_ack(timeout=4.0)
            clean = ack.replace("\r", " ").replace("\n", " ").strip()

            if "Done" in ack:
                self.sig.log.emit(f"         ◀ Done ✓", "ok")
            elif clean:
                self.sig.log.emit(f"         ◀ {clean[:90]}", "dim")
            else:
                self.sig.log.emit(f"         ◀ (timeout — ok)", "dim")

            time.sleep(0.06)

        self.sig.log.emit(f"━━━ Config sent ({total} commands) ✓ ━━━", "ok")
        self.sig.config_ok.emit(True)
        return True

    def _read_ack(self, timeout=4.0):
        """Read CLI response until 'Done'/'Error'/timeout."""
        deadline = time.time() + timeout
        buf = ""
        while time.time() < deadline:
            if self._stop_evt.is_set():
                break
            if self._ser_cli.in_waiting:
                buf += self._ser_cli.read(
                    self._ser_cli.in_waiting).decode("ascii", errors="ignore")
                if "Done" in buf or "done" in buf:
                    break
                if "not recognized" in buf.lower():
                    break
            else:
                time.sleep(0.01)
        return buf

    def stop(self):
        self._stop_evt.set()
        self.wait(3000)

    def _close(self):
        for s, name in [(self._ser_cli, "CLI"), (self._ser_data, "Data")]:
            try:
                if s and s.is_open:
                    if name == "CLI":
                        try: s.write(b"sensorStop\n"); s.flush(); time.sleep(0.15)
                        except: pass
                    s.close()
                    self.sig.log.emit(f"{name} port closed.", "dim")
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════
#  MATPLOTLIB 3-D CANVAS
# ══════════════════════════════════════════════════════════════════
class Radar3DCanvas(FigureCanvas):
    """Embedded 3-D scatter view with room box + hazard zone."""

    def __init__(self, zone: HazardZone, parent=None):
        self.fig = Figure(facecolor="#0b0e0b", tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.zone = zone

        self.ax = self.fig.add_subplot(111, projection="3d")
        self._style_axes()

        self._pt_scat  = None
        self._tk_scat  = None
        self._hz_mesh  = None
        self._room_lines = []
        self._draw_room()
        self._draw_hazard_zone()

        self.setMinimumHeight(440)

    # ── axes style ────────────────────────────────────────────────
    def _style_axes(self):
        ax = self.ax
        ax.set_facecolor("#0b0e0b")
        ax.tick_params(colors="#1f6b10", labelsize=7)
        for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            pane.fill = False
            pane.set_edgecolor("#14201a")
        for spine in ax.spines.values():
            spine.set_edgecolor("#14201a")
        ax.xaxis.label.set_color("#39ff14")
        ax.yaxis.label.set_color("#39ff14")
        ax.zaxis.label.set_color("#39ff14")
        ax.set_xlabel("X (m)", fontsize=8, labelpad=4)
        ax.set_ylabel("Y (m)", fontsize=8, labelpad=4)
        ax.set_zlabel("Z (m)", fontsize=8, labelpad=4)
        ax.set_xlim(-4, 4)
        ax.set_ylim(0, 6)
        ax.set_zlim(0, 3)
        ax.set_title("RADAR FIELD  —  IWR6843AOP EVM  (6 m range)",
                     color="#39ff14", fontsize=9, pad=8,
                     fontfamily="monospace")

    # ── room wireframe ────────────────────────────────────────────
    def _draw_room(self):
        for l in self._room_lines:
            l.remove()
        self._room_lines = []
        rx = (-4, 4); ry = (0, 6); rz = (0, 3)
        def edge(p1, p2):
            xs = [p1[0], p2[0]]; ys = [p1[1], p2[1]]; zs = [p1[2], p2[2]]
            ln, = self.ax.plot(xs, ys, zs, color="#14451a", lw=0.8, alpha=0.6)
            self._room_lines.append(ln)

        corners = [
            (rx[0],ry[0],rz[0]), (rx[1],ry[0],rz[0]),
            (rx[1],ry[1],rz[0]), (rx[0],ry[1],rz[0]),
            (rx[0],ry[0],rz[1]), (rx[1],ry[0],rz[1]),
            (rx[1],ry[1],rz[1]), (rx[0],ry[1],rz[1]),
        ]
        edges_idx = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                     (0,4),(1,5),(2,6),(3,7)]
        for a, b in edges_idx:
            edge(corners[a], corners[b])

    # ── hazard zone ───────────────────────────────────────────────
    def _draw_hazard_zone(self):
        if self._hz_mesh:
            try:
                self._hz_mesh.remove()
            except Exception:
                pass
        c = self.zone.corners()
        faces = [
            [c[0],c[1],c[2],c[3]],   # bottom
            [c[4],c[5],c[6],c[7]],   # top
            [c[0],c[1],c[5],c[4]],   # front
            [c[2],c[3],c[7],c[6]],   # back
            [c[0],c[3],c[7],c[4]],   # left
            [c[1],c[2],c[6],c[5]],   # right
        ]
        poly = Poly3DCollection(faces, alpha=0.08,
                                facecolor="#ff2020", edgecolor="#ff4040",
                                linewidth=1.2, linestyle="--")
        self._hz_mesh = self.ax.add_collection3d(poly)

        # label
        cx = (self.zone.x0 + self.zone.x1) / 2
        cy = (self.zone.y0 + self.zone.y1) / 2
        cz = self.zone.z1 + 0.15
        self.ax.text(cx, cy, cz, "⚠ HAZARD", color="#ff4040",
                     fontsize=7, fontfamily="monospace", ha="center")

    # ── public update ─────────────────────────────────────────────
    def update_scene(self, points: np.ndarray, targets: list, persons: dict):
        ax = self.ax

        # Remove old scatters
        if self._pt_scat:
            self._pt_scat.remove(); self._pt_scat = None
        if self._tk_scat:
            self._tk_scat.remove(); self._tk_scat = None

        # Point cloud — colour by height
        if len(points) > 0:
            xs, ys, zs = points[:,0], points[:,1], points[:,2]
            z_norm = np.clip(zs / 3.0, 0, 1)
            colors = np.zeros((len(points), 4))
            colors[:,0] = 0.0
            colors[:,1] = 0.3 + z_norm * 0.7
            colors[:,2] = 0.0
            colors[:,3] = 0.6
            self._pt_scat = ax.scatter(xs, ys, zs, c=colors, s=8, depthshade=False)

        # Track centroids
        if targets:
            txs = [t["x"] for t in targets]
            tys = [t["y"] for t in targets]
            tzs = [t["z"] for t in targets]
            tcs = []
            for t in targets:
                p = persons.get(t["id"])
                if p and p.in_hazard:
                    tcs.append("#ff2020")
                elif p and p.fall:
                    tcs.append("#ffb300")
                else:
                    tcs.append("#39ff14")
            self._tk_scat = ax.scatter(txs, tys, tzs, c=tcs, s=90,
                                       marker="^", depthshade=False, zorder=5)

        self.draw_idle()

    def refresh_hazard_zone(self):
        self._draw_hazard_zone()
        self._draw_room()
        self.draw_idle()


# ══════════════════════════════════════════════════════════════════
#  STYLED WIDGET HELPERS
# ══════════════════════════════════════════════════════════════════
def mk_label(text, size=11, bold=False, color=WHITE_TEXT, mono=False):
    l = QLabel(text)
    ff = "Courier New, monospace" if mono else "Arial"
    w  = "700" if bold else "400"
    l.setStyleSheet(f"color:{color};font-size:{size}px;font-weight:{w};font-family:{ff};")
    return l

def mk_divider():
    d = QFrame(); d.setFrameShape(QFrame.HLine)
    d.setStyleSheet(f"color:{BORDER}; background:{BORDER};"); d.setFixedHeight(1)
    return d

class StatCard(QFrame):
    def __init__(self, title, value="—", unit="", accent=PHOSPHOR):
        super().__init__()
        self.accent = accent
        self.setStyleSheet(f"""
            QFrame {{
                background:{PANEL};
                border:1px solid {BORDER};
                border-left:3px solid {accent};
                border-radius:4px;
            }}
        """)
        v = QVBoxLayout(self); v.setContentsMargins(10,8,10,8); v.setSpacing(1)
        self._title = QLabel(title.upper())
        self._title.setStyleSheet(f"color:{SUBTEXT};font-size:9px;letter-spacing:2px;font-family:Courier New;")
        self._val   = QLabel(value)
        self._val.setStyleSheet(f"color:{accent};font-size:20px;font-weight:700;font-family:Courier New;")
        self._unit  = QLabel(unit)
        self._unit.setStyleSheet(f"color:{SUBTEXT};font-size:9px;font-family:Courier New;")
        v.addWidget(self._title)
        v.addWidget(self._val)
        v.addWidget(self._unit)

    def set_value(self, v):
        self._val.setText(str(v))

class AlertBanner(QFrame):
    def __init__(self, icon, text, color=RED_ALERT):
        super().__init__()
        self.color  = color
        self.active = False
        self.setFixedHeight(38)
        lay = QHBoxLayout(self); lay.setContentsMargins(12,4,12,4); lay.setSpacing(8)
        self._icon = QLabel(icon)
        self._icon.setStyleSheet(f"font-size:16px;")
        self._lbl  = QLabel(text)
        self._lbl.setStyleSheet(f"font-size:11px;font-weight:700;font-family:Courier New;letter-spacing:1px;")
        self._dot  = QLabel("●")
        self._dot.setStyleSheet(f"font-size:10px;")
        lay.addWidget(self._dot); lay.addWidget(self._icon); lay.addWidget(self._lbl)
        lay.addStretch()
        self._off()

    def _off(self):
        self.setStyleSheet(f"QFrame{{background:{PANEL};border:1px solid {BORDER};border-radius:4px;}}")
        self._lbl.setStyleSheet(f"color:{SUBTEXT};font-size:11px;font-weight:700;font-family:Courier New;letter-spacing:1px;")
        self._dot.setStyleSheet(f"color:{SUBTEXT};font-size:10px;")
        self._icon.setStyleSheet(f"color:{SUBTEXT};font-size:16px;")

    def _on(self):
        self.setStyleSheet(f"QFrame{{background:{self.color}18;border:1px solid {self.color};border-radius:4px;}}")
        self._lbl.setStyleSheet(f"color:{self.color};font-size:11px;font-weight:700;font-family:Courier New;letter-spacing:1px;")
        self._dot.setStyleSheet(f"color:{self.color};font-size:10px;")
        self._icon.setStyleSheet(f"color:{self.color};font-size:16px;")

    def set_active(self, state: bool):
        if state != self.active:
            self.active = state
            self._on() if state else self._off()


# ══════════════════════════════════════════════════════════════════
#  PERSON ROW WIDGET
# ══════════════════════════════════════════════════════════════════
class PersonRow(QFrame):
    def __init__(self, person: PersonState):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._build(person)

    def _build(self, p: PersonState):
        # pick border colour
        bc = RED_ALERT if p.in_hazard else (AMBER if p.fall else BORDER)
        self.setStyleSheet(f"""
            QFrame {{
                background:{PANEL};
                border:1px solid {bc};
                border-left:3px solid {bc};
                border-radius:3px;
            }}
        """)
        row = QHBoxLayout(self); row.setContentsMargins(8,5,8,5); row.setSpacing(14)

        def field(label, val, col=WHITE_TEXT):
            w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
            lbl = QLabel(label); lbl.setStyleSheet(f"color:{SUBTEXT};font-size:8px;font-family:Courier New;letter-spacing:1px;")
            vl  = QLabel(val);   vl.setStyleSheet(f"color:{col};font-size:12px;font-weight:700;font-family:Courier New;")
            lay.addWidget(lbl); lay.addWidget(vl)
            return w

        row.addWidget(field("ID", f"#{p.tid:02d}", PHOSPHOR))
        row.addWidget(field("HEIGHT", f"{p.height:.2f} m",
                            AMBER if p.fall else WHITE_TEXT))
        row.addWidget(field("X", f"{p.x:+.2f}"))
        row.addWidget(field("Y", f"{p.y:.2f}"))
        row.addWidget(field("Z", f"{p.z:.2f}"))

        flags = []
        if p.in_hazard:    flags.append(("⚠ HAZARD", RED_ALERT))
        if p.fall:         flags.append(("⚡ FALL",   AMBER))

        for txt, col in flags:
            fl = QLabel(txt)
            fl.setStyleSheet(f"color:{col};font-size:9px;font-weight:700;font-family:Courier New;"
                             f"background:{col}18;border:1px solid {col};border-radius:3px;padding:1px 5px;")
            row.addWidget(fl)
        row.addStretch()


# ══════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════
GLOBAL_SS = f"""
QMainWindow, QWidget {{
    background: {BG};
    color: {WHITE_TEXT};
    font-family: Arial, sans-serif;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 6px;
    color: {SUBTEXT};
    font-size: 9px;
    letter-spacing: 2px;
    font-family: Courier New;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    top: 0px;
}}
QComboBox, QDoubleSpinBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    color: {PHOSPHOR};
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 11px;
    font-family: Courier New;
    min-height: 22px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    color: {PHOSPHOR};
    border: 1px solid {BORDER};
    selection-background-color: {BORDER};
}}
QPushButton {{
    background: {BORDER};
    border: none;
    color: {WHITE_TEXT};
    padding: 7px 16px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 700;
    font-family: Courier New;
    letter-spacing: 1px;
}}
QPushButton:hover {{ background: #253525; }}
QPushButton:disabled {{ color: {SUBTEXT}; }}
QPushButton#btn_connect {{
    background: {PHOSPHOR};
    color: #000;
    border: none;
}}
QPushButton#btn_connect:hover {{ background: #55ff33; }}
QPushButton#btn_stop {{
    background: {RED_ALERT};
    color: #fff;
}}
QPushButton#btn_stop:hover {{ background: #cc0000; }}
QTextEdit {{
    background: #050805;
    border: 1px solid {BORDER};
    color: {DIM_GREEN};
    font-family: Courier New;
    font-size: 10px;
    border-radius: 3px;
}}
QScrollBar:vertical {{
    background: {PANEL}; width: 7px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER}; border-radius: 4px;
}}
QTabBar::tab {{
    background: {PANEL}; color: {SUBTEXT};
    padding: 6px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-family: Courier New;
    font-size: 10px;
    letter-spacing: 1px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {BORDER};
    color: {PHOSPHOR};
}}
QSplitter::handle {{
    background: {BORDER};
}}
"""

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RADAR IMS  ·  IWR6843AOP EVM  ·  Industrial Monitoring")
        self.setMinimumSize(1360, 820)
        self.setStyleSheet(GLOBAL_SS)

        self.zone    = HazardZone()
        self.persons = {}        # tid → PersonState
        self.worker  = None
        self._frame_ts = deque(maxlen=60)

        self._build_ui()

        # Auto-populate ports after the window is fully constructed
        QTimer.singleShot(100, self._on_refresh_ports)
        QTimer.singleShot(200, self._load_initial_config)

    def _load_initial_config(self):
        if os.path.exists(DEFAULT_CFG_PATH):
            try:
                with open(DEFAULT_CFG_PATH, "r") as f:
                    cfg = f.read()
                    self.cfg_editor.setPlainText(cfg.strip())
                    self._log(f"Loaded config from {os.path.basename(DEFAULT_CFG_PATH)}", "ok")
            except Exception as e:
                self._log(f"Error loading {os.path.basename(DEFAULT_CFG_PATH)}: {e}", "error")
        else:
            self._log(f"Config file not found: {os.path.basename(DEFAULT_CFG_PATH)}", "warn")

    # ── UI ────────────────────────────────────────────────────────
    def _build_ui(self):
        root_w = QWidget(); self.setCentralWidget(root_w)
        root   = QHBoxLayout(root_w)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ════════════ LEFT PANEL ════════════
        left = QWidget(); left.setFixedWidth(310)
        ll   = QVBoxLayout(left); ll.setSpacing(8); ll.setContentsMargins(0,0,0,0)

        # Header
        hdr = QLabel("◈  RADAR  IMS")
        hdr.setStyleSheet(f"color:{PHOSPHOR};font-size:20px;font-weight:700;"
                          f"font-family:Courier New;letter-spacing:4px;")
        sub = QLabel("INDUSTRIAL MONITORING SYSTEM")
        sub.setStyleSheet(f"color:{SUBTEXT};font-size:8px;font-family:Courier New;letter-spacing:3px;")
        sub2= QLabel("IWR6843AOP EVM  ·  60 GHz mmWave")
        sub2.setStyleSheet(f"color:{DIM_GREEN};font-size:9px;font-family:Courier New;")
        ll.addWidget(hdr); ll.addWidget(sub); ll.addWidget(sub2)
        ll.addWidget(mk_divider())

        # Connection
        conn = QGroupBox("CONNECTION"); cg = QGridLayout(conn); cg.setSpacing(5)
        cg.addWidget(mk_label("CLI Port", 10, color=SUBTEXT, mono=True), 0, 0)
        self.cmb_cli = QComboBox()
        self.cmb_cli.setMinimumWidth(160)
        cg.addWidget(self.cmb_cli, 0, 1)

        cg.addWidget(mk_label("Data Port", 10, color=SUBTEXT, mono=True), 1, 0)
        self.cmb_data = QComboBox()
        self.cmb_data.setMinimumWidth(160)
        cg.addWidget(self.cmb_data, 1, 1)

        btn_refresh = QPushButton("⟳ REFRESH PORTS")
        btn_refresh.clicked.connect(self._on_refresh_ports)
        cg.addWidget(btn_refresh, 2, 0, 1, 2)

        self.btn_connect = QPushButton("▶  CONNECT"); self.btn_connect.setObjectName("btn_connect")
        self.btn_connect.clicked.connect(self._on_toggle_connection)
        cg.addWidget(self.btn_connect, 3, 0, 1, 2)

        ll.addWidget(conn)

        # Status indicator
        self.lbl_status = QLabel("⬤  OFFLINE")
        self.lbl_status.setStyleSheet(f"color:{SUBTEXT};font-size:12px;font-weight:700;font-family:Courier New;")
        ll.addWidget(self.lbl_status)
        ll.addWidget(mk_divider())

        # Stats grid
        stats = QGroupBox("LIVE STATISTICS"); sg = QGridLayout(stats); sg.setSpacing(6)
        self.card_count = StatCard("People", "0",   "detected",  PHOSPHOR)
        self.card_fps   = StatCard("Frame Rate", "0", "Hz",      CYAN_INFO)
        self.card_pts   = StatCard("Points", "0",   "in cloud",  DIM_GREEN)
        self.card_trk   = StatCard("Tracks", "0",   "active",    AMBER)
        sg.addWidget(self.card_count, 0, 0); sg.addWidget(self.card_fps,  0, 1)
        sg.addWidget(self.card_pts,   1, 0); sg.addWidget(self.card_trk,  1, 1)
        ll.addWidget(stats)

        # Alerts
        alrt_grp = QGroupBox("SYSTEM ALERTS"); ag = QVBoxLayout(alrt_grp); ag.setSpacing(5)
        self.alert_hazard = AlertBanner("⚠", "HAZARD ZONE INTRUSION", RED_ALERT)
        self.alert_fall   = AlertBanner("⚡", "FALL DETECTED",          AMBER)
        ag.addWidget(self.alert_hazard); ag.addWidget(self.alert_fall)
        ll.addWidget(alrt_grp)

        # Person list
        ppl_grp = QGroupBox("DETECTED PERSONS")
        pg_lay  = QVBoxLayout(ppl_grp); pg_lay.setContentsMargins(4,4,4,4)
        scroll  = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFixedHeight(160)
        self._person_container = QWidget()
        self._person_layout    = QVBoxLayout(self._person_container)
        self._person_layout.setSpacing(3); self._person_layout.setContentsMargins(0,0,0,0)
        self._person_layout.addStretch()
        scroll.setWidget(self._person_container)
        pg_lay.addWidget(scroll)
        ll.addWidget(ppl_grp)

        # Hazard zone config
        hz_grp = QGroupBox("HAZARD ZONE  (metres)"); hzg = QGridLayout(hz_grp); hzg.setSpacing(4)
        self._hz_spins = []
        fields = [("X MIN",-1.5),("X MAX",1.5),("Y MIN",2.0),("Y MAX",5.0),("Z MIN",0.0),("Z MAX",3.0)]
        for i, (lbl_t, val) in enumerate(fields):
            r, c_off = i//2, (i%2)*2
            hzg.addWidget(mk_label(lbl_t, 9, color=SUBTEXT, mono=True), r, c_off)
            sp = QDoubleSpinBox(); sp.setRange(-20,20); sp.setValue(val); sp.setSingleStep(0.5)
            sp.setDecimals(1)
            hzg.addWidget(sp, r, c_off+1)
            self._hz_spins.append(sp)
        btn_hz = QPushButton("APPLY ZONE")
        btn_hz.clicked.connect(self._apply_zone)
        hzg.addWidget(btn_hz, 3, 0, 1, 4)
        ll.addWidget(hz_grp)

        ll.addStretch()

        # ════════════ RIGHT PANEL ════════════
        right = QWidget()
        rl    = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(6)

        tabs = QTabWidget()

        # Tab 1 — 3D view
        tab3d = QWidget(); t3l = QVBoxLayout(tab3d); t3l.setContentsMargins(4,4,4,4)
        self.canvas3d = Radar3DCanvas(self.zone, tab3d)
        t3l.addWidget(self.canvas3d)
        tabs.addTab(tab3d, "  3D RADAR VIEW  ")

        # Tab 2 — CLI console
        tab_cli = QWidget(); tcl = QVBoxLayout(tab_cli); tcl.setContentsMargins(6,6,6,6)
        tcl.addWidget(mk_label("CLI  /  SERIAL CONSOLE", 10, bold=True, color=PHOSPHOR, mono=True))
        tcl.addWidget(mk_label(
            f"AOP_6m_default (People Tracking)  ·  CLI @ {CLI_BAUD}  ·  Data @ {DATA_BAUD} baud  "
            f"·  Lower COM# = CLI,  Higher COM# = Data",
            9, color=SUBTEXT, mono=True))
        self.cli_log = QTextEdit(); self.cli_log.setReadOnly(True)
        tcl.addWidget(self.cli_log)
        tabs.addTab(tab_cli, "  CLI CONSOLE  ")

        # Tab 3 — Config editor
        tab_cfg = QWidget(); tfl = QVBoxLayout(tab_cfg); tfl.setContentsMargins(6,6,6,6)
        tfl.addWidget(mk_label("ACTIVE CONFIGURATION SCRIPT", 10, bold=True, color=PHOSPHOR, mono=True))
        self.cfg_editor = QTextEdit()
        tfl.addWidget(self.cfg_editor)
        tabs.addTab(tab_cfg, "  CONFIG SCRIPT  ")

        rl.addWidget(tabs)

        # Root layout
        root.addWidget(left)
        root.addWidget(right, stretch=1)

    # ── port helpers ──────────────────────────────────────────────
    def _get_sorted_ports(self):
        """Return ports sorted numerically by COM number."""
        ports = list(serial.tools.list_ports.comports())
        def port_num(p):
            import re
            m = re.search(r'\d+', p.device)
            return int(m.group()) if m else 0
        return sorted(ports, key=port_num)

    def _fill_ports(self, combo):
        combo.clear()
        ports = self._get_sorted_ports()
        for p in ports:
            desc = p.description or p.device
            # shorten long XDS110 descriptions
            if "XDS110" in desc:
                if "App" in desc or "User" in desc:
                    desc = f"{p.device}  [XDS110 CLI]"
                elif "Auxiliary" in desc or "Data" in desc:
                    desc = f"{p.device}  [XDS110 Data]"
                else:
                    desc = f"{p.device}  [{desc[:20]}]"
            else:
                desc = f"{p.device}  [{desc[:25]}]"
            combo.addItem(desc, userData=p.device)
        if not ports:
            combo.addItem("(none found)", userData="")

    def _on_refresh_ports(self):
        """Refresh both dropdowns and auto-assign CLI=lower, Data=higher."""
        self._fill_ports(self.cmb_cli)
        self._fill_ports(self.cmb_data)

        ports = self._get_sorted_ports()
        if len(ports) >= 2:
            # Auto-select: lower COM# → CLI, higher COM# → Data
            self.cmb_cli.setCurrentIndex(0)
            self.cmb_data.setCurrentIndex(len(ports) - 1)

            cli_dev  = self.cmb_cli.currentData()  or self.cmb_cli.currentText().split()[0]
            data_dev = self.cmb_data.currentData() or self.cmb_data.currentText().split()[0]
            self._log(f"Auto-assigned → CLI: {cli_dev}   Data: {data_dev}", "ok")
            self._log("  (Lower COM# = CLI,  Higher COM# = Data — for IWR6843AOP EVM)", "dim")
        elif len(ports) == 1:
            self._log("⚠  Only 1 COM port found — EVM may not be connected or drivers missing", "warn")
        else:
            self._log("✘  No COM ports found — check USB cable and XDS110 drivers", "error")

    # ── connect / stop ────────────────────────────────────────────
    def _on_toggle_connection(self):
        if self.worker and self.worker.isRunning():
            self._on_stop()
        else:
            self._on_connect()

    def _on_connect(self):
        # currentData() holds the raw device path (e.g. "COM5")
        # currentText() holds the display string (e.g. "COM5  [XDS110 CLI]")
        cp  = self.cmb_cli.currentData()  or self.cmb_cli.currentText().split()[0]
        dp  = self.cmb_data.currentData() or self.cmb_data.currentText().split()[0]
        cfg = self.cfg_editor.toPlainText()

        if not cp or "none" in cp.lower():
            self._log("No CLI port selected — click ⟳ REFRESH PORTS first.", "error")
            return
        if not dp or "none" in dp.lower():
            self._log("No Data port selected — click ⟳ REFRESH PORTS first.", "error")
            return

        if cp == dp:
            self._log("⚠  CLI and Data ports are the SAME PORT — they must be different!", "error")
            self._log("    IWR6843AOP EVM creates 2 COM ports over one USB cable.", "warn")
            self._log("    Lower COM# → CLI port   |   Higher COM# → Data port", "warn")
            self._log("    Open Device Manager → Ports (COM & LPT) to check.", "warn")
            return

        self.btn_connect.setText("■  DISCONNECT")
        self.btn_connect.setStyleSheet(f"background: {RED_ALERT}; color: #fff;")
        self._set_status("CONNECTING…", AMBER)
        self._log(f"━━━ Connecting:  CLI={cp}   Data={dp} ━━━", "info")
        self._log("  (Code will auto-swap ports if no data detected)", "dim")

        self.worker = SerialWorker(cp, dp, cfg)
        self.worker.sig.log.connect(self._log)
        self.worker.sig.config_ok.connect(self._on_config_ok)
        self.worker.sig.data_started.connect(self._on_data_started)
        self.worker.sig.frame.connect(self._on_frame)
        self.worker.start()

    def _on_stop(self):
        if self.worker:
            self.worker.stop(); self.worker = None
        self.btn_connect.setText("▶  CONNECT")
        self.btn_connect.setStyleSheet(GLOBAL_SS) # Reset to default style from GLOBAL_SS
        # But wait, GLOBAL_SS has QPushButton#btn_connect style which is green.
        # Let's just force the background again to be sure or rely on objectName.
        self.btn_connect.setStyleSheet("") # Clearing local stylesheet should revert to GLOBAL_SS style
        self._set_status("OFFLINE", SUBTEXT)
        self._log("Sensor stopped.", "info")

    # ── signal callbacks ──────────────────────────────────────────
    def _on_config_ok(self, ok):
        if not ok:
            self._set_status("CONFIG ERR", RED_ALERT)
            self._log("━━━ Connection failed. Check ports and retry. ━━━", "error")
            self._log("  1. Confirm lower COM# = CLI port, higher COM# = Data port", "warn")
            self._log("  2. Close TI mmWave Demo Visualizer if open (port conflict)", "warn")
            self._log("  3. Power-cycle the EVM, then click CONNECT again", "warn")
            self.btn_connect.setText("▶  CONNECT")
            self.btn_connect.setStyleSheet("")

    def _on_data_started(self):
        self._set_status("LIVE", PHOSPHOR)

    def _on_frame(self, frame: RadarFrame):
        now = time.time()
        self._frame_ts.append(now)
        fps = len([t for t in self._frame_ts if now - t < 2.0]) / 2.0

        pts = frame.points
        # Update/create person states
        active_ids = set()
        for t in frame.targets:
            tid = t["id"]; active_ids.add(tid)
            if tid not in self.persons:
                self.persons[tid] = PersonState(tid)
            self.persons[tid].update(t["x"], t["y"], t["z"], pts, self.zone)
        # Remove stale
        for gone in set(self.persons) - active_ids:
            del self.persons[gone]

        # Alerts
        any_hazard = any(p.in_hazard for p in self.persons.values())
        any_fall   = any(p.fall      for p in self.persons.values())
        self.alert_hazard.set_active(any_hazard)
        self.alert_fall.set_active(any_fall)

        # Stat cards
        self.card_count.set_value(len(self.persons))
        self.card_fps.set_value(f"{fps:.1f}")
        self.card_pts.set_value(len(pts))
        self.card_trk.set_value(len(frame.targets))

        # Person list
        self._refresh_person_panel()

        # 3D
        self.canvas3d.update_scene(pts, frame.targets, self.persons)

    def _refresh_person_panel(self):
        layout = self._person_layout
        # remove all but stretch
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for p in sorted(self.persons.values(), key=lambda x: x.tid):
            layout.insertWidget(layout.count()-1, PersonRow(p))

    def _apply_zone(self):
        v = [s.value() for s in self._hz_spins]
        self.zone.update(*v)
        self.canvas3d.zone = self.zone
        self.canvas3d.refresh_hazard_zone()
        self._log(f"Hazard zone updated → X[{v[0]:.1f},{v[1]:.1f}] Y[{v[2]:.1f},{v[3]:.1f}] Z[{v[4]:.1f},{v[5]:.1f}]","info")

    # ── log ───────────────────────────────────────────────────────
    def _log(self, msg, level="info"):
        col_map = {"info": CYAN_INFO, "ok": PHOSPHOR, "error": RED_ALERT,
                   "tx": AMBER, "dim": SUBTEXT, "warn": AMBER}
        col = col_map.get(level, WHITE_TEXT)
        ts  = time.strftime("%H:%M:%S")
        self.cli_log.append(
            f'<span style="color:{SUBTEXT}">[{ts}]</span>'
            f' <span style="color:{col}">{msg}</span>'
        )
        sb = self.cli_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_status(self, text, color):
        self.lbl_status.setText(f"⬤  {text}")
        self.lbl_status.setStyleSheet(
            f"color:{color};font-size:12px;font-weight:700;font-family:Courier New;")

    def closeEvent(self, ev):
        self._on_stop(); super().closeEvent(ev)


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()