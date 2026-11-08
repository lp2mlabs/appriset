from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageQt
from PySide6.QtCore import Qt, QObject, QThread, Signal, QUrl, QStandardPaths
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPainter, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QSpinBox, QSlider, QCheckBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar,
    QScrollArea, QMessageBox, QLineEdit, QSplitter, QSizePolicy,
)

from engine import Settings, Result, SUPPORTED, Cancelled, compress, load_image

APP_NAME = 'WebImage Studio'


def size_text(n):
    return f'{n / 1048576:.2f} MB' if n >= 1048576 else f'{n / 1024:.1f} KB'


STYLE = '''
QWidget { font-family: "Segoe UI"; font-size: 12px; color: #e5e5e5; }
QMainWindow, QWidget#root { background: #161616; }
QLabel#brand { font-size: 24px; font-weight: 750; color: #f3f3f3; }
QLabel#subtitle, QLabel#muted { color: #a6a6a6; }
QLabel#eyebrow { color: #b8b8b8; font-size: 10px; font-weight: 750; letter-spacing: 1px; }
QLabel#section { font-size: 15px; font-weight: 700; }
QLabel#number { font-size: 23px; font-weight: 750; color: #eeeeee; }
QLabel#chip { color: #dddddd; background: #303030; border-radius: 13px; padding: 7px 13px; font-weight: 650; }
QFrame#card, QFrame#settings { background: #202020; border: 1px solid #383838; border-radius: 12px; }
QFrame#drop { background: #242424; border: 1px dashed #606060; border-radius: 12px; }
QPushButton { background: #2b2b2b; border: 1px solid #444444; padding: 9px 14px; border-radius: 7px; font-weight: 600; }
QPushButton:hover { background: #242424; border-color: #777777; }
QPushButton:pressed { background: #414141; }
QPushButton:disabled { color: #777777; background: #242424; border-color: #363636; }
QPushButton#primary { background: #e4e4e4; color: #171717; border: none; font-size: 14px; padding: 14px; }
QPushButton#primary:hover { background: #ffffff; }
QPushButton#primary:disabled { background: #505050; }
QPushButton#quiet { border: none; background: transparent; color: #b0b0b0; padding: 5px 8px; }
QComboBox, QSpinBox, QLineEdit { background: #292929; border: 1px solid #484848; border-radius: 6px; padding: 7px; min-height: 19px; }
QComboBox:focus, QSpinBox:focus, QLineEdit:focus { border: 1px solid #999999; }
QComboBox:disabled, QSpinBox:disabled { color: #757575; background: #242424; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #292929; selection-background-color: #454545; color: #e5e5e5; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QTableWidget { background: #202020; border: none; gridline-color: #343434; selection-background-color: #3b3b3b; selection-color: #ffffff; }
QHeaderView::section { background: #262626; border: none; border-bottom: 1px solid #3b3b3b; padding: 9px 6px; color: #b0b0b0; font-size: 11px; font-weight: 650; }
QTableWidget::item { padding: 7px 5px; border-bottom: 1px solid #343434; }
QTableWidget::item:selected { background: #3b3b3b; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: #202020; }
QScrollBar:vertical { width: 7px; background: transparent; }
QScrollBar::handle:vertical { background: #626262; min-height: 25px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSlider::groove:horizontal { height: 5px; background: #444444; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #bdbdbd; border-radius: 2px; }
QSlider::handle:horizontal { background: #e4e4e4; width: 15px; margin: -5px 0; border-radius: 7px; }
QProgressBar { border: none; background: #3d3d3d; border-radius: 3px; height: 6px; text-align: center; }
QProgressBar::chunk { background: #bbbbbb; border-radius: 3px; }
QToolTip { background: #333333; color: white; border: none; padding: 7px; }
'''


def label(text, role=None, wrap=False):
    item = QLabel(text)
    if role:
        item.setObjectName(role)
    item.setWordWrap(wrap)
    return item


class DropZone(QFrame):
    files_dropped = Signal(list)
    choose = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('drop')
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 14, 20, 14)
        icon = label('↙', 'number')
        row.addWidget(icon)
        text = QVBoxLayout()
        text.addWidget(label('Tarik gambar atau folder ke sini', 'section'))
        text.addWidget(label('JPG · PNG · WebP · AVIF · BMP · TIFF  /  gambar statis', 'muted'))
        row.addLayout(text, 1)
        button = QPushButton('+ Pilih gambar')
        button.clicked.connect(self.choose)
        row.addWidget(button)

    def dragEnterEvent(self, event):
        if self.isEnabled() and event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.files_dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()


class ImageView(QWidget):
    def __init__(self, empty):
        super().__init__()
        self.pixmap = None
        self.empty = empty
        self.setMinimumHeight(125)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def show_path(self, path):
        self.pixmap = None
        if path:
            try:
                image = load_image(Path(path))
                image.thumbnail((1000, 600), Image.Resampling.LANCZOS)
                self.pixmap = QPixmap.fromImage(ImageQt.ImageQt(image))
            except Exception:
                pass
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#262626'))
        if self.pixmap:
            for y in range(0, self.height(), 12):
                for x in range(0, self.width(), 12):
                    if (x // 12 + y // 12) % 2:
                        painter.fillRect(x, y, 12, 12, QColor('#333333'))
            scaled = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
        else:
            painter.setPen(QColor('#999999'))
            painter.drawText(self.rect(), Qt.AlignCenter, self.empty)


class Worker(QObject):
    started_item = Signal(int, str)
    stage = Signal(str)
    result = Signal(int, object)
    failure = Signal(int, str)
    finished = Signal()

    def __init__(self, paths, folder, settings):
        super().__init__()
        self.paths, self.folder, self.settings = paths, folder, settings
        self.stop = threading.Event()

    def run(self):
        try:
            for index, path in enumerate(self.paths):
                if self.stop.is_set():
                    break
                self.started_item.emit(index, path.name)
                try:
                    result = compress(path, self.folder, self.settings, self.stop.is_set, self.stage.emit)
                    self.result.emit(index, result)
                except Cancelled:
                    break
                except Exception as exc:
                    self.failure.emit(index, str(exc))
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + ' — Kompres gambar offline')
        self.setMinimumSize(1080, 740)
        self.resize(1320, 910)
        self.paths, self.results, self.errors = [], {}, {}
        self.busy = False
        self.worker = self.thread = None
        self._processed = 0
        self._run_name = ''
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 20, 26, 18)
        outer.setSpacing(19)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(3)
        title.addWidget(label('WebImage Studio', 'brand'))
        title.addWidget(label('Gambar lebih ringan. Website lebih cepat.', 'subtitle'))
        header.addLayout(title)
        header.addStretch()
        header.addWidget(label('●  100% offline', 'chip'))
        outer.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(22)
        outer.addLayout(body, 1)
        left = QVBoxLayout()
        left.setSpacing(14)
        body.addLayout(left, 1)
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_files = self.stat_card(stats, 'GAMBAR', '0')
        self.stat_before = self.stat_card(stats, 'UKURAN AWAL', '0 KB')
        self.stat_after = self.stat_card(stats, 'HASIL TERSIMPAN', '—')
        self.stat_saved = self.stat_card(stats, 'PENGHEMATAN', '—')
        left.addLayout(stats)
        self.drop = DropZone()
        self.drop.choose.connect(self.choose_files)
        self.drop.files_dropped.connect(self.add_paths)
        left.addWidget(self.drop)
        queue = QFrame()
        queue.setObjectName('card')
        qlayout = QVBoxLayout(queue)
        qlayout.setContentsMargins(0, 10, 0, 2)
        tools = QHBoxLayout()
        tools.setContentsMargins(14, 0, 10, 2)
        tools.addWidget(label('Daftar gambar', 'section'))
        tools.addStretch()
        self.folder_add = QPushButton('+ Folder')
        self.folder_add.setObjectName('quiet')
        self.folder_add.clicked.connect(self.choose_folder)
        self.remove_button = QPushButton('Hapus pilihan')
        self.remove_button.setObjectName('quiet')
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button = QPushButton('Bersihkan')
        self.clear_button.setObjectName('quiet')
        self.clear_button.clicked.connect(self.clear)
        for button in (self.folder_add, self.remove_button, self.clear_button):
            tools.addWidget(button)
        qlayout.addLayout(tools)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Nama gambar', 'Resolusi awal', 'Awal', 'Hasil', 'Hemat', 'Status'])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(43)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column, width in enumerate([0, 103, 80, 80, 65, 142]):
            if column:
                self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self.update_preview)
        self.table.setMinimumHeight(130)
        qlayout.addWidget(self.table)
        self.queue_hint = label('Belum ada gambar. Tambahkan file untuk mulai.', 'muted')
        self.queue_hint.setContentsMargins(15, 6, 15, 8)
        qlayout.addWidget(self.queue_hint)
        left.addWidget(queue, 3)
        preview = QFrame()
        preview.setObjectName('card')
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(14, 11, 14, 12)
        pv.setSpacing(7)
        phead = QHBoxLayout()
        phead.addWidget(label('Perbandingan', 'section'))
        phead.addStretch()
        phead.addWidget(label('Pilih satu baris untuk melihat gambar', 'muted'))
        pv.addLayout(phead)
        views = QHBoxLayout()
        for before in [True, False]:
            col = QVBoxLayout()
            head = label('ASLI' if before else 'HASIL', 'eyebrow')
            view = ImageView('Gambar asli' if before else 'Pratinjau setelah kompresi')
            detail = label('—', 'muted')
            detail.setAlignment(Qt.AlignCenter)
            col.addWidget(head)
            col.addWidget(view, 1)
            col.addWidget(detail)
            views.addLayout(col, 1)
            if before:
                self.before_view, self.before_detail = view, detail
            else:
                self.after_view, self.after_detail = view, detail
        pv.addLayout(views, 1)
        left.addWidget(preview, 2)
        self.make_settings(body)
        bottom = QHBoxLayout()
        status_group = QVBoxLayout()
        status_group.setSpacing(8)
        self.status = label('Siap. File asli tetap aman; hasil disimpan sebagai file baru.', 'muted')
        self.status.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        status_group.addWidget(self.status)
        status_group.addWidget(self.progress)
        bottom.addLayout(status_group, 1)
        self.cancel_button = QPushButton('Batalkan')
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        self.open_button = QPushButton('Buka hasil ↗')
        self.open_button.clicked.connect(self.open_folder)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.open_button)
        outer.addLayout(bottom)
        self.credit = label('Pengembang Dr, Muhamad · <a href="mailto:muhamad@iprija.ac.id" style="color:#bdbdbd;">muhamad@iprija.ac.id</a>', 'muted')
        self.credit.setOpenExternalLinks(True)
        self.credit.setTextInteractionFlags(Qt.TextBrowserInteraction)
        outer.addWidget(self.credit)
        self.preset_changed()
        self.update_stats()

    def stat_card(self, row, name, value):
        card = QFrame()
        card.setObjectName('card')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(4)
        layout.addWidget(label(name, 'eyebrow'))
        number = label(value, 'number')
        layout.addWidget(number)
        row.addWidget(card, 1)
        return number

    def make_settings(self, body):
        panel = QFrame()
        panel.setObjectName('settings')
        panel.setFixedWidth(302)
        body.addWidget(panel)
        base = QVBoxLayout(panel)
        base.setContentsMargins(16, 17, 16, 16)
        base.setSpacing(12)
        base.addWidget(label('Pengaturan ekspor', 'section'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(8)
        scroll.setWidget(content)
        base.addWidget(scroll, 1)
        layout.addWidget(label('FORMAT OUTPUT', 'eyebrow'))
        self.format_box = QComboBox()
        self.format_box.addItems(['Otomatis · file terkecil', 'WebP', 'AVIF', 'Tetap ekstensi semula'])
        layout.addWidget(self.format_box)
        self.format_hint = label('', 'muted', True)
        layout.addWidget(self.format_hint)
        self.format_box.currentIndexChanged.connect(self.update_format_hint)
        self.update_format_hint()
        layout.addSpacing(7)
        qrow = QHBoxLayout()
        qrow.addWidget(label('KUALITAS MAKSIMUM', 'eyebrow'))
        qrow.addStretch()
        self.quality_text = label('80', 'eyebrow')
        qrow.addWidget(self.quality_text)
        layout.addLayout(qrow)
        self.quality = QSlider(Qt.Horizontal)
        self.quality.setRange(25, 100)
        self.quality.setValue(80)
        self.quality.valueChanged.connect(lambda value: self.quality_text.setText(str(value)))
        layout.addWidget(self.quality)
        layout.addWidget(label('Lebih kecil  ←                       →  Lebih detail', 'muted'))
        layout.addSpacing(7)
        layout.addWidget(label('UKURAN & RESOLUSI', 'eyebrow'))
        self.preset = QComboBox()
        self.preset.addItems(['Asli · tanpa resize', 'HD · 1280 × 720', 'Full HD · 1920 × 1080',
                              'QHD · 2560 × 1440', '4K · 3840 × 2160',
                              'Website · 1600 × 900', 'Sosial · 4:5 / 5:4', '2K DCI · 2048 × 1080', 'Kustom'])
        self.preset.setCurrentIndex(2)
        self.preset.currentIndexChanged.connect(self.preset_changed)
        layout.addWidget(self.preset)
        self.orientation = QComboBox()
        self.orientation.addItems(['Landscape · mendatar', 'Portrait · tegak', 'Persegi · 1:1'])
        self.orientation.currentIndexChanged.connect(self.preset_changed)
        layout.addWidget(self.orientation)
        dims = QHBoxLayout()
        self.width_box, self.height_box = QSpinBox(), QSpinBox()
        for control, name in [(self.width_box, 'Lebar'), (self.height_box, 'Tinggi')]:
            control.setRange(1, 12000)
            control.setSuffix(' px')
            control.setToolTip(name + ' dalam piksel')
            control.valueChanged.connect(self.dimensions_changed)
            dims.addWidget(control)
            if control is self.width_box:
                dims.addWidget(label('×', 'muted'))
        layout.addLayout(dims)
        self.mode = QComboBox()
        self.mode.addItems(['Muat seluruh gambar · proporsional', 'Potong tengah · pas ukuran'])
        layout.addWidget(self.mode)
        self.allow_upscale = QCheckBox('Izinkan memperbesar gambar kecil')
        layout.addWidget(self.allow_upscale)
        layout.addWidget(label('Mode muat menjaga seluruh isi; ukuran hasil bisa lebih kecil dari kotak pilihan. Potong tengah mengisi kotak. Tanpa perbesar, kotak ikut diperkecil jika sumber kecil.', 'muted', True))
        layout.addSpacing(7)
        layout.addWidget(label('TARGET UKURAN PER GAMBAR', 'eyebrow'))
        self.target = QSpinBox()
        self.target.setRange(0, 100000)
        self.target.setSingleStep(50)
        self.target.setSuffix(' KB')
        self.target.setSpecialValueText('Tidak dibatasi')
        layout.addWidget(self.target)
        layout.addWidget(label('Target menurunkan kualitas JPEG/WebP/AVIF hingga 25. PNG/TIFF memakai kompresi lossless; BMP mengikuti resolusi. Target yang belum tercapai ditandai.', 'muted', True))
        layout.addWidget(label('Metadata EXIF/GPS dihapus. File asli tidak ditimpa.', 'muted', True))
        layout.addStretch()
        base.addWidget(label('FOLDER HASIL', 'eyebrow'))
        pictures = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        default_folder = Path(pictures or str(Path.home() / 'Pictures')) / 'WebImage Studio'
        self.output_folder = QLineEdit(str(default_folder))
        self.output_folder.setReadOnly(True)
        self.output_folder.setToolTip(str(default_folder))
        self.output_folder.setCursorPosition(len(str(default_folder)))
        base.addWidget(self.output_folder)
        base.addWidget(label('Default: folder WebImage Studio di Gambar/Pictures. Anda dapat memilih folder lain.', 'muted', True))
        self.choose_output_button = QPushButton('Ubah folder hasil…')
        self.choose_output_button.clicked.connect(self.choose_output)
        base.addWidget(self.choose_output_button)
        self.start_button = QPushButton('Kompres semua gambar  →')
        self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self.start)
        base.addWidget(self.start_button)
        base.addWidget(label('Diproses lokal · tanpa unggah · tanpa akun', 'muted'))
        self.settings_content = content

    def update_format_hint(self, *_):
        self.format_hint.setText('Otomatis membandingkan AVIF dan WebP pada kualitas pilihan.'
            if self.format_box.currentIndex() == 0 else
            'Format dan ekstensi setiap sumber dipertahankan, misalnya .jpg tetap .jpg dan .png tetap .png. PNG/TIFF lossless; BMP bisa tetap besar.'
            if self.format_box.currentIndex() == 3 else
            'Semua hasil dikonversi ke ' + self.format_box.currentText() + '.')

    def preset_changed(self, *_):
        index = self.preset.currentIndex()
        original = index == 0
        self.orientation.setEnabled(not original)
        self.mode.setEnabled(not original)
        self.allow_upscale.setEnabled(not original)
        for control in [self.width_box, self.height_box]:
            control.setEnabled(not original)
        if original:
            return
        sizes = {1: (1280, 720), 2: (1920, 1080), 3: (2560, 1440), 4: (3840, 2160),
                 5: (1600, 900), 6: (1350, 1080), 7: (2048, 1080)}
        width, height = sizes.get(index, (self.width_box.value(), self.height_box.value()))
        long, short = max(width, height), min(width, height)
        orient = self.orientation.currentIndex()
        width, height = (long, short) if orient == 0 else (short, long) if orient == 1 else (short, short)
        for control, value in [(self.width_box, width), (self.height_box, height)]:
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)

    def dimensions_changed(self, *_):
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(8)
        self.preset.blockSignals(False)
        w, h = self.width_box.value(), self.height_box.value()
        self.orientation.blockSignals(True)
        self.orientation.setCurrentIndex(0 if w > h else 1 if h > w else 2)
        self.orientation.blockSignals(False)

    def settings(self):
        original = self.preset.currentIndex() == 0
        return Settings(['AUTO', 'WEBP', 'AVIF', 'ORIGINAL'][self.format_box.currentIndex()], self.quality.value(),
                        0 if original else self.width_box.value(), 0 if original else self.height_box.value(),
                        'crop' if self.mode.currentIndex() else 'fit', self.allow_upscale.isChecked(), self.target.value())

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Pilih gambar', '',
            'Gambar (*.jpg *.jpeg *.png *.webp *.avif *.bmp *.tif *.tiff)')
        self.add_paths(files)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Pilih folder gambar')
        if folder:
            self.add_paths([folder])

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, 'Pilih folder hasil', self.output_folder.text())
        if folder:
            self.output_folder.setText(folder)
            self.output_folder.setToolTip(folder)
            self.output_folder.setCursorPosition(len(folder))
            self.status.setText('Folder hasil dipilih: ' + folder)

    def add_paths(self, paths):
        if self.busy:
            return
        known = {str(path).casefold() for path in self.paths}
        added, rejected = 0, 0
        for raw in paths:
            path = Path(raw)
            try:
                candidates = sorted(path.rglob('*')) if path.is_dir() else [path]
                for file in candidates:
                    if not file.is_file() or file.suffix.lower() not in SUPPORTED:
                        continue
                    file = file.resolve()
                    if str(file).casefold() in known:
                        continue
                    known.add(str(file).casefold())
                    row = len(self.paths)
                    self.paths.append(file)
                    self.table.insertRow(row)
                    try:
                        with Image.open(file) as image:
                            w, h = image.size
                            if image.getexif().get(274) in {5, 6, 7, 8}:
                                w, h = h, w
                        values = [file.name, f'{w} × {h}', size_text(file.stat().st_size), '—', '—', 'Menunggu']
                    except Exception:
                        values = [file.name, 'Tidak terbaca', size_text(file.stat().st_size), '—', '—', 'Perlu diperiksa']
                    for col, value in enumerate(values):
                        item = QTableWidgetItem(value)
                        item.setToolTip(str(file) if col == 0 else value)
                        self.table.setItem(row, col, item)
                    added += 1
            except OSError:
                rejected += 1
        self.queue_hint.setText(f'{len(self.paths)} gambar dalam antrean · pilih baris untuk pratinjau')
        self.status.setText(f'{added} gambar ditambahkan.' + (f' {rejected} lokasi tidak dapat diakses.' if rejected else ''))
        self.update_stats()
        if self.paths and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def remove_selected(self):
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            path = self.paths.pop(row)
            self.results.pop(str(path), None)
            self.errors.pop(str(path), None)
            self.table.removeRow(row)
        self.update_stats()
        self.update_preview()

    def clear(self):
        self.paths.clear()
        self.results.clear()
        self.errors.clear()
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.queue_hint.setText('Belum ada gambar. Tambahkan file untuk mulai.')
        self.status.setText('Antrean dibersihkan. Hasil yang sudah tersimpan tetap ada di folder hasil.')
        self.update_stats()
        self.update_preview()

    def update_stats(self):
        total = sum(p.stat().st_size for p in self.paths if p.exists())
        self.stat_files.setText(str(len(self.paths)))
        self.stat_before.setText(size_text(total))
        items = list(self.results.values())
        self.stat_after.setText(size_text(sum(r.output_bytes for r in items)) if items else '—')
        before = sum(r.original_bytes for r in items)
        after = sum(r.output_bytes for r in items)
        self.stat_saved.setText(f'{100 * (1 - after / before):.1f}%' if before else '—')
        self.stat_saved.setToolTip('Dihitung hanya dari gambar yang berhasil diproses. Nilai negatif berarti hasil lebih besar.')
        self.start_button.setEnabled(bool(self.paths) and not self.busy)

    def update_preview(self):
        row = self.table.currentRow()
        path = self.paths[row] if 0 <= row < len(self.paths) else None
        self.before_view.show_path(path)
        self.before_detail.setText('—')
        self.after_detail.setText('—')
        result = self.results.get(str(path)) if path else None
        self.after_view.show_path(result.output if result else None)
        if path:
            self.before_detail.setText(f'{self.table.item(row, 1).text()} px  ·  {self.table.item(row, 2).text()}')
        if result:
            self.after_detail.setText(f'{result.width} × {result.height} px  ·  {result.format}  ·  {size_text(result.output_bytes)}')

    def set_busy(self, busy):
        self.busy = busy
        for item in [self.drop, self.folder_add, self.remove_button, self.clear_button, self.settings_content, self.choose_output_button]:
            item.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText('Batalkan')
        self.update_stats()

    def start(self):
        if self.busy or not self.paths:
            return
        settings = self.settings()
        try:
            settings.validate()
            folder = Path(self.output_folder.text())
            folder.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Periksa pengaturan', str(exc))
            return
        self.results.clear()
        self.errors.clear()
        for row in range(len(self.paths)):
            for col in [3, 4]:
                self.table.item(row, col).setText('—')
            self.table.item(row, 5).setText('Menunggu')
        self._processed = 0
        self.set_busy(True)
        self.update_preview()
        self.progress.setRange(0, len(self.paths))
        self.progress.setValue(0)
        self.thread = QThread(self)
        self.worker = Worker(list(self.paths), folder, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.started_item.connect(self.item_started)
        self.worker.stage.connect(self.on_stage)
        self.worker.result.connect(self.item_done)
        self.worker.failure.connect(self.item_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.all_done)
        self.thread.start()

    def item_started(self, row, name):
        self._run_name = name
        self.table.item(row, 5).setText('Memproses…')
        self.status.setText(f'{row + 1}/{len(self.paths)} · {name}')

    def on_stage(self, stage):
        self.status.setText(f'{self._processed + 1}/{len(self.paths)} · {self._run_name} · {stage}')

    def item_done(self, row, result):
        self.results[str(self.paths[row])] = result
        self.table.item(row, 3).setText(size_text(result.output_bytes))
        self.table.item(row, 4).setText(f'{result.savings:.1f}%')
        note = 'Target belum tercapai' if not result.target_met else 'Lebih besar' if result.savings < 0 else 'Selesai · ' + result.format
        self.table.item(row, 5).setText(note)
        self.table.item(row, 5).setToolTip(f'{note}\n{result.width} × {result.height} px · kualitas {result.quality}\n{result.output}')
        self.table.item(row, 5).setForeground(QColor('#bababa' if not result.target_met or result.savings < 0 else '#dedede'))
        self._processed += 1
        self.progress.setValue(self._processed)
        self.update_stats()
        if self.table.currentRow() == row:
            self.update_preview()

    def item_failed(self, row, message):
        self.errors[str(self.paths[row])] = message
        self.table.item(row, 5).setText('Gagal · lihat detail')
        self.table.item(row, 5).setToolTip(message)
        self.table.item(row, 5).setForeground(QColor('#ffffff'))
        self._processed += 1
        self.progress.setValue(self._processed)

    def all_done(self):
        stopped = self.worker.stop.is_set()
        for row in range(len(self.paths)):
            if str(self.paths[row]) not in self.results and str(self.paths[row]) not in self.errors:
                self.table.item(row, 5).setText('Dibatalkan')
        misses = sum(not item.target_met for item in self.results.values())
        self.set_busy(False)
        self.status.setText(f'{"Dibatalkan" if stopped else "Selesai"} · {len(self.results)} berhasil · {len(self.errors)} gagal'
                            + (f' · {misses} target belum tercapai' if misses else '') + ' · Hasil: ' + self.output_folder.text())
        self.thread.deleteLater()
        self.thread = None
        self.worker = None

    def cancel(self):
        if self.worker:
            self.worker.stop.set()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText('Membatalkan…')
            self.status.setText('Membatalkan setelah encoder menyelesaikan pekerjaan saat ini…')

    def open_folder(self):
        folder = Path(self.output_folder.text())
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        else:
            self.status.setText('Folder hasil akan dibuat saat kompresi dimulai.')

    def closeEvent(self, event):
        if self.busy:
            self.cancel()
            self.status.setText('Tunggu pembatalan selesai, lalu tutup aplikasi kembali.')
            event.ignore()
        else:
            event.accept()


def create_icon():
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor('#292929'))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 120, 120, 29, 29)
    painter.setPen(QColor('white'))
    painter.setFont(QFont('Segoe UI', 55, QFont.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, 'W')
    painter.end()
    return QIcon(pixmap)


def self_test(folder):
    """Exercise the packaged encoders and Qt using generated fixtures, never user files."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGBA', (960, 640), (40, 150, 130, 0))
    ImageDraw.Draw(image).rounded_rectangle((80, 70, 880, 570), 60, fill=(27, 129, 107, 220))
    source = folder / 'smoke-source.png'
    image.save(source)
    results = [compress(source, folder / 'hasil', Settings(format=codec, width=360, height=640, mode='crop'))
               for codec in ['WEBP', 'AVIF', 'AUTO', 'ORIGINAL']]
    for result in results:
        with Image.open(result.output) as output:
            assert output.size == (360, 640), output.size
            assert 'A' in output.getbands()
    jpeg = folder / 'smoke-source.jpeg'
    image.convert('RGB').save(jpeg)
    preserved = compress(jpeg, folder / 'hasil', Settings(format='ORIGINAL', width=360, height=640, mode='crop'))
    assert Path(preserved.output).suffix == '.jpeg'
    with Image.open(preserved.output) as output:
        assert output.format == 'JPEG' and output.size == (360, 640)
    results.append(preserved)
    report = {'ok': True, 'results': [r.to_dict() for r in results]}
    (folder / 'self-test.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return source


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setWindowIcon(create_icon())
    if '--self-test' in sys.argv:
        folder = Path(sys.argv[sys.argv.index('--self-test') + 1])
        source = self_test(folder)
        window = MainWindow()
        window.add_paths([str(source)])
        window.show()
        app.processEvents()
        window.grab().save(str(folder / 'packaged-ui.png'))
        return 0
    window = MainWindow()
    screen = app.primaryScreen().availableGeometry()
    window.resize(min(1320, screen.width() - 50), min(910, screen.height() - 70))
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
