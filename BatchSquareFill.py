"""
BatchSquareFill.py  –  Batch Square Fill Processor
Aufruf:  uv run BatchSquareFill.py  /  python BatchSquareFill.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QColor, QPalette, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QScrollArea, QProgressBar,
    QFileDialog, QFrame,
)

JPEG_QUALITY     = 92
JPEG_SUBSAMPLING = 0
JPEG_OPTIMIZE    = True

SCRIPT_DIR = Path(sys.argv[0]).resolve().parent

# ── Palette (Apple dark mode) ────────────────────────────────────────
_BG     = "#1c1c1e"
_SURF   = "#2c2c2e"
_SURF2  = "#3a3a3c"
_SURF3  = "#48484a"
_TEXT   = "#e5e5e7"
_TEXT2  = "#8e8e93"
_ACCENT = "#FFD60A"
_RED    = "#FF453A"
_BLUE   = "#0A84FF"


# ── Image processing (pure Pillow, no GUI) ──────────────────────────
def _apply_watermark(
    canvas: Image.Image,
    wm_img: Image.Image,
    size_pct: int,
    x_pct: int,
    y_pct: int,
    strength: int,
    mode: str,          # "lighten" | "desat" | "both"
) -> None:
    wm_w = max(1, round(canvas.width * size_pct / 100))
    wm_h = max(1, round(wm_img.height * wm_w / wm_img.width))
    wm   = wm_img.resize((wm_w, wm_h), Image.LANCZOS)
    alpha = wm.split()[3]   # logo shape as an L-mode mask

    x = round((canvas.width  - wm_w) * x_pct / 100)
    y = round((canvas.height - wm_h) * y_pct / 100)

    region = canvas.crop((x, y, x + wm_w, y + wm_h)).convert("RGB")
    s = strength / 100

    if mode == "lighten":
        white    = Image.new("RGB", region.size, (255, 255, 255))
        modified = Image.blend(region, white, s)
    elif mode == "desat":
        gray     = ImageOps.grayscale(region).convert("RGB")
        modified = Image.blend(region, gray, s)
    else:  # "both" – desaturate then brighten toward light-gray
        gray       = ImageOps.grayscale(region).convert("RGB")
        white      = Image.new("RGB", region.size, (255, 255, 255))
        light_gray = Image.blend(gray, white, s * 0.5)
        modified   = Image.blend(region, light_gray, s)

    # Paste modified region back, using logo alpha as per-pixel blend weight
    canvas.paste(modified, (x, y), mask=alpha)


def _make_square(
    img: Image.Image,
    side: int,
    blur_px: int,
    wm_img: "Image.Image | None" = None,
    wm_size_pct: int = 35,
    wm_x_pct: int    = 50,
    wm_y_pct: int    = 98,
    wm_strength: int = 90,
    wm_mode: str     = "both",
) -> Image.Image:
    w, h = img.size
    scale = side / max(w, h)
    fg = img.resize((round(w * scale), round(h * scale)), Image.BICUBIC)

    scale_bg = side / min(w, h)
    bg_w, bg_h = round(w * scale_bg), round(h * scale_bg)
    bg = img.resize((bg_w, bg_h), Image.BICUBIC)
    left, top = (bg_w - side) // 2, (bg_h - side) // 2
    bg = bg.crop((left, top, left + side, top + side))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_px))

    canvas = bg.copy()
    canvas.paste(fg, ((side - fg.width) // 2, (side - fg.height) // 2))

    if wm_img is not None:
        _apply_watermark(canvas, wm_img, wm_size_pct, wm_x_pct, wm_y_pct, wm_strength, wm_mode)

    return canvas


def process_image(
    src: Path,
    side: int,
    blur_pct: int,
    side_pct: bool = False,
    wm_img: "Image.Image | None" = None,
    wm_size_pct: int = 35,
    wm_x_pct: int    = 50,
    wm_y_pct: int    = 98,
    wm_strength: int = 90,
    wm_mode: str     = "both",
) -> None:
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if side_pct:
        side = round(max(img.size) * side / 100)
    canvas = _make_square(
        img, side, round(side * blur_pct / 100),
        wm_img, wm_size_pct, wm_x_pct, wm_y_pct, wm_strength, wm_mode,
    )

    out_dir = src.parent / "out"
    out_dir.mkdir(exist_ok=True)
    canvas.save(
        out_dir / f"{src.stem}_square.jpg",
        format="JPEG",
        quality=JPEG_QUALITY,
        subsampling=JPEG_SUBSAMPLING,
        optimize=JPEG_OPTIMIZE,
    )


# ── Worker thread ────────────────────────────────────────────────────
class Worker(QThread):
    progress = Signal(int, int, str)
    error    = Signal(str, str)
    done     = Signal(int)

    def __init__(
        self,
        files: list,
        side: int,
        blur: int,
        side_pct: bool = False,
        wm_img: "Image.Image | None" = None,
        wm_size_pct: int = 35,
        wm_x_pct: int    = 50,
        wm_y_pct: int    = 98,
        wm_strength: int = 90,
        wm_mode: str     = "both",
    ):
        super().__init__()
        self.files       = files
        self.side        = side
        self.blur        = blur
        self.side_pct    = side_pct
        self.wm_img      = wm_img
        self.wm_size_pct = wm_size_pct
        self.wm_x_pct    = wm_x_pct
        self.wm_y_pct    = wm_y_pct
        self.wm_strength = wm_strength
        self.wm_mode     = wm_mode

    def run(self):
        n = len(self.files)
        for i, f in enumerate(self.files):
            self.progress.emit(i, n, f.name)
            try:
                process_image(
                    f, self.side, self.blur, self.side_pct,
                    self.wm_img, self.wm_size_pct, self.wm_x_pct,
                    self.wm_y_pct, self.wm_strength, self.wm_mode,
                )
            except Exception as e:
                self.error.emit(f.name, str(e))
        self.done.emit(n)


# ── Drop zone ────────────────────────────────────────────────────────
class DropZone(QFrame):
    files_dropped = Signal(list)
    add_clicked   = Signal()

    _CSS_IDLE = f"""
        DropZone {{
            background: rgba(255,255,255,0.04);
            border: 1.5px dashed rgba(255,255,255,0.2);
            border-radius: 12px;
        }}
    """
    _CSS_DRAG = f"""
        DropZone {{
            background: rgba(255,214,10,0.08);
            border: 1.5px dashed #FFD60A;
            border-radius: 12px;
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(72)
        self.setStyleSheet(self._CSS_IDLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)

        icon = QLabel("⊕")
        icon.setStyleSheet(f"color: {_TEXT2}; font-size: 20px; border: none; background: transparent;")
        text = QLabel("Drop JPEG images or folders here  ·  or click  ＋ Add")
        text.setStyleSheet(f"color: {_TEXT2}; font-size: 13px; border: none; background: transparent;")
        lay.addWidget(icon)
        lay.addWidget(text)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._CSS_DRAG)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._CSS_IDLE)

    def dropEvent(self, event):
        self.setStyleSheet(self._CSS_IDLE)
        paths = []
        for u in event.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.is_dir():
                paths.extend(
                    f for f in sorted(p.iterdir())
                    if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg"}
                )
            elif p.suffix.lower() in {".jpg", ".jpeg"}:
                paths.append(p)
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, event):
        self.add_clicked.emit()


# ── Main window ──────────────────────────────────────────────────────
_PREVIEW_SIZE = 800
_RIGHT_W      = 820


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BatchSquareFill")
        self.setFixedSize(620 + _RIGHT_W, 840)
        self.files: list = []
        self._side_pct   = False
        self._selected   = 0
        self._wm_enabled = False
        self._wm_img     = None
        self._wm_mode    = "both"   # "lighten" | "desat" | "both"

        central = QWidget()
        central.setStyleSheet(f"background: {_BG};")
        self.setCentralWidget(central)

        # ── Root: left controls | right preview sidebar ───────────────
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel ────────────────────────────────────────────────
        left = QWidget()
        left.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(left)
        lay.setContentsMargins(16, 20, 12, 16)
        lay.setSpacing(0)
        root.addWidget(left, stretch=1)

        # Wordmark — inherit the app's system UI font, only override size/weight
        title_font = QApplication.font()
        title_font.setPointSize(22)
        title_font.setWeight(QFont.Weight.DemiBold)

        wordmark = QLabel("BatchSquareFill")
        wordmark.setFont(title_font)
        wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wordmark.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        lay.addWidget(wordmark)

        sub = QLabel("Batch square fill with blurred background")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {_TEXT2}; font-size: 12px; background: transparent;")
        lay.addWidget(sub)
        lay.addSpacing(16)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        self.drop_zone.add_clicked.connect(self._add_files)
        lay.addWidget(self.drop_zone)
        lay.addSpacing(12)

        # File list card
        list_card = QFrame()
        list_card.setStyleSheet(f"QFrame {{ background: {_SURF}; border-radius: 10px; }}")
        list_card_lay = QVBoxLayout(list_card)
        list_card_lay.setContentsMargins(0, 0, 0, 0)
        list_card_lay.setSpacing(0)

        lh = QWidget()
        lh.setStyleSheet("background: transparent;")
        lh_lay = QHBoxLayout(lh)
        lh_lay.setContentsMargins(12, 10, 10, 6)
        sec_lbl = QLabel("IMAGES")
        sec_lbl.setStyleSheet(
            f"color: {_TEXT2}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        lh_lay.addWidget(sec_lbl)
        lh_lay.addStretch()
        add_btn = QPushButton("＋ Add")
        add_btn.setFixedHeight(24)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {_BLUE}; font-size: 12px;
                           font-weight: 500; border-radius: 5px; padding: 0 8px; border: none; }}
            QPushButton:hover {{ background: rgba(10,132,255,0.12); }}
        """)
        add_btn.clicked.connect(self._add_files)
        lh_lay.addWidget(add_btn)
        list_card_lay.addWidget(lh)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(255,255,255,0.08); border: none;")
        list_card_lay.addWidget(divider)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(190)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px 0; }}
            QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.2);
                                           border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(0)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.list_widget)
        list_card_lay.addWidget(self.scroll)
        lay.addWidget(list_card)
        lay.addSpacing(12)

        # Settings card
        settings = QFrame()
        settings.setStyleSheet(f"QFrame {{ background: {_SURF}; border-radius: 10px; }}")
        sl = QVBoxLayout(settings)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(10)

        row_side = QHBoxLayout()
        row_side.setSpacing(8)
        lbl_side = QLabel("Side length")
        lbl_side.setFixedWidth(100)
        lbl_side.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_side.addWidget(lbl_side)
        self.spin_side = QSpinBox()
        self.spin_side.setRange(256, 8192)
        self.spin_side.setValue(1080)
        self.spin_side.setFixedWidth(88)
        self.spin_side.setStyleSheet(self._spinbox_css())
        row_side.addWidget(self.spin_side)

        seg = QFrame()
        seg.setFixedSize(68, 28)
        seg.setStyleSheet(f"QFrame {{ background: {_SURF2}; border-radius: 7px; }}")
        seg_lay = QHBoxLayout(seg)
        seg_lay.setContentsMargins(2, 2, 2, 2)
        seg_lay.setSpacing(2)
        self._btn_px  = QPushButton("px")
        self._btn_pct = QPushButton("%")
        for b in (self._btn_px, self._btn_pct):
            b.setFixedHeight(24)
        self._apply_seg_style()
        self._btn_px.clicked.connect(lambda: self._set_side_unit(False))
        self._btn_pct.clicked.connect(lambda: self._set_side_unit(True))
        seg_lay.addWidget(self._btn_px)
        seg_lay.addWidget(self._btn_pct)
        row_side.addWidget(seg)
        row_side.addStretch()
        sl.addLayout(row_side)

        row_blur = QHBoxLayout()
        row_blur.setSpacing(8)
        lbl_blur = QLabel("Blur radius (%)")
        lbl_blur.setFixedWidth(110)
        lbl_blur.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_blur.addWidget(lbl_blur)
        self.spin_blur = QSpinBox()
        self.spin_blur.setRange(0, 25)
        self.spin_blur.setValue(8)
        self.spin_blur.setFixedWidth(88)
        self.spin_blur.setStyleSheet(self._spinbox_css())
        row_blur.addWidget(self.spin_blur)
        row_blur.addStretch()
        sl.addLayout(row_blur)
        self.spin_blur.valueChanged.connect(self._refresh_preview)

        lay.addWidget(settings)
        lay.addSpacing(12)

        # ── Watermark card ────────────────────────────────────────────
        wm_card = QFrame()
        wm_card.setStyleSheet(f"QFrame {{ background: {_SURF}; border-radius: 10px; }}")
        wml = QVBoxLayout(wm_card)
        wml.setContentsMargins(16, 12, 16, 12)
        wml.setSpacing(10)

        # Header: WATERMARK label + On/Off toggle
        wm_hdr_row = QHBoxLayout()
        wm_hdr_row.setSpacing(8)
        wm_sec_lbl = QLabel("WATERMARK")
        wm_sec_lbl.setStyleSheet(
            f"color: {_TEXT2}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        wm_hdr_row.addWidget(wm_sec_lbl)
        wm_hdr_row.addStretch()

        wm_seg = QFrame()
        wm_seg.setFixedSize(68, 28)
        wm_seg.setStyleSheet(f"QFrame {{ background: {_SURF2}; border-radius: 7px; }}")
        wm_seg_lay = QHBoxLayout(wm_seg)
        wm_seg_lay.setContentsMargins(2, 2, 2, 2)
        wm_seg_lay.setSpacing(2)
        self._btn_wm_on  = QPushButton("On")
        self._btn_wm_off = QPushButton("Off")
        for b in (self._btn_wm_on, self._btn_wm_off):
            b.setFixedHeight(24)
        self._apply_wm_seg_style()
        self._btn_wm_on.clicked.connect(lambda: self._set_wm_enabled(True))
        self._btn_wm_off.clicked.connect(lambda: self._set_wm_enabled(False))
        wm_seg_lay.addWidget(self._btn_wm_on)
        wm_seg_lay.addWidget(self._btn_wm_off)
        wm_hdr_row.addWidget(wm_seg)
        wml.addLayout(wm_hdr_row)

        # Body
        self._wm_body = QWidget()
        self._wm_body.setStyleSheet("background: transparent;")
        self._wm_body.setEnabled(False)
        wm_body_lay = QVBoxLayout(self._wm_body)
        wm_body_lay.setContentsMargins(0, 0, 0, 0)
        wm_body_lay.setSpacing(10)

        # Logo picker row
        row_logo = QHBoxLayout()
        row_logo.setSpacing(8)
        self._btn_wm_choose = QPushButton("Choose PNG…")
        self._btn_wm_choose.setFixedHeight(24)
        self._btn_wm_choose.setStyleSheet(f"""
            QPushButton {{ background: {_SURF2}; color: {_TEXT}; font-size: 12px;
                           font-weight: 500; border-radius: 5px; padding: 0 10px; border: none; }}
            QPushButton:hover {{ background: {_SURF3}; }}
        """)
        self._btn_wm_choose.clicked.connect(self._choose_watermark)
        row_logo.addWidget(self._btn_wm_choose)
        self._wm_name_lbl = QLabel("No file selected")
        self._wm_name_lbl.setStyleSheet(
            f"color: {_TEXT2}; font-size: 11px; background: transparent;"
        )
        self._wm_name_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_logo.addWidget(self._wm_name_lbl, stretch=1)
        wm_body_lay.addLayout(row_logo)

        # Size + Strength row
        row_ss = QHBoxLayout()
        row_ss.setSpacing(8)
        lbl_wm_size = QLabel("Size %")
        lbl_wm_size.setFixedWidth(60)
        lbl_wm_size.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_ss.addWidget(lbl_wm_size)
        self.spin_wm_size = QSpinBox()
        self.spin_wm_size.setRange(1, 100)
        self.spin_wm_size.setValue(35)
        self.spin_wm_size.setFixedWidth(88)
        self.spin_wm_size.setStyleSheet(self._spinbox_css())
        row_ss.addWidget(self.spin_wm_size)
        row_ss.addStretch()
        lbl_wm_str = QLabel("Strength %")
        lbl_wm_str.setFixedWidth(78)
        lbl_wm_str.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_ss.addWidget(lbl_wm_str)
        self.spin_wm_strength = QSpinBox()
        self.spin_wm_strength.setRange(0, 100)
        self.spin_wm_strength.setValue(90)
        self.spin_wm_strength.setFixedWidth(88)
        self.spin_wm_strength.setStyleSheet(self._spinbox_css())
        row_ss.addWidget(self.spin_wm_strength)
        row_ss.addStretch()
        wm_body_lay.addLayout(row_ss)

        # Mode toggle row: [Lighten | Desat | Both]
        row_mode = QHBoxLayout()
        row_mode.setSpacing(8)
        lbl_mode = QLabel("Mode")
        lbl_mode.setFixedWidth(60)
        lbl_mode.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_mode.addWidget(lbl_mode)

        mode_seg = QFrame()
        mode_seg.setFixedSize(160, 28)
        mode_seg.setStyleSheet(f"QFrame {{ background: {_SURF2}; border-radius: 7px; }}")
        mode_seg_lay = QHBoxLayout(mode_seg)
        mode_seg_lay.setContentsMargins(2, 2, 2, 2)
        mode_seg_lay.setSpacing(2)
        self._btn_mode_lighten = QPushButton("Light")
        self._btn_mode_desat   = QPushButton("Desat")
        self._btn_mode_both    = QPushButton("Both")
        for b in (self._btn_mode_lighten, self._btn_mode_desat, self._btn_mode_both):
            b.setFixedHeight(24)
        self._apply_mode_seg_style()
        self._btn_mode_lighten.clicked.connect(lambda: self._set_wm_mode("lighten"))
        self._btn_mode_desat.clicked.connect(lambda:   self._set_wm_mode("desat"))
        self._btn_mode_both.clicked.connect(lambda:    self._set_wm_mode("both"))
        mode_seg_lay.addWidget(self._btn_mode_lighten)
        mode_seg_lay.addWidget(self._btn_mode_desat)
        mode_seg_lay.addWidget(self._btn_mode_both)
        row_mode.addWidget(mode_seg)
        row_mode.addStretch()
        wm_body_lay.addLayout(row_mode)

        # X pos + Y pos row
        row_xy = QHBoxLayout()
        row_xy.setSpacing(8)
        lbl_wm_x = QLabel("X pos %")
        lbl_wm_x.setFixedWidth(60)
        lbl_wm_x.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_xy.addWidget(lbl_wm_x)
        self.spin_wm_x = QSpinBox()
        self.spin_wm_x.setRange(0, 100)
        self.spin_wm_x.setValue(50)
        self.spin_wm_x.setFixedWidth(88)
        self.spin_wm_x.setStyleSheet(self._spinbox_css())
        row_xy.addWidget(self.spin_wm_x)
        row_xy.addStretch()
        lbl_wm_y = QLabel("Y pos %")
        lbl_wm_y.setFixedWidth(75)
        lbl_wm_y.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_xy.addWidget(lbl_wm_y)
        self.spin_wm_y = QSpinBox()
        self.spin_wm_y.setRange(0, 100)
        self.spin_wm_y.setValue(98)
        self.spin_wm_y.setFixedWidth(88)
        self.spin_wm_y.setStyleSheet(self._spinbox_css())
        row_xy.addWidget(self.spin_wm_y)
        row_xy.addStretch()
        wm_body_lay.addLayout(row_xy)

        wml.addWidget(self._wm_body)
        lay.addWidget(wm_card)
        lay.addSpacing(12)

        for sp in (self.spin_wm_size, self.spin_wm_strength, self.spin_wm_x, self.spin_wm_y):
            sp.valueChanged.connect(self._refresh_preview)

        # Process button
        self.btn_process = QPushButton("▶  Process")
        self.btn_process.setFixedHeight(44)
        self.btn_process.setStyleSheet(f"""
            QPushButton {{ background: {_BLUE}; color: #ffffff; font-size: 15px;
                           font-weight: 600; border-radius: 10px; border: none; }}
            QPushButton:hover   {{ background: #2090ff; }}
            QPushButton:pressed {{ background: #006edb; }}
            QPushButton:disabled {{ background: {_SURF2}; color: {_TEXT2}; }}
        """)
        self.btn_process.clicked.connect(self._start_processing)
        lay.addWidget(self.btn_process)
        lay.addSpacing(10)

        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(4)
        self.progressbar.setStyleSheet(f"""
            QProgressBar {{ background: rgba(255,255,255,0.08); border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background: {_BLUE}; border-radius: 2px; }}
        """)
        lay.addWidget(self.progressbar)
        lay.addSpacing(8)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_lbl.setStyleSheet(f"color: {_TEXT2}; font-size: 12px; background: transparent;")
        lay.addWidget(self.progress_lbl)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color: {_TEXT2}; font-size: 12px; background: transparent;")
        lay.addWidget(self.status_lbl)

        # ── Right preview sidebar ─────────────────────────────────────
        prev_sidebar = QFrame()
        prev_sidebar.setFixedWidth(_RIGHT_W)
        prev_sidebar.setStyleSheet(f"""
            QFrame {{
                background: {_SURF};
                border-left: 1px solid rgba(255,255,255,0.06);
                border-radius: 0px;
            }}
        """)
        pc_lay = QVBoxLayout(prev_sidebar)
        pc_lay.setContentsMargins(10, 10, 10, 10)
        pc_lay.setSpacing(4)
        pc_lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        prev_hdr = QLabel("PREVIEW")
        prev_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_hdr.setStyleSheet(
            f"color: {_TEXT2}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        pc_lay.addWidget(prev_hdr)

        self.preview = QLabel("–")
        self.preview.setFixedSize(_PREVIEW_SIZE, _PREVIEW_SIZE)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            f"background: {_SURF2}; border-radius: 8px; color: {_TEXT2}; font-size: 12px;"
        )
        pc_lay.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(prev_sidebar)

        # Auto-load logo.png from the script directory if present
        _logo = SCRIPT_DIR / "logo.png"
        if _logo.exists():
            self._wm_img = Image.open(_logo).convert("RGBA")
            self._wm_name_lbl.setText(_logo.name)
            self._wm_enabled = True
            self._apply_wm_seg_style()
            self._wm_body.setEnabled(True)

    # ── Styling helpers ──────────────────────────────────────────────
    @staticmethod
    def _spinbox_css() -> str:
        return f"""
            QSpinBox {{ background: {_SURF2}; color: {_TEXT}; border-radius: 6px;
                        padding: 4px 8px; border: none; font-size: 13px; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; background: transparent; }}
            QSpinBox::up-arrow   {{ image: none; }}
            QSpinBox::down-arrow {{ image: none; }}
        """

    def _seg_on_css(self):
        return f"""QPushButton {{ background: {_SURF3}; color: {_TEXT};
                                   border-radius: 5px; font-size: 12px; padding: 0 8px; border: none; }}"""

    def _seg_off_css(self):
        return f"""QPushButton {{ background: transparent; color: {_TEXT2};
                                   border-radius: 5px; font-size: 12px; padding: 0 8px; border: none; }}"""

    def _apply_seg_style(self):
        self._btn_px.setStyleSheet(self._seg_on_css()  if not self._side_pct else self._seg_off_css())
        self._btn_pct.setStyleSheet(self._seg_off_css() if not self._side_pct else self._seg_on_css())

    def _apply_wm_seg_style(self):
        self._btn_wm_on.setStyleSheet(self._seg_on_css()  if self._wm_enabled else self._seg_off_css())
        self._btn_wm_off.setStyleSheet(self._seg_off_css() if self._wm_enabled else self._seg_on_css())

    def _apply_mode_seg_style(self):
        for btn, mode in (
            (self._btn_mode_lighten, "lighten"),
            (self._btn_mode_desat,   "desat"),
            (self._btn_mode_both,    "both"),
        ):
            btn.setStyleSheet(
                self._seg_on_css() if self._wm_mode == mode else self._seg_off_css()
            )

    def _set_side_unit(self, pct: bool):
        self._side_pct = pct
        self._apply_seg_style()
        if pct:
            self.spin_side.setRange(10, 200)
            self.spin_side.setValue(100)
        else:
            self.spin_side.setRange(256, 8192)
            self.spin_side.setValue(1080)

    def _set_wm_enabled(self, enabled: bool):
        self._wm_enabled = enabled
        self._apply_wm_seg_style()
        self._wm_body.setEnabled(enabled)
        self._refresh_preview()

    def _set_wm_mode(self, mode: str):
        self._wm_mode = mode
        self._apply_mode_seg_style()
        self._refresh_preview()

    # ── File handling ────────────────────────────────────────────────

    def _on_drop(self, paths: list):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self._refresh_list()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select JPEG images", str(SCRIPT_DIR),
            "JPEG images (*.jpg *.jpeg)"
        )
        for p in paths:
            pp = Path(p)
            if pp not in self.files:
                self.files.append(pp)
        self._refresh_list()

    def _choose_watermark(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select watermark PNG", str(SCRIPT_DIR),
            "PNG images (*.png)"
        )
        if path:
            self._wm_img = Image.open(path).convert("RGBA")
            self._wm_name_lbl.setText(Path(path).name)
            self._refresh_preview()

    def _refresh_preview(self):
        if self.files:
            self._show_preview(self._selected)

    def _refresh_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if w := item.widget():
                w.deleteLater()

        for i, f in enumerate(self.files):
            row = QWidget()
            row.setFixedHeight(32)
            is_even = i % 2 == 0
            row.setStyleSheet(
                f"background: {'rgba(255,255,255,0.03)' if is_even else 'transparent'};"
            )
            hl = QHBoxLayout(row)
            hl.setContentsMargins(12, 0, 8, 0)
            hl.setSpacing(6)

            lbl = QLabel(f.name)
            lbl.setStyleSheet(
                f"color: {_TEXT}; font-size: 12px; "
                f"font-family: 'SF Mono', Menlo, monospace; background: transparent;"
            )
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = lambda e, idx=i: self._show_preview(idx)
            hl.addWidget(lbl, stretch=1)

            btn = QPushButton("−")
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(f"""
                QPushButton {{ background: rgba(255,69,58,0.12); color: {_RED};
                               border-radius: 4px; font-size: 14px; border: none; }}
                QPushButton:hover {{ background: rgba(255,69,58,0.28); }}
            """)
            btn.clicked.connect(lambda checked, idx=i: self._remove(idx))
            hl.addWidget(btn)
            self.list_layout.addWidget(row)

        if self.files:
            self._show_preview(0)

    def _remove(self, idx):
        self.files.pop(idx)
        self._refresh_list()
        if not self.files:
            self.preview.setText("–")
            self.preview.setPixmap(QPixmap())

    def _show_preview(self, idx):
        self._selected = idx
        try:
            img = Image.open(self.files[idx])
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            dpr = self.preview.devicePixelRatioF()
            render_px = round(_PREVIEW_SIZE * dpr)
            img.thumbnail((render_px * 2, render_px * 2), Image.LANCZOS)
            blur_px = round(render_px * self.spin_blur.value() / 100)
            wm_img = self._wm_img if (self._wm_enabled and self._wm_img is not None) else None
            result = _make_square(
                img, render_px, blur_px, wm_img,
                self.spin_wm_size.value(), self.spin_wm_x.value(),
                self.spin_wm_y.value(), self.spin_wm_strength.value(),
                self._wm_mode,
            )
            data = result.tobytes("raw", "RGB")
            qimg = QImage(data, result.width, result.height, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            pixmap.setDevicePixelRatio(dpr)
            self.preview.setPixmap(pixmap)
        except Exception:
            self.preview.setText("Preview\nerror")

    # ── Processing ───────────────────────────────────────────────────
    def _start_processing(self):
        if not self.files:
            self._set_status("⚠ No images in list.", error=True)
            return
        self.btn_process.setEnabled(False)
        self.progressbar.setValue(0)
        self.progressbar.setMaximum(len(self.files))
        self.status_lbl.setText("")

        wm_img = self._wm_img if (self._wm_enabled and self._wm_img is not None) else None
        self.worker = Worker(
            self.files, self.spin_side.value(), self.spin_blur.value(),
            self._side_pct, wm_img,
            self.spin_wm_size.value(), self.spin_wm_x.value(),
            self.spin_wm_y.value(), self.spin_wm_strength.value(),
            self._wm_mode,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_error)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_progress(self, i: int, n: int, name: str):
        self.progressbar.setValue(i + 1)
        self.progress_lbl.setText(f"{name}  ({i+1}/{n})")

    def _on_error(self, name: str, msg: str):
        self._set_status(f"⚠ Error in {name}: {msg}", error=True)

    def _on_done(self, n: int):
        self.progressbar.setValue(n)
        self.progress_lbl.setText("")
        self._set_status(f"✓ {n} image(s) done → /out folder")
        self.btn_process.setEnabled(True)

    def _set_status(self, text: str, error: bool = False):
        color = _RED if error else "#30d158"
        self.status_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; background: transparent;"
        )
        self.status_lbl.setText(text)


# ── Entry point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(_BG))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(_TEXT))
    p.setColor(QPalette.ColorRole.Base,            QColor(_SURF))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(_SURF2))
    p.setColor(QPalette.ColorRole.Text,            QColor(_TEXT))
    p.setColor(QPalette.ColorRole.Button,          QColor(_SURF2))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(_TEXT))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(_ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(_BG))
    app.setPalette(p)

    window = App()
    window.show()
    sys.exit(app.exec())
