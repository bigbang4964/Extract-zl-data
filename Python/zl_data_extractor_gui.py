import os
import shutil
import sqlite3
from pathlib import Path
import pandas as pd
import threading
import json
import re
import requests
from io import BytesIO
from PIL import Image, ImageTk

import ttkbootstrap as tb
import tkinter as tk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox

# Thư mục tạm để copy file SQLite (tránh khóa file khi Zalo đang chạy)
TEMP_DIR = Path("temp_zalo_db")


# -----------------------------
# HÀM TIỆN ÍCH
# -----------------------------
def prepare_db_copy(db_file: Path) -> Path:
    """
    Copy file DB và các file liên quan (-wal, -shm) sang thư mục tạm để mở chế độ read-only
    Tránh tình trạng SQLite bị khóa khi Zalo đang sử dụng.
    """
    TEMP_DIR.mkdir(exist_ok=True)
    dst_db = TEMP_DIR / db_file.name
    shutil.copy2(db_file, dst_db)
    for ext in ["-wal", "-shm"]:
        f = Path(str(db_file) + ext)
        if f.exists():
            shutil.copy2(f, TEMP_DIR / f.name)
    return dst_db


def list_tables(db_file: Path):
    """Liệt kê danh sách bảng trong file SQLite DB"""
    db_copy = prepare_db_copy(db_file)
    conn = sqlite3.connect(f'file:{db_copy}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return tables


def extract_first_id(obj):
    """
    Trích xuất UID đầu tiên (chuỗi số >= 10 ký tự) từ JSON config
    Duyệt đệ quy trong dict, list, string
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.isdigit() and len(k) >= 10:
                return k
            res = extract_first_id(v)
            if res:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = extract_first_id(item)
            if res:
                return res
    elif isinstance(obj, str):
        match = re.search(r"\b\d{10,}\b", obj)
        if match:
            return match.group(0)
        try:
            nested = json.loads(obj)
            return extract_first_id(nested)
        except Exception:
            pass
    return None


# -----------------------------
# ỨNG DỤNG CHÍNH
# -----------------------------
class ZaloExtractorApp:
    def __init__(self, master: tb.Window):
        # Khởi tạo cửa sổ chính
        self.master = master
        master.title("📂 Zalo PC Data Extractor")
        master.geometry("1100x700")

        # Biến lưu trữ
        self.selected_dir = None       # thư mục ZaloData
        self.uid = None                # UID tài khoản
        self.avatar_img = None         # ảnh avatar chính
        self.avatar_cache = {}         # cache avatar của bạn bè
        self.message_arr = {}          # lưu trữ danh sách file Message DB đã quét

        self.style = tb.Style()

        # --- Notebook (tab) ---
        self.notebook = tb.Notebook(master, bootstyle="primary")
        self.notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # Tab 1: thao tác chính
        self.main_tab = tb.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Message DB")

        # Tab 2: danh bạ (info-cache)
        self.info_tab = tb.Frame(self.notebook)
        self.notebook.add(self.info_tab, text="Danh bạ (Info-cache)")

        # ========== NỘI DUNG TAB 1 ==========
        # Nhóm button thao tác
        top_frame = tb.LabelFrame(self.main_tab, text="Thao tác", padding=10, bootstyle="primary")
        top_frame.pack(fill=X, padx=10, pady=10)

        # Nút chọn thư mục
        self.btn_select = tb.Button(top_frame, text="📁 Chọn thư mục ZaloPC",
                                    bootstyle="info", command=self.choose_dir)
        self.btn_select.pack(side=LEFT, padx=5)

        # Nút quét dữ liệu
        self.btn_scan = tb.Button(top_frame, text="🔍 Quét dữ liệu",
                                  bootstyle="success", command=self.scan_dir)
        self.btn_scan.pack(side=LEFT, padx=5)

        # Nút đổi theme sáng/tối
        tb.Button(top_frame, text="🌞 / 🌙 Đổi theme",
                  bootstyle="warning", command=self.toggle_theme).pack(side=RIGHT, padx=10)

        # Khung hiển thị UID + info
        uid_frame = tb.LabelFrame(self.main_tab, text="UID / Info", padding=10, bootstyle="secondary")
        uid_frame.pack(fill=X, padx=10, pady=5)

        self.uid_var = tb.StringVar()
        tb.Entry(uid_frame, textvariable=self.uid_var, state="readonly").pack(fill=X, padx=5, pady=2)

        self.zname_var = tb.StringVar()
        tb.Entry(uid_frame, textvariable=self.zname_var, state="readonly").pack(fill=X, padx=5, pady=2)

        self.avatar_label = tb.Label(uid_frame, text="(Avatar sẽ hiển thị ở đây)")
        self.avatar_label.pack(pady=5)

        # Khung hiển thị danh sách file Message DB
        msg_frame = tb.LabelFrame(self.main_tab, text="Message DB Files", padding=10, bootstyle="secondary")
        msg_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.tree = tb.Treeview(msg_frame, columns=("file",), show="headings", bootstyle="info")
        self.tree.heading("file", text="File")
        self.tree.pack(fill=BOTH, expand=True)

        sb = tb.Scrollbar(msg_frame, orient="vertical", command=self.tree.yview, bootstyle="round")
        self.tree.configure(yscroll=sb.set)
        sb.pack(side=RIGHT, fill=Y)

        # Double-click vào file để mở DB
        self.tree.bind("<Double-1>", self.open_message_db)

        # ========== NỘI DUNG TAB 2 ==========
        # Cột trái: danh sách info-cache
        left = tb.Frame(self.info_tab)
        left.pack(side=LEFT, fill=Y, padx=5, pady=5)

        self.cache_tree = tb.Treeview(left, columns=("key", "name"), show="headings", bootstyle="info")
        self.cache_tree.heading("key", text="Key")
        self.cache_tree.heading("name", text="Tên (zName)")
        self.cache_tree.column("key", width=180)
        self.cache_tree.column("name", width=200)
        self.cache_tree.pack(fill=Y, expand=True)

        sb2 = tb.Scrollbar(left, orient="vertical", command=self.cache_tree.yview, bootstyle="round")
        self.cache_tree.configure(yscroll=sb2.set)
        sb2.pack(side=RIGHT, fill=Y)

        self.cache_tree.bind("<<TreeviewSelect>>", self.on_select_cache)

        # Cột phải: chi tiết info-cache
        right = tb.Frame(self.info_tab)
        right.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=5)

        self.avatar_canvas = tk.Canvas(right, width=120, height=120, bg="lightgray")
        self.avatar_canvas.pack(pady=10)
        self.avatar_canvas.create_text(60, 60, text="(Avatar)")

        self.zname_var2 = tb.StringVar()
        self.key_var2 = tb.StringVar()

        tb.Label(right, text="Tên:").pack(anchor=W)
        tb.Entry(right, textvariable=self.zname_var2, state="readonly").pack(fill=X, padx=5)

        tb.Label(right, text="UID:").pack(anchor=W)
        tb.Entry(right, textvariable=self.key_var2, state="readonly").pack(fill=X, padx=5)

        tb.Label(right, text="JSON raw:").pack(anchor=W)
        self.json_text = tb.Text(right, height=12)
        self.json_text.pack(fill=BOTH, expand=True, padx=5, pady=5)

    # -----------------------------
    # Đổi theme sáng/tối
    def toggle_theme(self):
        current = self.style.theme_use()
        new_theme = "darkly" if current not in ("darkly", "cyborg", "superhero") else "litera"
        self.style.theme_use(new_theme)

    # Chọn thư mục ZaloData
    def choose_dir(self):
        d = filedialog.askdirectory(title="Chọn thư mục ZaloPC")
        if d:
            self.selected_dir = Path(d)
            messagebox.showinfo("Chọn thư mục", f"✅ Đã chọn: {d}")

    # Quét thư mục ZaloData
    def scan_dir(self):
        if not self.selected_dir:
            messagebox.showwarning("Chưa chọn", "⚠ Hãy chọn thư mục ZaloPC trước.")
            return

        # Reset UI
        self.tree.delete(*self.tree.get_children())
        self.uid_var.set("")
        self.zname_var.set("")
        self.avatar_label.config(image="", text="(Avatar sẽ hiển thị ở đây)")
        self.uid = None

        # Đọc file database-config.json để tìm UID
        cfg_file = self.selected_dir / "database-config.json"
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
                self.uid = extract_first_id(data)
                if self.uid:
                    self.uid_var.set(self.uid)
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không đọc được database-config.json: {e}")

        if not self.uid:
            messagebox.showwarning("UID", "❌ Không tìm thấy UID trong database-config.json")
            return

        # Kiểm tra Storage.db để lấy info-cache (tên, avatar)
        storage_db = self.selected_dir / "Database" / "_production" / "Storage.db"
        if storage_db.exists():
            self.load_info_cache(storage_db, self.uid)
            self.load_all_info_cache(storage_db)

        # Tìm thư mục chứa message DB
        msg_dir = self.selected_dir / "Database" / "_production" / self.uid / "Core" / "Message"
        if msg_dir.exists():
            self.message_arr.clear()
            for f in msg_dir.glob("*.db"):
                self.tree.insert("", "end", values=(f.name,f))
                self.message_arr[f.name] = (f.name,f)
        else:
            messagebox.showinfo("Kết quả", "❌ Không có thư mục Message DB.")

    # Load info-cache của chính tài khoản (tên, avatar)
    def load_info_cache(self, storage_db: Path, uid: str):
        try:
            db_copy = prepare_db_copy(storage_db)
            conn = sqlite3.connect(f'file:{db_copy}?mode=ro', uri=True)
            cur = conn.cursor()
            cur.execute("SELECT val FROM 'info-cache' WHERE key=?", (f"0_{uid}",))
            row = cur.fetchone()
            conn.close()

            if not row:
                return

            data = json.loads(row[0])
            zname = data.get("zName", "")
            avatar_url = data.get("avatar", "")

            self.zname_var.set(zname)

            # Nếu có avatar thì tải về
            if avatar_url:
                resp = requests.get(avatar_url, timeout=10)
                img = Image.open(BytesIO(resp.content))
                img = img.resize((120, 120))
                self.avatar_img = ImageTk.PhotoImage(img)
                self.avatar_label.config(image=self.avatar_img, text="")
            else:
                self.avatar_label.config(text="(No avatar)")

        except Exception as e:
            messagebox.showerror("Lỗi", f"Load info-cache thất bại: {e}")

    # Load toàn bộ info-cache (danh bạ bạn bè)
    def load_all_info_cache(self, storage_db: Path):
        try:
            db_copy = prepare_db_copy(storage_db)
            conn = sqlite3.connect(f'file:{db_copy}?mode=ro', uri=True)
            cur = conn.cursor()
            cur.execute("SELECT key, val FROM 'info-cache'")
            rows = cur.fetchall()
            conn.close()

            self.cache_tree.delete(*self.cache_tree.get_children())
            self.avatar_cache.clear()

            for key, val in rows:
                try:
                    data = json.loads(val)
                    zname = data.get("zName", "")
                    avatar = data.get("avatar", "")
                except:
                    zname, avatar = "", ""
                self.cache_tree.insert("", "end", values=(key, zname, avatar, val))
                self.avatar_cache[key] = (zname, avatar, val)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không load được info-cache: {e}")

    # Xử lý khi chọn 1 người trong info-cache
    def on_select_cache(self, event):
        sel = self.cache_tree.selection()
        if not sel:
            return

        item = self.cache_tree.item(sel[0])
        vals = item.get("values", [])
        if len(vals) < 4:
            return

        uid, zname, avatar, raw = vals

        # cập nhật entry
        self.key_var2.set(str(uid))
        self.zname_var2.set(zname)

        # cập nhật JSON preview
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", raw)

        # cập nhật avatar
        self.avatar_canvas.delete("all")
        if avatar:
            try:
                resp = requests.get(avatar, timeout=10)
                img = Image.open(BytesIO(resp.content)).resize((100, 100))
                self.avatar_img2 = ImageTk.PhotoImage(img)
                self.avatar_canvas.create_image(
                    60, 60, image=self.avatar_img2, anchor="center"
                )
            except Exception as e:
                print("Lỗi load avatar:", e)
                self.avatar_canvas.create_text(60, 60, text="(Avatar lỗi)")
        else:
            self.avatar_canvas.create_text(60, 60, text="(Không có avatar)")

    # -----------------------------
    # Preview bảng SQLite
    # -----------------------------
    def open_message_db(self, event):
        item = self.tree.focus()
        if not item:
            return
        db_file = Path(self.message_arr[self.tree.item(item, "values")[0]][1])
        self.preview_message_db(db_file)

    # Hiển thị danh sách bảng trong DB
    def preview_message_db(self, db_file: Path):
        ...
        # (giữ nguyên code preview bảng và export CSV/Excel)
        ...

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    root = tb.Window(themename="litera")
    app = ZaloExtractorApp(root)

    # Auto detect thư mục ZaloData trong Windows
    if os.name == "nt":
        try:
            user = os.getlogin()
        except Exception:
            user = os.environ.get("USERNAME") or ""
        zalo_path = Path(f"C:/Users/{user}/AppData/Roaming/ZaloData")
        if zalo_path.exists():
            app.selected_dir = zalo_path
            root.after(300, app.scan_dir)
        else:
            messagebox.showwarning("Zalo chưa cài đặt",
                                   "⚠ Không tìm thấy thư mục ZaloData.\nVui lòng cài đặt hoặc đăng nhập Zalo PC.")

    root.mainloop()