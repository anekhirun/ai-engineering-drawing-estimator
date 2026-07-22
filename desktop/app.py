from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction, QColor, QBrush, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.workflow import (
    confirmation_output_dir,
    decision_counts,
    detection_output_dir,
    load_candidates,
    unresolved_candidate_ids,
)
from mcp.server import (
    VERSION,
    confirm_symbol_count,
    detect_symbol_candidates,
    inspect_drawing,
)


SYMBOL_LABELS = {
    "DUPLEX_SOCKET_OUTLET": "Duplex Socket Outlet (เต้ารับคู่)",
    "SINGLE_SOCKET_OUTLET": "Single Socket Outlet (เต้ารับเดี่ยว)",
    "DATA_OUTLET": "Data Outlet (จุดต่อข้อมูล)",
}


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class FunctionWorker(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.function())
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()


class DrawingView(QGraphicsView):
    image_clicked = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#20242b"))
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._manual_items: list[QGraphicsEllipseItem] = []
        self._manual_mode = False
        self._dpi = 300

    def set_image(self, path: str | Path | None, *, fit: bool = True) -> None:
        self.scene().clear()
        self._pixmap_item = None
        self._manual_items.clear()
        if not path:
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(self._pixmap_item.boundingRect())
        if fit:
            self.fit_image()

    def fit_image(self) -> None:
        if self._pixmap_item:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = enabled
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
            if enabled
            else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_manual_points(self, points_pt: list[list[float]], dpi: int) -> None:
        self._dpi = dpi
        for item in self._manual_items:
            self.scene().removeItem(item)
        self._manual_items.clear()
        scale = dpi / 72.0
        pen = QPen(QColor("#00d084"), 3)
        brush = QBrush(QColor(0, 208, 132, 70))
        radius = 11
        for x_pt, y_pt in points_pt:
            item = self.scene().addEllipse(
                x_pt * scale - radius,
                y_pt * scale - radius,
                radius * 2,
                radius * 2,
                pen,
                brush,
            )
            item.setZValue(10)
            self._manual_items.append(item)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._manual_mode and event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            if self._pixmap_item and self._pixmap_item.boundingRect().contains(point):
                scale = self._dpi / 72.0
                self.image_clicked.emit(point.x() / scale, point.y() / scale)
                return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if not self._pixmap_item:
            return
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self.scale(factor, factor)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"TakeoffLens {VERSION}")
        self.resize(1440, 900)
        self.thread_pool = QThreadPool.globalInstance()
        self.pdf_path: Path | None = None
        self.inspection: dict[str, Any] | None = None
        self.detection_result: dict[str, Any] | None = None
        self.candidates: list[dict[str, Any]] = []
        self.decisions: dict[str, str] = {}
        self.manual_points: list[list[float]] = []
        self._busy = False
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        toolbar = self.addToolBar("Main")
        open_action = QAction("เปิด PDF", self)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)
        fit_action = QAction("พอดีหน้าจอ", self)
        fit_action.triggered.connect(self.drawing_view_fit)
        toolbar.addAction(fit_action)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.drawing_view = DrawingView()
        self.drawing_view.image_clicked.connect(self.add_manual_point)
        splitter.addWidget(self.drawing_view)

        panel = QWidget()
        panel.setMinimumWidth(430)
        panel.setMaximumWidth(560)
        panel_layout = QVBoxLayout(panel)

        source_group = QGroupBox("1. แบบและหน้าที่ตรวจ")
        source_form = QFormLayout(source_group)
        file_row = QHBoxLayout()
        self.file_label = QLabel("ยังไม่ได้เลือกไฟล์")
        self.file_label.setWordWrap(True)
        browse_button = QPushButton("เปิด PDF")
        browse_button.clicked.connect(self.open_pdf)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(browse_button)
        source_form.addRow("ไฟล์", file_row)
        self.page_combo = QComboBox()
        self.page_combo.currentIndexChanged.connect(self.reset_detection)
        source_form.addRow("หน้า", self.page_combo)
        self.symbol_combo = QComboBox()
        for symbol_id, label in SYMBOL_LABELS.items():
            self.symbol_combo.addItem(label, symbol_id)
        self.symbol_combo.currentIndexChanged.connect(self.reset_detection)
        source_form.addRow("อุปกรณ์", self.symbol_combo)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(150, 600)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.setValue(300)
        self.dpi_spin.valueChanged.connect(self.reset_detection)
        source_form.addRow("ความละเอียด", self.dpi_spin)
        template_row = QHBoxLayout()
        self.template_label = QLabel("Starter template")
        self.template_label.setWordWrap(True)
        template_button = QPushButton("เลือก Template")
        template_button.clicked.connect(self.choose_template)
        template_row.addWidget(self.template_label, 1)
        template_row.addWidget(template_button)
        source_form.addRow("Template", template_row)
        self.template_path: Path | None = None
        self.detect_button = QPushButton("ตรวจหา Candidate")
        self.detect_button.clicked.connect(self.run_detection)
        source_form.addRow(self.detect_button)
        panel_layout.addWidget(source_group)

        review_group = QGroupBox("2. ตรวจทาน Candidate")
        review_layout = QVBoxLayout(review_group)
        self.counts_label = QLabel("Accepted 0 | Rejected 0 | Uncertain 0 | Unreviewed 0")
        review_layout.addWidget(self.counts_label)
        self.candidate_table = QTableWidget(0, 4)
        self.candidate_table.setHorizontalHeaderLabels(
            ["ID", "Score", "Rotation", "Decision"]
        )
        self.candidate_table.horizontalHeader().setStretchLastSection(True)
        self.candidate_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.candidate_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.candidate_table.itemSelectionChanged.connect(self.preview_selected_crop)
        review_layout.addWidget(self.candidate_table, 1)
        self.crop_preview = QLabel("เลือก Candidate เพื่อดูภาพ Crop")
        self.crop_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_preview.setMinimumHeight(150)
        review_layout.addWidget(self.crop_preview)
        panel_layout.addWidget(review_group, 1)

        manual_group = QGroupBox("3. เพิ่มจุดที่ตรวจตกหล่น")
        manual_layout = QHBoxLayout(manual_group)
        self.manual_button = QPushButton("โหมดคลิกเพิ่มจุด")
        self.manual_button.setCheckable(True)
        self.manual_button.toggled.connect(self.toggle_manual_mode)
        manual_layout.addWidget(self.manual_button)
        self.manual_label = QLabel("Manual 0")
        manual_layout.addWidget(self.manual_label)
        undo_button = QPushButton("ลบจุดล่าสุด")
        undo_button.clicked.connect(self.undo_manual_point)
        manual_layout.addWidget(undo_button)
        panel_layout.addWidget(manual_group)

        confirm_group = QGroupBox("4. ยืนยันและส่งออก")
        confirm_layout = QVBoxLayout(confirm_group)
        self.wall_sweep_check = QCheckBox(
            "ตรวจ Candidate, แนวผนัง, มุม และสองข้างประตูครบแล้ว"
        )
        confirm_layout.addWidget(self.wall_sweep_check)
        self.confirm_button = QPushButton("ยืนยันจำนวนและสร้าง CSV / Markup")
        self.confirm_button.clicked.connect(self.run_confirmation)
        confirm_layout.addWidget(self.confirm_button)
        self.result_label = QLabel("ผลลัพธ์ยังไม่ถูกยืนยัน")
        self.result_label.setWordWrap(True)
        confirm_layout.addWidget(self.result_label)
        panel_layout.addWidget(confirm_group)

        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("พร้อมใช้งาน")

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7fa; }
            QGroupBox { font-weight: 600; border: 1px solid #ccd3dc;
                        border-radius: 8px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { padding: 7px 10px; border-radius: 5px; border: 1px solid #aab3bf; }
            QPushButton:hover { background: #eaf2ff; }
            QPushButton:checked { background: #ffe8b3; border-color: #d18b00; }
            QTableWidget { border: 1px solid #ccd3dc; gridline-color: #e3e7ec; }
            """
        )

    def drawing_view_fit(self) -> None:
        self.drawing_view.fit_image()

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.detect_button.setEnabled(not busy)
        self.confirm_button.setEnabled(not busy)
        if message:
            self.statusBar().showMessage(message)

    def run_worker(
        self,
        function: Callable[[], Any],
        success: Callable[[Any], None],
        message: str,
    ) -> None:
        self.set_busy(True, message)
        worker = FunctionWorker(function)
        worker.signals.result.connect(success)
        worker.signals.error.connect(self.show_worker_error)
        worker.signals.finished.connect(lambda: self.set_busy(False, "พร้อมใช้งาน"))
        self.thread_pool.start(worker)

    def show_worker_error(self, details: str) -> None:
        QMessageBox.critical(self, "เกิดข้อผิดพลาด", details)

    def open_pdf(self) -> None:
        if self._busy:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "เลือกแบบ PDF", str(PROJECT_ROOT), "PDF files (*.pdf)"
        )
        if not filename:
            return
        path = Path(filename).resolve()
        self.file_label.setText(str(path))
        self.pdf_path = path
        self.page_combo.clear()
        self.reset_detection()
        self.run_worker(
            lambda: inspect_drawing({"pdf_path": str(path)}),
            self.on_inspected,
            "กำลังตรวจชนิดของแต่ละหน้า...",
        )

    def on_inspected(self, result: dict[str, Any]) -> None:
        self.inspection = result
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        for page in result["pages"]:
            label = (
                f"หน้า {page['page']} — {page['classification']} "
                f"({page['vector_items']} vector items)"
            )
            self.page_combo.addItem(label, page["page"])
        self.page_combo.blockSignals(False)
        self.statusBar().showMessage(f"ตรวจพบ {result['page_count']} หน้า", 6000)

    def choose_template(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "เลือก Project-specific Template",
            str(PROJECT_ROOT),
            "JSON template (*.json)",
        )
        if filename:
            self.template_path = Path(filename).resolve()
            self.template_label.setText(str(self.template_path))
            self.reset_detection()

    def current_page(self) -> int:
        value = self.page_combo.currentData()
        if value is None:
            raise ValueError("กรุณาเปิด PDF และเลือกหน้าก่อน")
        return int(value)

    def current_symbol(self) -> str:
        return str(self.symbol_combo.currentData())

    def reset_detection(self) -> None:
        self.detection_result = None
        self.candidates = []
        self.decisions = {}
        self.manual_points = []
        if hasattr(self, "candidate_table"):
            self.candidate_table.setRowCount(0)
            self.drawing_view.set_image(None)
            self.crop_preview.setText("เลือก Candidate เพื่อดูภาพ Crop")
            self.crop_preview.setPixmap(QPixmap())
            self.wall_sweep_check.setChecked(False)
            self.result_label.setText("ผลลัพธ์ยังไม่ถูกยืนยัน")
            self.refresh_counts()

    def run_detection(self) -> None:
        if not self.pdf_path:
            QMessageBox.information(self, "ยังไม่มีไฟล์", "กรุณาเปิด PDF ก่อน")
            return
        page = self.current_page()
        symbol_id = self.current_symbol()
        output_dir = detection_output_dir(PROJECT_ROOT, self.pdf_path, page, symbol_id)
        args: dict[str, Any] = {
            "pdf_path": str(self.pdf_path),
            "page": page,
            "symbol_id": symbol_id,
            "dpi": self.dpi_spin.value(),
            "output_dir": str(output_dir),
            "exclude_text": True,
            "shortlist_limit": 100,
        }
        if self.template_path:
            args["template_path"] = str(self.template_path)
        self.run_worker(
            lambda: detect_symbol_candidates(args),
            self.on_detected,
            "กำลังตรวจหา Candidate...",
        )

    def on_detected(self, result: dict[str, Any]) -> None:
        self.detection_result = result
        self.candidates = load_candidates(Path(result["candidates_json"]))
        self.decisions = {
            str(candidate["candidate_id"]): "unreviewed" for candidate in self.candidates
        }
        self.manual_points = []
        self.populate_candidate_table()
        self.drawing_view.set_image(result["markup_path"])
        self.drawing_view.set_manual_points([], self.dpi_spin.value())
        self.wall_sweep_check.setChecked(False)
        self.result_label.setText("ตรวจพบ Candidate แล้ว กรุณาตรวจทานทุกจุด")
        self.statusBar().showMessage(
            f"ตรวจพบ Candidate {len(self.candidates)} จุด — ยังไม่ใช่จำนวนสุดท้าย", 8000
        )

    def populate_candidate_table(self) -> None:
        self.candidate_table.setRowCount(len(self.candidates))
        for row, candidate in enumerate(self.candidates):
            candidate_id = str(candidate["candidate_id"])
            self.candidate_table.setItem(row, 0, QTableWidgetItem(candidate_id))
            self.candidate_table.setItem(
                row, 1, QTableWidgetItem(f"{float(candidate['score']):.4f}")
            )
            self.candidate_table.setItem(
                row, 2, QTableWidgetItem(str(candidate.get("rotation", "")))
            )
            combo = QComboBox()
            combo.addItem("Unreviewed", "unreviewed")
            combo.addItem("Accept", "accept")
            combo.addItem("Reject", "reject")
            combo.addItem("Uncertain", "uncertain")
            combo.currentIndexChanged.connect(
                lambda _index, cid=candidate_id, widget=combo: self.set_decision(
                    cid, str(widget.currentData())
                )
            )
            self.candidate_table.setCellWidget(row, 3, combo)
        self.candidate_table.resizeColumnsToContents()
        self.refresh_counts()

    def set_decision(self, candidate_id: str, decision: str) -> None:
        self.decisions[candidate_id] = decision
        self.refresh_counts()

    def refresh_counts(self) -> None:
        ids = [str(item["candidate_id"]) for item in self.candidates]
        counts = decision_counts(self.decisions, ids)
        self.counts_label.setText(
            "Accepted {accept} | Rejected {reject} | Uncertain {uncertain} | "
            "Unreviewed {unreviewed}".format(**counts)
        )
        self.manual_label.setText(f"Manual {len(self.manual_points)}")

    def preview_selected_crop(self) -> None:
        rows = self.candidate_table.selectionModel().selectedRows()
        if not rows or not self.detection_result:
            return
        candidate = self.candidates[rows[0].row()]
        crop_path = Path(self.detection_result["candidates_json"]).parent / str(
            candidate.get("crop_file", "")
        )
        pixmap = QPixmap(str(crop_path))
        if pixmap.isNull():
            self.crop_preview.setText("ไม่พบภาพ Crop")
            return
        self.crop_preview.setPixmap(
            pixmap.scaled(
                260,
                180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def toggle_manual_mode(self, enabled: bool) -> None:
        if enabled and not self.detection_result:
            self.manual_button.setChecked(False)
            QMessageBox.information(
                self, "ยังไม่มี Candidate", "กรุณารันการตรวจจับก่อนเพิ่มจุดด้วยมือ"
            )
            return
        self.drawing_view.set_manual_mode(enabled)
        self.manual_button.setText(
            "กำลังคลิกเพิ่มจุด (กดเพื่อหยุด)" if enabled else "โหมดคลิกเพิ่มจุด"
        )

    def add_manual_point(self, x_pt: float, y_pt: float) -> None:
        self.manual_points.append([round(x_pt, 3), round(y_pt, 3)])
        self.drawing_view.set_manual_points(self.manual_points, self.dpi_spin.value())
        self.refresh_counts()
        self.statusBar().showMessage(
            f"เพิ่ม Manual point ({x_pt:.1f}, {y_pt:.1f}) pt", 4000
        )

    def undo_manual_point(self) -> None:
        if self.manual_points:
            self.manual_points.pop()
            self.drawing_view.set_manual_points(self.manual_points, self.dpi_spin.value())
            self.refresh_counts()

    def run_confirmation(self) -> None:
        if not self.pdf_path or not self.detection_result:
            QMessageBox.information(
                self, "ยังไม่มีผลตรวจ", "กรุณาตรวจหาและทบทวน Candidate ก่อน"
            )
            return
        ids = [str(item["candidate_id"]) for item in self.candidates]
        unresolved = unresolved_candidate_ids(self.decisions, ids)
        if unresolved:
            QMessageBox.warning(
                self,
                "ยังตรวจไม่ครบ",
                f"ยังมี Candidate ที่ Unreviewed/Uncertain {len(unresolved)} จุด:\n"
                + ", ".join(unresolved[:20]),
            )
            return
        if not self.wall_sweep_check.isChecked():
            QMessageBox.warning(
                self,
                "ต้องยืนยันการกวาดตรวจ",
                "กรุณาตรวจแนวผนัง มุม และสองข้างประตู แล้วติ๊กยืนยันก่อนส่งออก",
            )
            return
        accepted = [cid for cid in ids if self.decisions.get(cid) == "accept"]
        rejected = [cid for cid in ids if self.decisions.get(cid) == "reject"]
        candidate_dir = Path(self.detection_result["candidates_json"]).parent
        output_dir = confirmation_output_dir(candidate_dir)
        args: dict[str, Any] = {
            "pdf_path": str(self.pdf_path),
            "page": self.current_page(),
            "symbol_id": self.current_symbol(),
            "dpi": self.dpi_spin.value(),
            "candidates_json": self.detection_result["candidates_json"],
            "accepted_ids": accepted,
            "rejected_ids": rejected,
            "uncertain_ids": [],
            "wall_door_sweep_completed": True,
            "manual_points": self.manual_points,
            "output_dir": str(output_dir),
            "template_path": self.detection_result["template_path"],
        }
        self.run_worker(
            lambda: confirm_symbol_count(args),
            self.on_confirmed,
            "กำลังสร้างรายงานและ Markup...",
        )

    def on_confirmed(self, result: dict[str, Any]) -> None:
        self.drawing_view.set_manual_mode(False)
        self.manual_button.setChecked(False)
        self.drawing_view.set_image(result["markup_path"])
        warning = f"\nคำเตือน: {result['review_warning']}" if result.get("review_warning") else ""
        self.result_label.setText(
            f"ยืนยันแล้ว {result['confirmed_count']} จุด\n"
            f"CSV: {result['report_csv']}\nMarkup: {result['markup_path']}{warning}"
        )
        QMessageBox.information(
            self,
            "ส่งออกสำเร็จ",
            f"จำนวนที่ยืนยัน: {result['confirmed_count']}\n\n"
            f"CSV: {result['report_csv']}\n"
            f"Markup: {result['markup_path']}",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("TakeoffLens")
    app.setOrganizationName("TakeoffLens")
    app.setFont(QFont("Leelawadee UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
