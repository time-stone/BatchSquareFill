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
_BG     = "#1c1c1e"   # systemBackground
_SURF   = "#2c2c2e"   # secondarySystemBackground
_SURF2  = "#3a3a3c"   # tertiarySystemBackground
_SURF3  = "#48484a"   # quaternary fill
_TEXT   = "#e5e5e7"   # label
_TEXT2  = "#8e8e93"   # secondaryLabel
_ACCENT = "#FFD60A"   # system yellow
_RED    = "#FF453A"   # system red
_BLUE   = "#0A84FF"   # system blue


# ── Image processing (pure Pillow, no GUI) ──────────────────────────
def _make_square(img: Image.Image, side: int, blur_px: int) -> Image.Image:
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
    return canvas


def process_image(src: Path, side: int, blur_pct: int, side_pct: bool = False) -> None:
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if side_pct:
        side = round(max(img.size) * side / 100)
    canvas = _make_square(img, side, round(side * blur_pct / 100))

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

    def __init__(self, files: list[Path], side: int, blur: int, side_pct: bool = False):
        super().__init__()
        self.files    = files
        self.side     = side
        self.blur     = blur
        self.side_pct = side_pct

    def run(self):
        n = len(self.files)
        for i, f in enumerate(self.files):
            self.progress.emit(i, n, f.name)
            try:
                process_image(f, self.side, self.blur, self.side_pct)
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
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BatchSquareFill")
        self.setFixedSize(620, 630)
        self.files: list[Path] = []
        self._side_pct = False
        self._selected = 0

        central = QWidget()
        central.setStyleSheet(f"background: {_BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(16, 20, 16, 16)
        root.setSpacing(0)

        # ── Wordmark ─────────────────────────────────────────────────
        title_font = QFont()
        title_font.setFamily("SF Pro Display")
        title_font.setPointSize(22)
        title_font.setWeight(QFont.Weight.DemiBold)

        wordmark = QLabel("BatchSquareFill")
        wordmark.setFont(title_font)
        wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wordmark.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        root.addWidget(wordmark)

        sub = QLabel("Batch square fill with blurred background")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {_TEXT2}; font-size: 12px; background: transparent;")
        root.addWidget(sub)
        root.addSpacing(16)

        # ── Drop zone ─────────────────────────────────────────────────
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_drop)
        self.drop_zone.add_clicked.connect(self._add_files)
        root.addWidget(self.drop_zone)
        root.addSpacing(12)

        # ── Middle: file list  +  preview ─────────────────────────────
        mid = QHBoxLayout()
        mid.setSpacing(10)
        root.addLayout(mid)

        # List card
        list_card = QFrame()
        list_card.setStyleSheet(f"QFrame {{ background: {_SURF}; border-radius: 10px; }}")
        list_card_lay = QVBoxLayout(list_card)
        list_card_lay.setContentsMargins(0, 0, 0, 0)
        list_card_lay.setSpacing(0)

        # List header
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
        divider.setStyleSheet(f"background: rgba(255,255,255,0.08); border: none;")
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
        mid.addWidget(list_card, stretch=1)

        # Preview card
        prev_card = QFrame()
        prev_card.setFixedWidth(196)
        prev_card.setStyleSheet(f"QFrame {{ background: {_SURF}; border-radius: 10px; }}")
        pc_lay = QVBoxLayout(prev_card)
        pc_lay.setContentsMargins(14, 10, 14, 14)
        pc_lay.setSpacing(8)
        pc_lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        prev_hdr = QLabel("PREVIEW")
        prev_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_hdr.setStyleSheet(
            f"color: {_TEXT2}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        pc_lay.addWidget(prev_hdr)

        self.preview = QLabel("–")
        self.preview.setFixedSize(168, 168)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            f"background: {_SURF2}; border-radius: 8px; color: {_TEXT2}; font-size: 12px;"
        )
        pc_lay.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        mid.addWidget(prev_card)

        root.addSpacing(12)

        # ── Settings card ─────────────────────────────────────────────
        settings = QFrame()
        settings.setStyleSheet(f"QFrame {{ background: {_SURF}; border-radius: 10px; }}")
        sl = QVBoxLayout(settings)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(10)

        # Side length row
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

        # Segmented control px / %
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

        # Blur radius row
        row_blur = QHBoxLayout()
        row_blur.setSpacing(8)
        lbl_blur = QLabel("Blur radius (%)")
        lbl_blur.setFixedWidth(110)
        lbl_blur.setStyleSheet(f"color: {_TEXT}; font-size: 13px; background: transparent;")
        row_blur.addWidget(lbl_blur)
        self.spin_blur = QSpinBox()
        self.spin_blur.setRange(0, 25)
        self.spin_blur.setValue(1)
        self.spin_blur.setFixedWidth(88)
        self.spin_blur.setStyleSheet(self._spinbox_css())
        row_blur.addWidget(self.spin_blur)
        row_blur.addStretch()
        sl.addLayout(row_blur)
        self.spin_blur.valueChanged.connect(
            lambda: self._show_preview(self._selected) if self.files else None
        )

        root.addWidget(settings)
        root.addSpacing(12)

        # ── Process button ────────────────────────────────────────────
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
        root.addWidget(self.btn_process)
        root.addSpacing(10)

        # ── Progress ──────────────────────────────────────────────────
        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(4)
        self.progressbar.setStyleSheet(f"""
            QProgressBar {{ background: rgba(255,255,255,0.08); border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background: {_BLUE}; border-radius: 2px; }}
        """)
        root.addWidget(self.progressbar)
        root.addSpacing(8)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_lbl.setStyleSheet(f"color: {_TEXT2}; font-size: 12px; background: transparent;")
        root.addWidget(self.progress_lbl)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color: {_TEXT2}; font-size: 12px; background: transparent;")
        root.addWidget(self.status_lbl)

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

    def _apply_seg_style(self):
        _on  = f"""QPushButton {{ background: {_SURF3}; color: {_TEXT};
                                   border-radius: 5px; font-size: 12px; padding: 0 8px; border: none; }}"""
        _off = f"""QPushButton {{ background: transparent; color: {_TEXT2};
                                   border-radius: 5px; font-size: 12px; padding: 0 8px; border: none; }}"""
        self._btn_px.setStyleSheet(_on  if not self._side_pct else _off)
        self._btn_pct.setStyleSheet(_off if not self._side_pct else _on)

    def _set_side_unit(self, pct: bool):
        self._side_pct = pct
        self._apply_seg_style()
        if pct:
            self.spin_side.setRange(10, 200)
            self.spin_side.setValue(100)
        else:
            self.spin_side.setRange(256, 8192)
            self.spin_side.setValue(1080)

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
            img.thumbnail((400, 400), Image.LANCZOS)
            blur_px = round(168 * self.spin_blur.value() / 100)
            result = _make_square(img, 168, blur_px)
            data = result.tobytes("raw", "RGB")
            qimg = QImage(data, result.width, result.height, QImage.Format.Format_RGB888)
            self.preview.setPixmap(QPixmap.fromImage(qimg))
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

        self.worker = Worker(
            self.files, self.spin_side.value(), self.spin_blur.value(), self._side_pct
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
