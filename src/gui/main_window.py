import sys
import os
import json
import copy
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGraphicsView, QGraphicsScene, QGraphicsLineItem,
    QGraphicsPixmapItem, QMessageBox, QSpinBox, QLineEdit, QShortcut
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QPixmap, QImage, QPen, QColor, QPainter, QKeySequence, QCursor
import numpy as np

from src.models import TablePageBounds, DetectedTable

class DraggableLine(QGraphicsLineItem):
    def __init__(self, x1, y1, x2, y2, orientation, page_width, page_height, callback, boundary_callback=None, line_type=None, is_modified=False, table=None):
        super().__init__(x1, y1, x2, y2)
        self.orientation = orientation
        self.callback = callback
        self.boundary_callback = boundary_callback
        self.line_type = line_type
        self.page_width = page_width
        self.page_height = page_height
        self.is_modified = is_modified
        self.table = table
        self.is_being_dragged = False
        
        self.setFlag(QGraphicsLineItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsLineItem.ItemIsMovable, True)
        self.setFlag(QGraphicsLineItem.ItemSendsGeometryChanges, True)
        
        self.update_appearance()
        self.setCursor(Qt.SizeVerCursor if orientation == 'horizontal' else Qt.SizeHorCursor)

    def set_modified(self, modified):
        if self.is_modified != modified:
            self.is_modified = modified
            self.update_appearance()

    def update_appearance(self):
        colors = {
            'start': QColor(0, 255, 0),
            'end': QColor(255, 0, 0),
            'divider': QColor(0, 0, 255),
            'selector': QColor(128, 128, 128)
        }
        color = colors.get(self.line_type, QColor(0, 0, 0))
        if self.is_modified:
            if self.line_type == 'start': color = QColor(50, 200, 50)
            elif self.line_type == 'end': color = QColor(200, 50, 50)
            elif self.line_type == 'divider': color = QColor(50, 50, 200)
            width = 8
        else:
            width = 5
        pen = QPen(color)
        pen.setWidth(width)
        if self.line_type == 'selector': pen.setStyle(Qt.DotLine)
        self.setPen(pen)

    def itemChange(self, change, value):
        if change == QGraphicsLineItem.ItemPositionChange:
            new_pos = value
            if self.orientation == 'horizontal':
                new_pos.setX(0)
                new_y = self.line().y1() + new_pos.y()
                if new_y < 0: new_pos.setY(-self.line().y1())
                elif new_y > self.page_height: new_pos.setY(self.page_height - self.line().y1())
            else:
                new_pos.setY(0)
                new_x = self.line().x1() + new_pos.x()
                if new_x < 0: new_pos.setX(-self.line().x1())
                elif new_x > self.page_width: new_pos.setX(self.page_width - self.line().x1())
            return new_pos
        elif change == QGraphicsLineItem.ItemPositionHasChanged:
            # Only trigger callback on explicit position change to avoid recursive loops/deletion
            if self.orientation == 'horizontal':
                current_val = self.line().y1() + self.pos().y()
            else:
                current_val = self.line().x1() + self.pos().x()
            self.callback(current_val)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_being_dragged = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_being_dragged = False
        super().mouseReleaseEvent(event)
        if self.orientation == 'horizontal' and self.boundary_callback:
            y = self.line().y1() + self.pos().y()
            if y <= 0.1: self.boundary_callback(self.line_type, 'up')
            elif y >= self.page_height - 0.1: self.boundary_callback(self.line_type, 'down')

class InteractivePageView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.image_item = None
        self.start_lines = {}
        self.end_lines = {}
        self.divider_lines = {}
        self.static_divider = None
        self.selector_line = None
        self.on_selector_changed = None
        self.on_scroll_boundary = None

    def set_image(self, img_np: np.ndarray):
        self.scene.clear()
        if len(img_np.shape) == 2:
            h, w = img_np.shape; ch = 3
            img_rgb = np.stack((img_np,)*3, axis=-1)
        else:
            h, w, ch = img_np.shape; img_rgb = img_np
        bytes_per_line = ch * w
        format = QImage.Format_RGBA8888 if ch == 4 else QImage.Format_RGB888
        img_rgb = np.require(img_rgb, np.uint8, 'C')
        q_img = QImage(img_rgb.tobytes(), w, h, bytes_per_line, format).copy()
        pixmap = QPixmap.fromImage(q_img)
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.image_item)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.img_w, self.img_h = w, h
        self.start_lines, self.end_lines, self.divider_lines = {}, {}, {}
        self.static_divider, self.selector_line = None, None

    def add_start_line(self, table, y_pos, callback, boundary_callback, is_modified):
        line = DraggableLine(0, y_pos, self.img_w, y_pos, 'horizontal', self.img_w, self.img_h, 
                             lambda y, t=table: callback(y, t), 
                             lambda ltype, direction, t=table: boundary_callback(ltype, direction, t), 
                             'start', is_modified, table=table)
        self.scene.addItem(line); self.start_lines[table] = line

    def add_end_line(self, table, y_pos, callback, boundary_callback, is_modified):
        line = DraggableLine(0, y_pos, self.img_w, y_pos, 'horizontal', self.img_w, self.img_h, 
                             lambda y, t=table: callback(y, t), 
                             lambda ltype, direction, t=table: boundary_callback(ltype, direction, t), 
                             'end', is_modified, table=table)
        self.scene.addItem(line); self.end_lines[table] = line
        
    def add_divider_line(self, table, x_pos, callback, is_modified):
        line = DraggableLine(x_pos, 0, x_pos, self.img_h, 'vertical', self.img_w, self.img_h, 
                             lambda x, t=table: callback(x, t), line_type='divider', is_modified=is_modified, table=table)
        self.scene.addItem(line); self.divider_lines[table] = line

    def add_static_divider(self, x_pos):
        self.static_divider = QGraphicsLineItem(x_pos, 0, x_pos, self.img_h)
        pen = QPen(QColor(150, 150, 255, 150)); pen.setStyle(Qt.DashLine); pen.setWidth(2)
        self.static_divider.setPen(pen); self.scene.addItem(self.static_divider)

    def add_selector_line(self, y_pos, callback):
        self.on_selector_changed = callback
        self.selector_line = DraggableLine(0, y_pos, self.img_w, y_pos, 'horizontal', self.img_w, self.img_h, self._handle_selector_changed, line_type='selector')
        self.scene.addItem(self.selector_line)

    def _handle_selector_changed(self, y):
        if self.on_selector_changed: self.on_selector_changed(y)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            scene_pos = self.mapToScene(event.pos())
            y = scene_pos.y()
            if 0 <= y <= self.img_h and self.selector_line:
                self.selector_line.setPos(0, y - self.selector_line.line().y1())
                self._handle_selector_changed(y)
        super().mousePressEvent(event)
            
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            zoom_factor = 1.25 if event.angleDelta().y() > 0 else 1/1.25
            self.scale(zoom_factor, zoom_factor)
        else:
            v_bar = self.verticalScrollBar()
            delta = event.angleDelta().y()
            if delta < 0 and v_bar.value() == v_bar.maximum():
                if self.on_scroll_boundary: self.on_scroll_boundary('down')
            elif delta > 0 and v_bar.value() == v_bar.minimum():
                if self.on_scroll_boundary: self.on_scroll_boundary('up')
            super().wheelEvent(event)


class TableExtractionApp(QMainWindow):
    def __init__(self, pipeline, detected_tables):
        super().__init__()
        self.pipeline, self.detected_tables = pipeline, detected_tables
        self.original_tables = copy.deepcopy(detected_tables)
        self.current_page_idx, self.num_pages = 0, len(pipeline.pages)
        self.default_divider_x, self.selector_y = pipeline.config.divider_x, 100
        self.submitted = False
        self.active_drag_info = None
        self.init_ui()
        self.load_page(0)

    def init_ui(self):
        self.setWindowTitle("Table Extraction Review"); self.setGeometry(100, 100, 1200, 800)
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QHBoxLayout(main_widget)
        self.view = InteractivePageView(); main_layout.addWidget(self.view, stretch=3)
        self.view.on_scroll_boundary = self._handle_scroll_boundary
        control_panel = QWidget(); control_layout = QVBoxLayout(control_panel); main_layout.addWidget(control_panel, stretch=1)
        self.lbl_page = QLabel("Page: 1 / 1"); control_layout.addWidget(self.lbl_page)
        nav_layout = QHBoxLayout()
        btn_prev = QPushButton("Prev Page (A)"); btn_prev.clicked.connect(self.prev_page)
        btn_next = QPushButton("Next Page (D)"); btn_next.clicked.connect(self.next_page)
        nav_layout.addWidget(btn_prev); nav_layout.addWidget(btn_next); control_layout.addLayout(nav_layout)
        QShortcut(QKeySequence("A"), self, self.prev_page); QShortcut(QKeySequence("D"), self, self.next_page)
        QShortcut(QKeySequence("W"), self, self.prev_table); QShortcut(QKeySequence("S"), self, self.next_table)
        QShortcut(QKeySequence("R"), self, self.snap_nearest_end_to_selector)
        QShortcut(QKeySequence("Space"), self, self.add_table_at_selector)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_to_cache)
        jump_layout = QHBoxLayout(); jump_layout.addWidget(QLabel("Go to Page:"))
        self.txt_jump = QLineEdit(); self.txt_jump.setPlaceholderText("Page #"); self.txt_jump.returnPressed.connect(self.jump_to_page)
        btn_jump = QPushButton("Go"); btn_jump.clicked.connect(self.jump_to_page)
        jump_layout.addWidget(self.txt_jump); jump_layout.addWidget(btn_jump); control_layout.addLayout(jump_layout)
        control_layout.addSpacing(20); self.lbl_table_count = QLabel(f"Table: 0 / {len(self.detected_tables)}")
        control_layout.addWidget(self.lbl_table_count)
        tab_nav_layout = QHBoxLayout()
        btn_prev_tab = QPushButton("Prev Table (W)"); btn_prev_tab.clicked.connect(self.prev_table)
        btn_next_tab = QPushButton("Next Table (S)"); btn_next_tab.clicked.connect(self.next_table)
        tab_nav_layout.addWidget(btn_prev_tab); tab_nav_layout.addWidget(btn_next_tab); control_layout.addLayout(tab_nav_layout)
        control_layout.addSpacing(20); control_layout.addWidget(QLabel("Global Fallback Divider X:"))
        self.spin_divider = QSpinBox(); self.spin_divider.setRange(0, 3000); self.spin_divider.setValue(int(self.default_divider_x))
        self.spin_divider.valueChanged.connect(self.update_global_divider); control_layout.addWidget(self.spin_divider)
        control_layout.addSpacing(20); control_layout.addWidget(QLabel("Table Actions:"))
        btn_add_at_selector = QPushButton("Add New Table At Selector (Space)")
        btn_add_at_selector.setStyleSheet("background-color: #2196F3; color: white; padding: 5px; font-weight: bold;")
        btn_add_at_selector.clicked.connect(self.add_table_at_selector); control_layout.addWidget(btn_add_at_selector)
        btn_clear = QPushButton("Clear Tables from Page"); btn_clear.clicked.connect(self.clear_page_tables); control_layout.addWidget(btn_clear)
        btn_reset_page = QPushButton("Reset Changes on Page"); btn_reset_page.clicked.connect(self.reset_page_changes); control_layout.addWidget(btn_reset_page)
        control_layout.addSpacing(20); control_layout.addWidget(QLabel("Cache Actions:"))
        cache_layout = QHBoxLayout(); btn_save_cache = QPushButton("Save Changes (Ctrl+S)"); btn_save_cache.clicked.connect(self.save_to_cache)
        btn_restore_cache = QPushButton("Restore from Cache"); btn_restore_cache.clicked.connect(self.restore_from_cache)
        cache_layout.addWidget(btn_save_cache); cache_layout.addWidget(btn_restore_cache); control_layout.addLayout(cache_layout)
        control_layout.addStretch()
        btn_submit = QPushButton("Submit & Extract")
        btn_submit.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        btn_submit.clicked.connect(self.submit); control_layout.addWidget(btn_submit)

    def _capture_drag_state(self):
        grabber = self.view.scene.mouseGrabberItem()
        if isinstance(grabber, DraggableLine) and grabber.is_being_dragged:
            self.active_drag_info = (grabber.line_type, grabber.table)
        else:
            self.active_drag_info = None

    def _restore_drag_state(self):
        if self.active_drag_info:
            line_type, table = self.active_drag_info
            target_line = None
            if line_type == 'start': target_line = self.view.start_lines.get(table)
            elif line_type == 'end': target_line = self.view.end_lines.get(table)
            elif line_type == 'divider': target_line = self.view.divider_lines.get(table)
            elif line_type == 'selector': target_line = self.view.selector_line
            
            if target_line:
                # Snap it to mouse position immediately
                view_pos = self.view.mapFromGlobal(QCursor.pos())
                scene_pos = self.view.mapToScene(view_pos)
                if target_line.orientation == 'horizontal':
                    target_line.setPos(0, scene_pos.y() - target_line.line().y1())
                else:
                    target_line.setPos(scene_pos.x() - target_line.line().x1(), 0)
                
                target_line.is_being_dragged = True
                target_line.grabMouse()

    def load_page(self, page_idx):
        if page_idx < 0 or page_idx >= self.num_pages: return
        self.current_page_idx = page_idx
        self.lbl_page.setText(f"Page: {page_idx + 1} / {self.num_pages}")
        self.update_table_indicator()
        page = self.pipeline.pages[page_idx]
        self.view.set_image(page.get_processed_np())
        self.view.add_static_divider(self.default_divider_x)
        self.view.add_selector_line(self.selector_y, self.update_selector)
        for table in self._get_tables_on_page(page_idx):
            bounds = table.get_bounds(page_idx)
            if table.start_page_idx == page_idx:
                self.view.add_start_line(table, table.start_y_pos, self.update_start, self.handle_boundary, 'start_y_pos' in table.modified_properties)
            if table.end_page_idx == page_idx:
                self.view.add_end_line(table, table.end_y_pos, self.update_end, self.handle_boundary, 'end_y_pos' in table.modified_properties)
            div_x = bounds.divider_x if bounds.divider_x is not None else self.default_divider_x
            self.view.add_divider_line(table, div_x, self.update_divider, 'divider_x' in bounds.modified_properties)
        self._restore_drag_state()

    def update_table_indicator(self):
        curr = 0
        for i, t in enumerate(self.detected_tables):
            if t.start_page_idx <= self.current_page_idx <= (t.end_page_idx or self.num_pages): curr = i + 1; break
        if curr == 0:
            for i, t in enumerate(self.detected_tables):
                if t.start_page_idx > self.current_page_idx: curr = i + 1; break
        self.lbl_table_count.setText(f"Table: {curr} / {len(self.detected_tables)}")

    def jump_to_page(self):
        try:
            p = int(self.txt_jump.text()) - 1
            if 0 <= p < self.num_pages:
                self._capture_drag_state()
                self.load_page(p)
                self.txt_jump.clear()
            else: QMessageBox.warning(self, "Invalid Page", f"Between 1 and {self.num_pages}")
        except: pass

    def update_global_divider(self, val):
        self.default_divider_x = val; self.pipeline.config.divider_x = val; self.load_page(self.current_page_idx)

    def _get_tables_on_page(self, page_idx):
        return [t for t in self.detected_tables if t.start_page_idx <= page_idx and (t.end_page_idx is None or page_idx <= t.end_page_idx)]

    def handle_boundary(self, line_type, direction, table):
        if direction == 'up':
            if line_type == 'start' and table.start_page_idx > 0:
                table.start_page_idx -= 1; table.start_y_pos = self.pipeline.pages[table.start_page_idx].get_processed_np().shape[0] - 10
                table.modified_properties.add('start_y_pos'); self.load_page(table.start_page_idx)
            elif line_type == 'end' and table.end_page_idx > table.start_page_idx:
                table.end_page_idx -= 1; table.end_y_pos = self.pipeline.pages[table.end_page_idx].get_processed_np().shape[0] - 10
                table.modified_properties.add('end_y_pos'); self.load_page(table.end_page_idx)
        elif direction == 'down':
            if line_type == 'start' and (table.end_page_idx is None or table.start_page_idx < table.end_page_idx):
                table.start_page_idx += 1; table.start_y_pos = 10
                table.modified_properties.add('start_y_pos'); self.load_page(table.start_page_idx)
            elif line_type == 'end':
                if table.end_page_idx is not None and table.end_page_idx < self.num_pages - 1:
                    table.end_page_idx += 1; table.end_y_pos = 10; table.modified_properties.add('end_y_pos'); self.load_page(table.end_page_idx)
                elif table.end_page_idx is None:
                    table.end_page_idx = table.start_page_idx + 1; table.end_y_pos = 10; table.modified_properties.add('end_y_pos'); self.load_page(table.end_page_idx)

    def update_start(self, y, table):
        table.start_y_pos = y; table.get_bounds(table.start_page_idx).y_start = y
        table.modified_properties.add('start_y_pos')
        if table in self.view.start_lines: self.view.start_lines[table].set_modified(True)

    def update_end(self, y, table):
        table.end_y_pos = y; table.get_bounds(table.end_page_idx).y_end = y
        table.modified_properties.add('end_y_pos')
        if table in self.view.end_lines: self.view.end_lines[table].set_modified(True)

    def update_divider(self, x, table):
        b = table.get_bounds(self.current_page_idx); b.divider_x = x
        b.modified_properties.add('divider_x')
        if table in self.view.divider_lines: self.view.divider_lines[table].set_modified(True)

    def update_selector(self, y): self.selector_y = y

    def _handle_scroll_boundary(self, direction):
        if direction == 'up':
            if self.current_page_idx > 0:
                self.prev_page()
                # Scroll to bottom of the new page
                QTimer.singleShot(10, lambda: self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum()))
        elif direction == 'down':
            if self.current_page_idx < self.num_pages - 1:
                self.next_page()
                # Scroll to top of the new page
                QTimer.singleShot(10, lambda: self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().minimum()))

    def snap_nearest_end_to_selector(self):
        best_table = None
        best_pos = (-1, -1)
        
        for t in self.detected_tables:
            if t.end_page_idx is None: continue
            
            # End line is "above" selector if on previous page OR same page and smaller Y
            is_above = (t.end_page_idx < self.current_page_idx) or \
                       (t.end_page_idx == self.current_page_idx and t.end_y_pos < self.selector_y)
            
            if is_above:
                # We want the one nearest to current (largest end_page_idx, then largest end_y_pos)
                if (t.end_page_idx > best_pos[0]) or \
                   (t.end_page_idx == best_pos[0] and t.end_y_pos > best_pos[1]):
                    best_table = t
                    best_pos = (t.end_page_idx, t.end_y_pos)
        
        if best_table:
            # Clear old bound if it exists
            if best_table.end_page_idx in best_table.page_bounds:
                best_table.page_bounds[best_table.end_page_idx].y_end = None
            
            best_table.end_page_idx = self.current_page_idx
            best_table.end_y_pos = self.selector_y
            best_table.get_bounds(self.current_page_idx).y_end = self.selector_y
            best_table.modified_properties.add('end_y_pos')
            self.load_page(self.current_page_idx)

    def prev_page(self):
        self._capture_drag_state()
        self.load_page(self.current_page_idx - 1)

    def next_page(self):
        self._capture_drag_state()
        self.load_page(self.current_page_idx + 1)

    def prev_table(self):
        tp = -1
        for i in range(len(self.detected_tables)-1, -1, -1):
            if self.detected_tables[i].start_page_idx < self.current_page_idx: tp = self.detected_tables[i].start_page_idx; break
        if tp >= 0:
            self._capture_drag_state()
            self.load_page(tp)

    def next_table(self):
        tp = -1
        for t in self.detected_tables:
            if t.start_page_idx > self.current_page_idx: tp = t.start_page_idx; break
        if tp >= 0:
            self._capture_drag_state()
            self.load_page(tp)

    def add_table_at_selector(self):
        from src.table_detection import find_table_end
        ep, ey = find_table_end(self.pipeline, self.current_page_idx, self.selector_y)
        if ep is None: ep, ey = self.current_page_idx, self.view.img_h - 100
        new_t = DetectedTable(os.path.splitext(self.pipeline.file_name)[0], self.current_page_idx, self.selector_y, ep, ey)
        new_t.modified_properties.update(['start_y_pos', 'end_y_pos']); self.detected_tables.append(new_t)
        self.detected_tables.sort(key=lambda x: x.start_page_idx); self.load_page(self.current_page_idx)

    def clear_page_tables(self):
        rem = []
        for t in self.detected_tables:
            if t.start_page_idx == self.current_page_idx and t.end_page_idx == self.current_page_idx: rem.append(t)
            elif t.start_page_idx == self.current_page_idx: t.start_page_idx += 1; t.start_y_pos = 0; t.modified_properties.add('start_y_pos')
            elif t.end_page_idx == self.current_page_idx: t.end_page_idx -= 1; t.modified_properties.add('end_y_pos')
        for t in rem: self.detected_tables.remove(t)
        self.load_page(self.current_page_idx)

    def reset_page_changes(self):
        for t in self._get_tables_on_page(self.current_page_idx):
            t.modified_properties.clear()
            for b in t.page_bounds.values(): b.modified_properties.clear()
            if self.current_page_idx in t.page_bounds: t.page_bounds[self.current_page_idx].divider_x = None
        self.load_page(self.current_page_idx)

    def get_cache_path(self):
        base = os.path.splitext(self.pipeline.file_name)[0]
        path = os.path.join(self.pipeline.config.output_dir, f"{base}-cache")
        os.makedirs(path, exist_ok=True); return os.path.join(path, "gui_table_cache.json")

    def save_to_cache(self):
        data = {"global_divider_x": self.default_divider_x, "tables": []}
        for t in self.detected_tables:
            td = {"document": t.document, "start_page_idx": t.start_page_idx, "start_y_pos": t.start_y_pos, "end_page_idx": t.end_page_idx, "end_y_pos": t.end_y_pos, "modified_properties": list(t.modified_properties), "page_bounds": {}}
            for pi, b in t.page_bounds.items(): td["page_bounds"][str(pi)] = {"y_start": b.y_start, "y_end": b.y_end, "divider_x": b.divider_x, "modified_properties": list(b.modified_properties)}
            data["tables"].append(td)
        with open(self.get_cache_path(), 'w') as f: json.dump(data, f, indent=2)
        QMessageBox.information(self, "Success", "Saved to cache.")

    def restore_from_cache(self):
        cp = self.get_cache_path()
        if not os.path.exists(cp): return
        with open(cp, 'r') as f: data = json.load(f)
        self.default_divider_x = data.get("global_divider_x", self.default_divider_x)
        self.spin_divider.setValue(int(self.default_divider_x)); self.pipeline.config.divider_x = self.default_divider_x
        self.detected_tables = []
        for td in data["tables"]:
            t = DetectedTable(td["document"], td["start_page_idx"], td["start_y_pos"], td["end_page_idx"], td["end_y_pos"])
            t.modified_properties = set(td.get("modified_properties", []))
            for pi_s, bd in td["page_bounds"].items():
                b = t.get_bounds(int(pi_s)); b.y_start, b.y_end, b.divider_x = bd["y_start"], bd["y_end"], bd["divider_x"]
                b.modified_properties = set(bd.get("modified_properties", []))
            self.detected_tables.append(t)
        self.load_page(self.current_page_idx)

    def submit(self):
        if QMessageBox.question(self, 'Submit', 'Run extraction?', QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes: self.submitted = True; self.close()

def run_gui(pipeline, detected_tables):
    app = QApplication(sys.argv); window = TableExtractionApp(pipeline, detected_tables); window.show(); app.exec_()
    return window.detected_tables if window.submitted else None
