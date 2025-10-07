import * as FileSystem from "expo-file-system";
import { Platform } from "react-native";
import XLSX from "xlsx";

// 🧩 Định nghĩa kiểu dữ liệu (type) cho từng loại thông tin
type Contact = {
  key: string;    // ID của người liên hệ
  name: string;   // Tên hiển thị
  avatar: string; // Ảnh đại diện (URL)
  raw: string;    // Dữ liệu gốc JSON
};

type Message = {
  id: number;       // ID tin nhắn
  sender: string;   // Người gửi
  content: string;  // Nội dung tin nhắn
  time: string;     // Thời gian gửi (chuỗi)
};

type Group = {
  id: string;         // ID nhóm
  name: string;       // Tên nhóm
  memberCount: number;// Số lượng thành viên
};

// ==========================================================
// 🔹 HÀM XUẤT DỮ LIỆU DANH BẠ (CONTACTS)
// ==========================================================

/**
 * Xuất danh bạ ra file CSV (dạng văn bản)
 * @param contacts - danh sách danh bạ
 * @param fileUri - đường dẫn nơi lưu file
 */
export async function exportContactsToCSV(contacts: Contact[], fileUri: string) {
  // Tạo dòng tiêu đề cho file CSV
  const header = "key,Name,Avatar,Raw\n";

  // Tạo từng dòng dữ liệu
  const rows = contacts
    .map(c => `${c.key},${c.name},${c.avatar},${c.raw}`)
    .join("\n");

  // Ghi toàn bộ dữ liệu vào file (UTF-8)
  const file = new FileSystem.File(fileUri);
  await file.write(header + rows, { encoding: "utf8" });
}

/**
 * Xuất danh bạ ra file Excel (.xlsx)
 */
export async function exportContactsToExcel(contacts: Contact[], fileUri: string) {
  // Chuyển danh sách danh bạ thành sheet Excel
  const ws = XLSX.utils.json_to_sheet(contacts);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Contacts");

  // Ghi workbook ra base64
  const wbout = XLSX.write(wb, { type: "base64", bookType: "xlsx" });

  // Lưu ra file định dạng base64
  const file = new FileSystem.File(fileUri);
  await file.write(wbout, { encoding: "base64" });
}

// ==========================================================
// 🔹 HÀM LẤY ĐƯỜNG DẪN XUẤT FILE TƯƠNG ỨNG MỖI NỀN TẢNG
// ==========================================================

/**
 * Lấy đường dẫn hợp lệ để lưu file xuất
 * @param filename - tên file muốn lưu
 * @returns đường dẫn tuyệt đối hợp lệ
 */
export function getExportPath(filename: string): string {
  if (Platform.OS === "android") {
    // Android: lưu vào thư mục "Download" của người dùng
    return `/storage/emulated/0/Download/${filename}`;
  } else {
    // iOS: lưu vào thư mục sandbox riêng của app
    return `${FileSystem.Paths.document}${filename}`;
  }
}

// ==========================================================
// 🔹 HÀM XUẤT DỮ LIỆU TIN NHẮN (MESSAGES)
// ==========================================================

/**
 * Xuất danh sách tin nhắn ra CSV
 */
export async function exportMessagesToCSV(messages: Message[], fileUri: string) {
  const header = "ID,Sender,Content,Time\n";

  // Escape ký tự " trong nội dung tin nhắn để tránh lỗi CSV
  const rows = messages
    .map(m => `${m.id},"${m.sender}","${m.content.replace(/"/g, '""')}",${m.time}`)
    .join("\n");

  const file = new FileSystem.File(fileUri);
  await file.write(header + rows, { encoding: "utf8" });
}

/**
 * Xuất danh sách tin nhắn ra Excel
 */
export async function exportMessagesToExcel(messages: Message[], fileUri: string) {
  const ws = XLSX.utils.json_to_sheet(messages);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Messages");
  const wbout = XLSX.write(wb, { type: "base64", bookType: "xlsx" });

  const file = new FileSystem.File(fileUri);
  await file.write(wbout, { encoding: "base64" });
}

// ==========================================================
// 🔹 HÀM XUẤT DỮ LIỆU NHÓM (GROUPS)
// ==========================================================

/**
 * Xuất danh sách nhóm ra CSV
 */
export async function exportGroupsToCSV(groups: Group[], fileUri: string) {
  const header = "ID,Name,MemberCount\n";
  const rows = groups
    .map(g => `${g.id},"${g.name}",${g.memberCount}`)
    .join("\n");

  const file = new FileSystem.File(fileUri);
  await file.write(header + rows, { encoding: "utf8" });
}

/**
 * Xuất danh sách nhóm ra Excel
 */
export async function exportGroupsToExcel(groups: Group[], fileUri: string) {
  const ws = XLSX.utils.json_to_sheet(groups);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Groups");
  const wbout = XLSX.write(wb, { type: "base64", bookType: "xlsx" });

  const file = new FileSystem.File(fileUri);
  await file.write(wbout, { encoding: "base64" });
}