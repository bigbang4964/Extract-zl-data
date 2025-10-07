#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zl_data_extractor_keypass_gui.py
-----------------------------------
Công cụ GUI cho phép:
 - Chọn file .db (hoặc auto detect)
 - Nhập khóa (key/passphrase) cho SQLCipher
 - Mở DB mã hóa (nếu key hợp lệ)
 - Liệt kê bảng, preview 100 dòng, tìm kiếm/filter
 - Xuất toàn bộ bảng hoặc dữ liệu đã lọc ra CSV / Excel (streaming, progressbar)
 - Ghi log cơ bản và SHA256 file để bảo toàn chứng cứ
-----------------------------------
Yêu cầu:
 pip install ttkbootstrap pandas openpyxl pysqlcipher3

Lưu ý:
 - Nếu bạn không thể cài pysqlcipher3 dễ dàng trên Windows, xem hướng dẫn cài sqlcipher & pysqlcipher3 phù hợp hệ thống.
 - Công cụ chỉ dùng khi bạn **có quyền hợp pháp** (dữ liệu của bạn hoặc giấy phép được phép truy cập).
 - Luôn làm việc trên **bản copy** của file gốc.
"""

import os
import shutil
import sqlite3
import hashlib
import tempfile
import threading
import csv
from pathlib import Path
from datetime import datetime

# UI
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox

# Data handling
import pandas as pd

# SQLCipher library (pysqlcipher3). Nếu không import được, tool sẽ hiển thị lỗi và hướng dẫn.
try:
    from pysqlcipher3 import dbapi2 as sqlcipher
    SQLCIPHER_AVAILABLE = True
except Exception as e:
    SQLCIPHER_AVAILABLE = False
    _sqlcipher_import_error = str(e)

# -----------------------
# Helper functions
# -----------------------

TEMP_DIR = Path(tempfile.gettempdir()) / "zalo_sqlcipher_tmp"
TEMP_DIR.mkdir(exist_ok=True)

def sha256_of_file(path: Path):
    """Tính SHA256 của file (để ghi nhận trước khi thao tác)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def safe_copy_db_with_wal_shm(db_path: Path) -> Path:
    """
    Copy file .db và các file .db-wal / .db-shm nếu có vào thư mục tạm,
    trả về path tới file copy.
    """
    TEMP_DIR.mkdir(exist_ok=True)
    dst = TEMP_DIR / (db_path.name + f".copy_{int(datetime.now().timestamp())}")
    shutil.copy2(db_path, dst)
    # copy wal/shm nếu tồn tại cùng thư mục gốc
    for ext in (".db-wal", ".db-shm"):
        # for files like name.db-wal or name.sqlite-wal
        candidate = db_path.with_name(db_path.name + ext)
        if candidate.exists():
            try:
                shutil.copy2(candidate, TEMP_DIR / candidate.name)
            except Exception:
                pass
    return dst

def open_sqlcipher_connection(db_path: Path, key: str, kdf_iter: int = None, cipher_compat: int = None, page_size: int=None):
    """
    Mở connection SQLCipher với key và optional pragmas.
    Trả về connection nếu thành công, hoặc raise Exception nếu lỗi.
    """
    if not SQLCIPHER_AVAILABLE:
        raise RuntimeError(f"pysqlcipher3 không có sẵn: {_sqlcipher_import_error}")
    conn = sqlcipher.connect(str(db_path))
    cur = conn.cursor()

    # optional pragmas (nếu DB dùng cấu hình khác)
    if cipher_compat is not None:
        cur.execute(f"PRAGMA cipher_compatibility = {int(cipher_compat)};")
    if kdf_iter is not None:
        cur.execute(f"PRAGMA kdf_iter = {int(kdf_iter)};")
    if page_size is not None:
        cur.execute(f"PRAGMA page_size = {int(page_size)};")

    # set key
    cur.execute("PRAGMA key = ?;", (key,))
    # test query
    try:
        cur.execute("SELECT count(*) FROM sqlite_master;")
        _ = cur.fetchone()
        return conn
    except Exception as e:
        conn.close()
        raise e

def list_tables_from_conn(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [r[0] for r in cur.fetchall()]

def fetch_preview_df(conn, table, limit=100):
    """Đọc preview (limit rows) vào pandas DataFrame để phục vụ hiển thị & lọc nhanh."""
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT {limit}', conn)
        return df
    except Exception as e:
        raise

def count_rows(conn, table):
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{table}";')
    r = cur.fetchone()
    return r[0] if r else 0

def export_table_streaming(conn, table, out_path: Path, fmt="csv", chunk_size=1000, progress_callback=None):
    """
    Xuất toàn bộ bảng ra CSV/Excel dạng streaming (tránh load toàn bộ vào RAM).
    - progress_callback(received_rows, total_rows) để cập nhật progressbar.
    """
    total = count_rows(conn, table)
    if fmt == "csv":
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM "{table}";')
        cols = [d[0] for d in cur.description]
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            exported = 0
            while True:
                rows = cur.fetchmany(chunk_size)
                if not rows:
                    break
                writer.writerows(rows)
                exported += len(rows)
                if progress_callback:
                    progress_callback(exported, total)
    else:
        # Excel export using pandas in chunks: we'll accumulate chunk files then concat (but to reduce memory, write via pandas using openpyxl in append mode)
        # Simpler approach: read in chunks and write via DataFrame to_excel with mode append - openpyxl supports append? We'll do batched DataFrame writes.
        # Note: openpyxl doesn't have efficient append for header/rows; for moderate sizes it's acceptable.
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM "{table}";')
        cols = [d[0] for d in cur.description]
        exported = 0
        # building Excel by accumulating chunks into DataFrame and writing in append mode
        first_write = True
        while True:
            rows = cur.fetchmany(chunk_size)
            if not rows:
                break
            df_chunk = pd.DataFrame(rows, columns=cols)
            if first_write:
                df_chunk.to_excel(out_path, index=False, engine="openpyxl")
                first_write = False
            else:
                # append: load existing then append -> slower but keeps memory low per chunk
                with pd.ExcelWriter(out_path, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                    # write at next row manually by reading existing? To keep code simpler we will append by creating a new sheet named _part_i
                    sheet_name = f"part_{exported//chunk_size}"
                    df_chunk.to_excel(writer, index=False, sheet_name=sheet_name)
            exported += len(rows)
            if progress_callback:
                progress_callback(exported, total)

# -----------------------
# GUI Application
# -----------------------

class App:
    def __init__(self, root: tb.Window):
        self.root = root
        self.root.title("Zalo SQLCipher Forensic GUI")
        self.root.geometry("1024x720")

        # Styles and theme switch
        self.style = root.style
        # top frame: inputs
        frm_top = tb.Frame(root)
        frm_top.pack(fill=X, padx=10, pady=8)

        # DB file selection
        tb.Label(frm_top, text="File .db:").grid(row=0, column=0, sticky="w", padx=4)
        self.db_path_var = tb.StringVar()
        self.entry_db = tb.Entry(frm_top, textvariable=self.db_path_var, width=70, bootstyle="info")
        self.entry_db.grid(row=0, column=1, padx=4, sticky="w")
        tb.Button(frm_top, text="Chọn file", bootstyle="secondary", command=self.choose_db).grid(row=0, column=2, padx=4)

        # Key input
        tb.Label(frm_top, text="Key (passphrase):").grid(row=1, column=0, sticky="w", padx=4, pady=6)
        self.key_var = tb.StringVar()
        self.entry_key = tb.Entry(frm_top, textvariable=self.key_var, width=50, show="*", bootstyle="warning")
        self.entry_key.grid(row=1, column=1, sticky="w", padx=4)

        # Optional PRAGMA inputs
        tb.Label(frm_top, text="KDF Iter (opt):").grid(row=2, column=0, sticky="w", padx=4)
        self.kdf_var = tb.StringVar()
        tb.Entry(frm_top, textvariable=self.kdf_var, width=12).grid(row=2, column=1, sticky="w", padx=4)

        tb.Label(frm_top, text="Cipher compat (opt):").grid(row=2, column=1, sticky="e", padx=4)
        self.cipher_compat_var = tb.StringVar()
        tb.Entry(frm_top, textvariable=self.cipher_compat_var, width=6).grid(row=2, column=2, sticky="w")

        # Open button + auto detect on Windows
        btn_frame = tb.Frame(root)
        btn_frame.pack(fill=X, padx=10)
        self.btn_open = tb.Button(btn_frame, text="🔓 Mở DB với key", bootstyle="success", command=self.open_db)
        self.btn_open.pack(side=LEFT, padx=6, pady=6)

        self.btn_hash = tb.Button(btn_frame, text="Hash SHA256 file", bootstyle="info", command=self.show_hash)
        self.btn_hash.pack(side=LEFT, padx=6, pady=6)

        # If running on Windows, attempt auto-detect ZaloData default path
        if os.name == "nt":
            try:
                user = os.getlogin()
                default = Path(f"C:/Users/{user}/AppData/Roaming/ZaloData")
                if default.exists():
                    # optional auto set
                    self.db_path_var.set(str(default))
            except Exception:
                pass

        # Middle frame: tables list + preview area
        mid_frame = tb.PanedWindow(root, orient=HORIZONTAL)
        mid_frame.pack(fill=BOTH, expand=True, padx=10, pady=6)

        # Left: tables list
        left_frame = tb.Labelframe(mid_frame, text="Tables", padding=6)
        mid_frame.add(left_frame, weight=1)
        self.tbl_tree = tb.Treeview(left_frame, columns=("table", "rows"), show="headings", bootstyle="secondary")
        self.tbl_tree.heading("table", text="Table")
        self.tbl_tree.heading("rows", text="Rows")
        self.tbl_tree.pack(fill=BOTH, expand=True, side=LEFT)
        scroll_t = tb.Scrollbar(left_frame, command=self.tbl_tree.yview, bootstyle="round")
        self.tbl_tree.configure(yscroll=scroll_t.set)
        scroll_t.pack(side=RIGHT, fill=Y)
        self.tbl_tree.bind("<Double-1>", self.on_table_double_click)

        # Right: preview + search + export
        right_frame = tb.Labelframe(mid_frame, text="Preview & Export", padding=6)
        mid_frame.add(right_frame, weight=3)

        # Search
        search_fr = tb.Frame(right_frame)
        search_fr.pack(fill=X, pady=4)
        tb.Label(search_fr, text="Tìm kiếm (lọc trong preview):").pack(side=LEFT)
        self.search_var = tb.StringVar()
        self.search_entry = tb.Entry(search_fr, textvariable=self.search_var, bootstyle="info")
        self.search_entry.pack(side=LEFT, fill=X, expand=True, padx=6)
        self.search_var.trace_add("write", self.apply_filter_preview)

        # Preview tree
        preview_frame = tb.Frame(right_frame)
        preview_frame.pack(fill=BOTH, expand=True)
        self.preview_tree = tb.Treeview(preview_frame, show="headings")
        self.preview_tree.pack(fill=BOTH, expand=True, side=LEFT)
        self.preview_scroll = tb.Scrollbar(preview_frame, command=self.preview_tree.yview, bootstyle="round")
        self.preview_tree.configure(yscroll=self.preview_scroll.set)
        self.preview_scroll.pack(side=RIGHT, fill=Y)

        # Bottom of right frame: export buttons & progress
        export_frame = tb.Frame(right_frame)
        export_frame.pack(fill=X, pady=6)
        self.btn_export_filtered_csv = tb.Button(export_frame, text="Xuất dữ liệu đang lọc → CSV", bootstyle="success", command=lambda: self.export_preview("csv"))
        self.btn_export_filtered_csv.pack(side=LEFT, padx=4)
        self.btn_export_filtered_excel = tb.Button(export_frame, text="Xuất dữ liệu đang lọc → Excel", bootstyle="info", command=lambda: self.export_preview("excel"))
        self.btn_export_filtered_excel.pack(side=LEFT, padx=4)
        self.btn_export_all_csv = tb.Button(export_frame, text="Xuất toàn bộ bảng → CSV", bootstyle="secondary", command=lambda: self.export_all("csv"))
        self.btn_export_all_csv.pack(side=LEFT, padx=4)
        self.btn_export_all_excel = tb.Button(export_frame, text="Xuất toàn bộ bảng → Excel", bootstyle="secondary", command=lambda: self.export_all("excel"))
        self.btn_export_all_excel.pack(side=LEFT, padx=4)

        # Progressbar
        self.progress = tb.Progressbar(root, mode="determinate", bootstyle="info")
        self.progress.pack(fill=X, padx=12, pady=6)

        # Status label
        self.status_var = tb.StringVar(value="Ready")
        self.status = tb.Label(root, textvariable=self.status_var)
        self.status.pack(fill=X, padx=12, pady=4)

        # internal state
        self.conn = None
        self.current_db_copy = None
        self.current_table = None
        self.current_preview_df = pd.DataFrame()

    # -----------------------
    # UI helpers
    # -----------------------
    def log_status(self, text):
        ts = datetime.now().isoformat(sep=" ", timespec="seconds")
        self.status_var.set(f"{ts} — {text}")

    def choose_db(self):
        f = filedialog.askopenfilename(title="Chọn file SQLite/SQLCipher .db", filetypes=[("DB files", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")])
        if f:
            self.db_path_var.set(f)
            self.log_status(f"Chọn file: {f}")

    def show_hash(self):
        p = self.db_path_var.get().strip()
        if not p:
            messagebox.showwarning("Chưa chọn file", "Vui lòng chọn file .db trước")
            return
        path = Path(p)
        if not path.exists():
            messagebox.showerror("File không tồn tại", str(path))
            return
        h = sha256_of_file(path)
        messagebox.showinfo("SHA256", f"{path.name}\nSHA256: {h}")
        self.log_status("Đã tính SHA256")

    # -----------------------
    # Open DB
    # -----------------------
    def open_db(self):
        """
        Hàm mở DB bằng key. Thực thi trong thread để tránh treo UI.
        """
        if not SQLCIPHER_AVAILABLE:
            messagebox.showerror("Thiếu thư viện", f"pysqlcipher3 chưa cài được.\nLỗi: {_sqlcipher_import_error}\nHãy cài bằng: pip install pysqlcipher3")
            return

        db_path = self.db_path_var.get().strip()
        if not db_path:
            messagebox.showwarning("Chưa chọn file", "Vui lòng chọn file .db trước")
            return
        key = self.key_var.get()
        if not key:
            if not messagebox.askyesno("Không nhập key", "Bạn chưa nhập key. Muốn thử mở (thường sẽ thất bại)?"):
                return

        # copy file + wal/shm vào temp
        try:
            dbp = Path(db_path)
            if not dbp.exists():
                messagebox.showerror("File không tồn tại", str(dbp))
                return
            self.current_db_copy = safe_copy_db_with_wal_shm(dbp)
        except Exception as e:
            messagebox.showerror("Lỗi copy", str(e))
            return

        # disable button
        self.btn_open.configure(state=DISABLED)
        self.log_status("Đang mở DB...")

        def worker():
            try:
                kdf = int(self.kdf_var.get()) if self.kdf_var.get().strip() else None
                cipher_compat = int(self.cipher_compat_var.get()) if self.cipher_compat_var.get().strip() else None
                conn = open_sqlcipher_connection(self.current_db_copy, key, kdf_iter=kdf, cipher_compat=cipher_compat)
                self.conn = conn
                tables = list_tables_from_conn(conn)
                # get rows count for each table (may take time for big DBs)
                table_info = []
                for t in tables:
                    try:
                        cnt = count_rows(conn, t)
                    except Exception:
                        cnt = -1
                    table_info.append((t, cnt))
                def update_ui():
                    self.tbl_tree.delete(*self.tbl_tree.get_children())
                    for t, cnt in table_info:
                        self.tbl_tree.insert("", "end", values=(t, cnt))
                    self.log_status(f"Mở DB thành công: {Path(db_path).name} (tìm thấy {len(table_info)} bảng)")
                    messagebox.showinfo("Mở thành công", f"Đã mở DB thành công.\nTìm thấy {len(table_info)} bảng.")
                self.root.after(0, update_ui)
            except Exception as e:
                err_msg = str(e).lower()
                def err_ui():
                    if "file is not a database" in err_msg or "not a database" in err_msg:
                        messagebox.showerror(
                            "Sai key hoặc cipher",
                            f"Không mở được DB.\n\nNguyên nhân có thể:\n"
                            f" • Sai key (thường là số điện thoại, chuỗi hex, ...)\n"
                            f" • Sai cipher_compat (thử đổi giữa 3 hoặc 4)\n\n"
                            f"Chi tiết lỗi: {e}"
                        )
                    else:
                        messagebox.showerror("Mở DB thất bại", f"Không mở được DB: {e}")
                    self.log_status("Mở DB thất bại")
                self.root.after(0, err_ui)
            finally:
                self.root.after(0, lambda: self.btn_open.configure(state=NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    # -----------------------
    # Table preview handling
    # -----------------------
    def on_table_double_click(self, event):
        sel = self.tbl_tree.focus()
        if not sel:
            return
        values = self.tbl_tree.item(sel, "values")
        if not values:
            return
        table = values[0]
        self.preview_table(table)

    def preview_table(self, table_name):
        """
        Load preview (100 dòng) in background and show in preview_tree.
        """
        if not self.conn:
            messagebox.showwarning("Chưa mở DB", "Vui lòng mở DB bằng key trước.")
            return
        self.current_table = table_name
        self.log_status(f"Đang tải preview {table_name} ...")
        self.progress.configure(mode="indeterminate")
        self.progress.start()

        def worker():
            try:
                df = fetch_preview_df(self.conn, table_name, limit=100)
                self.current_preview_df = df.copy()
                # prepare columns for treeview
                cols = list(df.columns)
                def show():
                    # clear previous columns
                    self.preview_tree.delete(*self.preview_tree.get_children())
                    self.preview_tree["columns"] = cols
                    for c in cols:
                        self.preview_tree.heading(c, text=c)
                        self.preview_tree.column(c, width=120, anchor="w")
                    # insert rows
                    for _, row in df.iterrows():
                        vals = [("" if pd.isna(v) else str(v)) for v in row.tolist()]
                        self.preview_tree.insert("", "end", values=vals)
                    self.log_status(f"Preview {table_name} hiển thị ({len(df)} dòng)")
                self.root.after(0, show)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi load preview", str(e)))
            finally:
                self.root.after(0, lambda: (self.progress.stop(), self.progress.configure(mode="determinate")))
        threading.Thread(target=worker, daemon=True).start()

    def apply_filter_preview(self, *args):
        """Lọc dữ liệu trong preview_df dựa trên search_var."""
        q = self.search_var.get().strip().lower()
        if self.current_preview_df is None or self.current_preview_df.empty:
            return
        if q == "":
            df = self.current_preview_df
        else:
            # any column contains query (case-insensitive)
            mask = self.current_preview_df.apply(lambda r: r.astype(str).str.lower().str.contains(q).any(), axis=1)
            df = self.current_preview_df[mask]
        # update preview_tree
        self.preview_tree.delete(*self.preview_tree.get_children())
        for _, row in df.iterrows():
            vals = [("" if pd.isna(v) else str(v)) for v in row.tolist()]
            self.preview_tree.insert("", "end", values=vals)

    # -----------------------
    # Export handlers
    # -----------------------
    def export_preview(self, fmt="csv"):
        """Export dữ liệu đang hiển thị (đã lọc) từ preview_tree -> file."""
        if self.current_preview_df is None or self.current_table is None:
            messagebox.showwarning("Không có dữ liệu", "Chưa có preview để xuất")
            return
        # apply current filter
        q = self.search_var.get().strip().lower()
        if q == "":
            df = self.current_preview_df
        else:
            mask = self.current_preview_df.apply(lambda r: r.astype(str).str.lower().str.contains(q).any(), axis=1)
            df = self.current_preview_df[mask]

        if df.empty:
            messagebox.showinfo("Không có dữ liệu", "Không có hàng nào khớp để xuất")
            return

        f = filedialog.asksaveasfilename(defaultextension=".csv" if fmt=="csv" else ".xlsx",
                                         filetypes=[("CSV", "*.csv")] if fmt=="csv" else [("Excel", "*.xlsx")],
                                         initialfile=f"{Path(self.db_path_var.get()).stem}__{self.current_table}_preview")
        if not f:
            return
        try:
            if fmt == "csv":
                df.to_csv(f, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(f, index=False)
            messagebox.showinfo("Xuất thành công", f"Đã xuất {len(df)} dòng ra {f}")
            self.log_status(f"Xuất preview: {f}")
        except Exception as e:
            messagebox.showerror("Lỗi xuất", str(e))

    def export_all(self, fmt="csv"):
        """Export toàn bộ bảng (streaming) với progressbar."""
        if self.conn is None:
            messagebox.showwarning("Chưa mở DB", "Vui lòng mở DB bằng key trước.")
            return
        if not self.current_table:
            messagebox.showwarning("Chưa chọn bảng", "Vui lòng double-click một bảng để chọn trước khi xuất toàn bộ.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".csv" if fmt=="csv" else ".xlsx",
                                           filetypes=[("CSV", "*.csv")] if fmt=="csv" else [("Excel", "*.xlsx")],
                                           initialfile=f"{Path(self.db_path_var.get()).stem}__{self.current_table}")
        if not out:
            return
        out_path = Path(out)
        self.progress.configure(mode="determinate", value=0, maximum=100)
        self.log_status(f"Đang xuất toàn bộ bảng {self.current_table} ...")
        self.btn_export_all_csv.configure(state=DISABLED)
        self.btn_export_all_excel.configure(state=DISABLED)

        def progress_cb(exported, total):
            if total and total > 0:
                perc = min(100, int(exported * 100 / total))
                self.root.after(0, lambda: self.progress.configure(value=perc))
                self.root.after(0, lambda: self.status_var.set(f"Exported {exported}/{total} rows ({perc}%)"))
            else:
                self.root.after(0, lambda: self.progress.configure(value=0))
                self.root.after(0, lambda: self.status_var.set(f"Exported {exported} rows"))

        def worker():
            try:
                export_table_streaming(self.conn, self.current_table, out_path, fmt=fmt, chunk_size=2000, progress_callback=progress_cb)
                self.root.after(0, lambda: messagebox.showinfo("Hoàn tất", f"Đã xuất bảng {self.current_table} ra {out_path}"))
                self.log_status(f"Xuất toàn bộ xong: {out_path}")
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi xuất", str(e)))
                self.log_status("Lỗi khi xuất toàn bộ")
            finally:
                # enable buttons lại
                self.root.after(0, lambda: self.btn_export_all_csv.configure(state=NORMAL))
                self.root.after(0, lambda: self.btn_export_all_excel.configure(state=NORMAL))
                self.root.after(0, lambda: self.progress.configure(value=0))

        threading.Thread(target=worker, daemon=True).start()

    def cleanup(self):
        """Xóa các file copy DB trong TEMP_DIR khi thoát ứng dụng"""
        try:
            if TEMP_DIR.exists():
                for f in TEMP_DIR.glob("*.db"):
                    try:
                        f.unlink()
                    except Exception as e:
                        print(f"Không xóa được {f}: {e}")
        except Exception as e:
            print(f"Lỗi cleanup: {e}")

    def on_close(self):
        self.cleanup()
        self.root.destroy()

# -----------------------
# Run application
# -----------------------

def main():
    root = tb.Window(themename="litera")
    app = App(root)
    # Khi đóng cửa sổ thì gọi cleanup trước khi destroy
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()