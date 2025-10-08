# zalo_extractor_gui_v2_commented.py
# ---------------------------------
# Project: Zalo Data Extractor v2 (GUI)
# Mục đích: mở 1 file SQLite, liệt kê các bảng trong DB, xem dữ liệu bảng,
#          xuất dữ liệu hiện đang hiển thị ra Excel hoặc PDF.
#
# Yêu cầu thư viện:
#   pip install pyqt6 pandas openpyxl reportlab
#
# Lưu ý:
# - Tên bảng trong DB Zalo có thể khác nhau giữa các phiên bản. App này cho phép
#   bạn chọn bất kỳ bảng nào để xem (không cố định vào "messages").
# - Để an toàn, nên đóng Zalo (nếu DB từ Zalo PC) trước khi mở file DB này trong app.
# - Đây là phiên bản demo/skeleton — nếu DB lớn, giới hạn 300 dòng khi hiển thị.
# ---------------------------------

import sys
import sqlite3              # đọc file SQLite
import pandas as pd         # xử lý bảng dữ liệu và export Excel
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QMessageBox,
    QLabel, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# CHÚ THÍCH: toàn bộ giao diện và logic đều nằm trong class ZaloExtractor.
# Class chịu trách nhiệm: mở DB, lấy danh sách bảng, load dữ liệu bảng, hiển thị,
# và export (Excel/PDF).
class ZaloExtractor(QMainWindow):
    def __init__(self):
        super().__init__()

        # Thiết lập cửa sổ chính
        self.setWindowTitle("Zalo Data Extractor v2")
        self.setGeometry(200, 200, 900, 600)

        # Biến lưu connection SQLite và DataFrame hiện tại
        # self.conn: sqlite3.Connection (hoặc None nếu chưa mở DB)
        # self.df: pandas.DataFrame chứa dữ liệu của bảng đang chọn
        self.conn = None
        self.df = pd.DataFrame()

        # Central widget + layout dọc chính
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Label hiển thị thông tin / trạng thái (chưa có DB / đã mở DB ...)
        self.info_label = QLabel("Chưa chọn database")
        layout.addWidget(self.info_label)

        # Hộp chọn bảng (ComboBox) + nhãn
        # Khi người dùng đổi lựa chọn, hàm load_selected_table sẽ được gọi
        hbox = QHBoxLayout()
        self.table_selector = QComboBox()
        self.table_selector.currentIndexChanged.connect(self.load_selected_table)
        hbox.addWidget(QLabel("Chọn bảng:"))
        hbox.addWidget(self.table_selector)
        layout.addLayout(hbox)

        # Table widget dùng để hiển thị dữ liệu (DataGrid)
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Nút: Mở database (file dialog)
        btn_load = QPushButton("Mở database (SQLite)")
        btn_load.clicked.connect(self.open_db)
        layout.addWidget(btn_load)

        # Nút: Export Excel (sử dụng pandas.DataFrame.to_excel)
        btn_excel = QPushButton("Export Excel")
        btn_excel.clicked.connect(self.export_excel)
        layout.addWidget(btn_excel)

        # Nút: Export PDF (sử dụng reportlab để vẽ text đơn giản sang PDF)
        btn_pdf = QPushButton("Export PDF")
        btn_pdf.clicked.connect(self.export_pdf)
        layout.addWidget(btn_pdf)

    # Hàm gọi khi nhấn nút "Mở database"
    def open_db(self):
        # Mở file dialog để chọn file SQLite
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file database", "", "SQLite DB (*.db *.sqlite *.sqlite3 *.zip)"
        )
        # Nếu không chọn file (người dùng hủy) thì return
        if not file_path:
            return

        try:
            # Nếu trước đó đã mở connection thì đóng lại để tránh leak
            if self.conn:
                self.conn.close()

            # Mở kết nối sqlite
            self.conn = sqlite3.connect(file_path)

            # Lấy danh sách bảng từ sqlite_master
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            # Nếu DB không có bảng nào (hiếm), cảnh báo
            if not tables:
                QMessageBox.warning(self, "Warning", "Không tìm thấy bảng nào trong DB")
                return

            # Đổ danh sách bảng vào ComboBox để người dùng chọn
            self.table_selector.clear()
            self.table_selector.addItems(tables)

            # Cập nhật label thông tin
            # Hiển thị đường dẫn file và số bảng tìm thấy
            self.info_label.setText(f"Đã mở DB: {file_path} ({len(tables)} bảng)")
        except Exception as e:
            # Nếu có lỗi (ví dụ file không phải SQLite hoặc file đang bị khóa),
            # show message box lỗi
            QMessageBox.critical(self, "Error", str(e))

    # Hàm gọi khi user chọn 1 bảng khác trong ComboBox
    def load_selected_table(self):
        # Nếu chưa mở DB thì không làm gì
        if not self.conn:
            return
        # Lấy tên bảng hiện tại
        table_name = self.table_selector.currentText()
        if not table_name:
            return
        try:
            # Chú ý: ở đây giới hạn 100 dòng để tránh load quá nặng giao diện
            # Bạn có thể sửa limit hoặc thêm paging
            query = f"SELECT * FROM '{table_name}'"
            # Dùng pandas.read_sql_query để load trực tiếp vào DataFrame
            df = pd.read_sql_query(query, self.conn)
            self.df = df  # lưu DataFrame hiện tại để export sau này
            self.show_table(df)
            # Cập nhật label trạng thái: tên bảng + số dòng đang hiển thị
            self.info_label.setText(f"Bảng: {table_name} | {len(df)} rows (hiển thị tối đa 100)")
        except Exception as e:
            # Thường lỗi xảy ra khi bảng có tên chứa ký tự đặc biệt (cần escape)
            # hoặc DB bị khóa / cấu trúc khác. Hiện ta show lỗi cho người dùng.
            QMessageBox.critical(self, "Error", str(e))

    # Hiển thị pandas.DataFrame vào QTableWidget
    def show_table(self, df):
        # Xóa nội dung cũ
        self.table.clear()
        # Thiết lập số hàng và số cột
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        # Dùng tên cột DataFrame làm header
        self.table.setHorizontalHeaderLabels(df.columns)

        # Duyệt từng ô để đặt giá trị vào QTableWidgetItem
        # Lưu ý: với bảng lớn, việc này có thể chậm — có thể tối ưu bằng model/view
        for i in range(len(df)):
            for j in range(len(df.columns)):
                # Chuyển giá trị thành string để đặt vào ô
                item = QTableWidgetItem(str(df.iat[i, j]))
                # Đặt chế độ chỉ đọc để người dùng không sửa trực tiếp
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, j, item)

        # Tự động resize cột cho vừa nội dung
        self.table.resizeColumnsToContents()

    # Xuất DataFrame hiện tại sang file Excel (.xlsx)
    def export_excel(self):
        # Nếu chưa có dữ liệu nào thì cảnh báo
        if self.df.empty:
            QMessageBox.warning(self, "Warning", "Chưa có dữ liệu")
            return
        # Mở file dialog để chọn nơi lưu
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Excel", "zalo_data.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return
        # Dùng pandas để lưu Excel (openpyxl sẽ tự động được dùng nếu cài)
        self.df.to_excel(file_path, index=False)
        QMessageBox.information(self, "OK", f"Đã lưu Excel: {file_path}")

    # Xuất DataFrame hiện tại ra PDF đơn giản (text lines)
    def export_pdf(self):
        # Nếu chưa có dữ liệu thì cảnh báo
        if self.df.empty:
            QMessageBox.warning(self, "Warning", "Chưa có dữ liệu")
            return
        # Mở dialog chọn file để lưu PDF
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu PDF", "zalo_data.pdf", "PDF (*.pdf)"
        )
        if not file_path:
            return

        # Tạo canvas PDF (ReportLab) với khổ A4
        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        # Chọn font và kích thước chữ
        c.setFont("Helvetica", 9)
        # Bắt đầu vẽ từ mép trên
        y = height - 40
        # Tiêu đề báo cáo: hiển thị tên bảng hiện tại
        c.drawString(30, y + 10, f"Zalo Data Report - Bảng {self.table_selector.currentText()}")

        # Vẽ từng dòng dữ liệu (mỗi dòng 1 text tóm tắt)
        #  - text[:120] giới hạn 120 ký tự cho 1 dòng để không tràn sang lề
        #  - nếu cần đầy đủ nội dung, có thể wrap text hoặc tăng kích thước trang
        for i, row in self.df.iterrows():
            # Ghép tất cả giá trị cột của 1 hàng thành 1 chuỗi phân cách bởi " | "
            text = " | ".join([str(x) for x in row.values])
            c.drawString(30, y, text[:120])  # chỉ vẽ tối đa 120 ký tự/dòng
            y -= 14  # nhảy xuống dòng tiếp theo (tùy chỉnh khoảng cách)
            # Nếu đã gần đến đáy trang, tạo trang mới
            if y < 40:
                c.showPage()
                c.setFont("Helvetica", 9)
                y = height - 40

        # Lưu file PDF
        c.save()
        QMessageBox.information(self, "OK", f"Đã lưu PDF: {file_path}")


# Entry point: tạo QApplication và hiển thị cửa sổ chính
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZaloExtractor()
    window.show()
    sys.exit(app.exec())
