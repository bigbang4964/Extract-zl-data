import os
import shutil
import sqlite3
from pathlib import Path
import pandas as pd
import threading

# UI hiện đại dựa trên ttkbootstrap
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox

# Thư mục tạm để copy database (tránh bị khóa khi Zalo đang chạy)
TEMP_DIR = Path("temp_zalo_db")


# -----------------------------
# HÀM TIỆN ÍCH
# -----------------------------
def prepare_db_copy(db_file: Path) -> Path:
    """
    Tạo bản copy database và các file đi kèm (.db-wal, .db-shm)
    để tránh lỗi locked khi đọc dữ liệu trực tiếp từ Zalo.
    """
    TEMP_DIR.mkdir(exist_ok=True)
    dst_db = TEMP_DIR / db_file.name
    shutil.copy2(db_file, dst_db)  # copy file .db chính

    # copy thêm file .db-wal và .db-shm nếu có
    wal = Path(str(db_file) + "-wal")
    shm = Path(str(db_file) + "-shm")
    if wal.exists():
        shutil.copy2(wal, TEMP_DIR / wal.name)
    if shm.exists():
        shutil.copy2(shm, TEMP_DIR / shm.name)

    return dst_db


def list_tables(db_file: Path):
    """
    Liệt kê tất cả tên bảng trong một file SQLite.
    """
    db_copy = prepare_db_copy(db_file)
    conn = sqlite3.connect(f'file:{db_copy}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return tables


# -----------------------------
# LỚP ỨNG DỤNG CHÍNH
# -----------------------------
class ZaloExtractorApp:
    def __init__(self, master: tb.Window):
        self.master = master
        master.title("📂 Zalo PC Data Extractor")
        master.geometry("900x600")

        self.selected_dir = None     # thư mục Zalo được chọn
        self.tables_index = []       # lưu danh sách (file, bảng)

        # style an toàn
        self.style = tb.Style()

        # --- FRAME CHỨC NĂNG ---
        top_frame = tb.LabelFrame(master, text="Thao tác", padding=10, bootstyle="primary")
        top_frame.pack(fill=X, padx=10, pady=10)

        # Nút chọn thư mục Zalo
        self.btn_select = tb.Button(top_frame, text="📁 Chọn thư mục ZaloPC", bootstyle="info", command=self.choose_dir)
        self.btn_select.pack(side=LEFT, padx=5)

        # Nút quét dữ liệu
        self.btn_scan = tb.Button(top_frame, text="🔍 Quét dữ liệu", bootstyle="success", command=self.scan_dir)
        self.btn_scan.pack(side=LEFT, padx=5)

        # --- FRAME DANH SÁCH BẢNG ---
        table_frame = tb.LabelFrame(master, text="Danh sách bảng dữ liệu", padding=10, bootstyle="secondary")
        table_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # Treeview hiển thị danh sách file.db và bảng
        self.tree = tb.Treeview(table_frame, columns=("file", "table"), show="headings", bootstyle="info")
        self.tree.heading("file", text="File")
        self.tree.heading("table", text="Bảng")
        self.tree.pack(fill=BOTH, expand=True)

        # Thanh cuộn dọc
        scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=self.tree.yview, bootstyle="round")
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Double-click vào bảng để xem preview
        self.tree.bind("<Double-1>", self.preview_table_event)

        # --- FRAME ĐỔI GIAO DIỆN ---
        switch_frame = tb.Frame(master)
        switch_frame.pack(fill=X, pady=5)
        tb.Button(switch_frame, text="🌞 / 🌙 Đổi theme", bootstyle="warning", command=self.toggle_theme).pack(side=RIGHT, padx=10)

    # -----------------------------
    # CHỨC NĂNG UI
    # -----------------------------
    def toggle_theme(self):
        """Đổi theme giữa sáng và tối."""
        current = self.style.theme_use()
        new_theme = "darkly" if current not in ("darkly", "cyborg", "superhero") else "litera"
        self.style.theme_use(new_theme)

    def choose_dir(self):
        """Mở hộp thoại chọn thư mục ZaloPC thủ công."""
        d = filedialog.askdirectory(title="Chọn thư mục ZaloPC")
        if d:
            self.selected_dir = Path(d)
            messagebox.showinfo("Chọn thư mục", f"✅ Đã chọn: {d}")

    def scan_dir(self):
        """
        Quét toàn bộ thư mục ZaloData để tìm file SQLite (.db).
        Chỉ liệt kê bảng 'info-cache' nếu có và auto-preview luôn.
        """
        if not self.selected_dir:
            messagebox.showwarning("Chưa chọn thư mục", "⚠ Hãy chọn thư mục ZaloPC trước.")
            return

        # Xóa dữ liệu cũ trong treeview
        self.tree.delete(*self.tree.get_children())
        self.tables_index.clear()

        found_item = None

        # Quét tất cả file *.db
        for f in self.selected_dir.rglob("*"):
            if f.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
                try:
                    tables = list_tables(f)
                    if "info-cache" in tables:
                        self.tables_index.append((f, "info-cache"))
                        self.tree.insert("", "end", values=(f.name, "info-cache"))
                        found_item = (f, "info-cache")
                        break  # dừng ngay khi tìm thấy
                except Exception as e:
                    print(f"[ERR] {f}: {e}")

        # Auto open preview
        if found_item:
            f, t = found_item
            # gọi method của instance
            self.master.after(300, lambda: self.preview_table_by_name(f, t))
        else:
            messagebox.showinfo("Kết quả", "❌ Không tìm thấy bảng 'info-cache'.")

    def preview_table_by_name(self, db_file: Path, table: str):
        """
        Mở trực tiếp preview theo file và bảng.
        Đây là method (không phải function ngoài).
        """
        preview_win = tb.Toplevel(self.master)
        preview_win.title(f"👀 Preview {db_file.name}:{table}")
        preview_win.geometry("1000x700")

        label_status = tb.Label(preview_win, text="⏳ Đang tải dữ liệu, vui lòng đợi...")
        label_status.pack(pady=10)
        pb = tb.Progressbar(preview_win, mode="indeterminate", bootstyle="info-striped")
        pb.pack(fill=X, padx=20, pady=5)
        pb.start()

        frame_data = tb.Frame(preview_win)
        frame_data.pack(fill=BOTH, expand=True)

        def load_data():
            try:
                db_copy = prepare_db_copy(db_file)
                conn = sqlite3.connect(f'file:{db_copy}?mode=ro', uri=True)
                df = pd.read_sql_query(f"SELECT * FROM \"{table}\"", conn)
                conn.close()

                def show_data():
                    label_status.destroy()
                    pb.stop()
                    pb.destroy()

                    # --- Search box ---
                    search_frame = tb.Frame(preview_win)
                    search_frame.pack(fill=X, padx=5, pady=5)
                    tb.Label(search_frame, text="🔎 Tìm kiếm:").pack(side=LEFT)
                    search_var = tb.StringVar()
                    search_entry = tb.Entry(search_frame, textvariable=search_var, bootstyle="info")
                    search_entry.pack(side=LEFT, fill=X, expand=True, padx=5)

                    # --- Treeview ---
                    cols = list(df.columns)
                    tree = tb.Treeview(frame_data, columns=cols, show="headings", bootstyle="primary")
                    for c in cols:
                        tree.heading(c, text=c)
                        tree.column(c, width=160, anchor="w", stretch=True)
                    tree.pack(fill=BOTH, expand=True)

                    sb = tb.Scrollbar(frame_data, orient="vertical", command=tree.yview, bootstyle="round")
                    tree.configure(yscroll=sb.set)
                    sb.pack(side=RIGHT, fill=Y)

                    def update_tree(dataframe):
                        tree.delete(*tree.get_children())
                        for _, row in dataframe.iterrows():
                            # convert nan -> empty string to avoid issues
                            vals = [("" if pd.isna(x) else x) for x in row.tolist()]
                            tree.insert("", "end", values=vals)

                    update_tree(df)

                    def do_search(*args):
                        q = search_var.get().lower()
                        if q:
                            filtered = df[df.apply(lambda r: r.astype(str).str.lower().str.contains(q).any(), axis=1)]
                        else:
                            filtered = df
                        update_tree(filtered)

                    # trace_add hiện tại chỉ có trên Python 3.6+; nếu lỗi bạn có thể dùng trace("w", ...)
                    try:
                        search_var.trace_add("write", do_search)
                    except Exception:
                        search_var.trace("w", lambda *a: do_search())

                    # Export
                    frame_export = tb.Frame(preview_win)
                    frame_export.pack(pady=5)
                    tb.Button(frame_export, text="💾 Xuất CSV", bootstyle="success",
                              command=lambda: self.export_df(df, "csv", db_file.name, table)).pack(side=LEFT, padx=5)
                    tb.Button(frame_export, text="💾 Xuất Excel", bootstyle="info",
                              command=lambda: self.export_df(df, "excel", db_file.name, table)).pack(side=LEFT, padx=5)

                # Hiển thị dữ liệu trong main thread
                self.master.after(0, show_data)
            except Exception as e:
                self.master.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
            finally:
                # đảm bảo progress dừng nếu có lỗi trước khi show_data
                try:
                    self.master.after(0, pb.stop)
                except Exception:
                    pass

        threading.Thread(target=load_data, daemon=True).start()

    def preview_table_event(self, event):
        """
        Xem trước dữ liệu khi double-click vào một bảng trong treeview.
        """
        item = self.tree.focus()
        if not item:
            return
        fname, table = self.tree.item(item, "values")

        # Tìm lại đường dẫn file .db từ self.tables_index
        db_path = None
        for f, t in self.tables_index:
            if f.name == fname and t == table:
                db_path = f
                break
        if not db_path:
            messagebox.showwarning("Lỗi", "Không tìm thấy file tương ứng trong index.")
            return

        self.preview_table_by_name(db_path, table)

    def export_df(self, df, fmt, fname, table):
        """
        Xuất toàn bộ DataFrame ra CSV hoặc Excel.
        """
        file = filedialog.asksaveasfilename(
            defaultextension=".csv" if fmt == "csv" else ".xlsx",
            filetypes=[("CSV", "*.csv")] if fmt == "csv" else [("Excel", "*.xlsx")],
            initialfile=f"{fname}__{table}"
        )
        if not file:
            return
        try:
            if fmt == "csv":
                df.to_csv(file, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(file, index=False)
            messagebox.showinfo("Xuất thành công", f"✅ Đã lưu {file}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))


# -----------------------------
# MAIN APP
# -----------------------------
if __name__ == "__main__":
    root = tb.Window(themename="litera")  # theme sáng mặc định

    app = ZaloExtractorApp(root)

    # 🔹 Auto detect thư mục ZaloData nếu chạy Windows
    if os.name == "nt":
        try:
            user = os.getlogin()
        except Exception:
            # fallback nếu không lấy được login name
            user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        zalo_path = Path(f"C:/Users/{user}/AppData/Roaming/ZaloData")
        if zalo_path.exists():
            app.selected_dir = zalo_path
            # gọi scan trong mainloop sau 300ms để GUI khởi tạo xong
            root.after(300, app.scan_dir)
        else:
            messagebox.showwarning("Zalo chưa cài đặt", "⚠ Không tìm thấy thư mục ZaloData.\nVui lòng cài đặt hoặc đăng nhập Zalo PC.")

    root.mainloop()
