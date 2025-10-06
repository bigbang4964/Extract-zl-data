import * as FileSystem from "expo-file-system";
import { Platform } from "react-native";
import XLSX from "xlsx";

type Contact = {
  key: string;
  name: string;
  avatar: string;
  raw: string;
};
type Message = { id: number; sender: string; content: string; time: string };
type Group = { id: string; name: string; memberCount: number };

// 🔹 Contacts export
export async function exportContactsToCSV(contacts: Contact[], fileUri: string) {
  const header = "key,Name,Avatar,Raw\n";
  const rows = contacts.map(c => `${c.key},${c.name},${c.avatar},${c.raw}`).join("\n");

  const file = new FileSystem.File(fileUri);
  await file.write(header + rows, { encoding: "utf8" });
}

export async function exportContactsToExcel(contacts: Contact[], fileUri: string) {
  const ws = XLSX.utils.json_to_sheet(contacts);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Contacts");
  const wbout = XLSX.write(wb, { type: "base64", bookType: "xlsx" });

  const file = new FileSystem.File(fileUri);
  await file.write(wbout, { encoding: "base64" });
}

export function getExportPath(filename: string): string {
  if (Platform.OS === "android") {
    // Android: lưu vào thư mục Download chung
    return `/storage/emulated/0/Download/${filename}`;
  } else {
    // iOS: lưu vào sandbox của app
    return `${FileSystem.Paths.document}${filename}`;
  }
}

// 🔹 Messages export
export async function exportMessagesToCSV(messages: Message[], fileUri: string) {
  const header = "ID,Sender,Content,Time\n";
  const rows = messages
    .map(m => `${m.id},"${m.sender}","${m.content.replace(/"/g, '""')}",${m.time}`)
    .join("\n");

  const file = new FileSystem.File(fileUri);
  await file.write(header + rows, { encoding: "utf8" });
}

export async function exportMessagesToExcel(messages: Message[], fileUri: string) {
  const ws = XLSX.utils.json_to_sheet(messages);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Messages");
  const wbout = XLSX.write(wb, { type: "base64", bookType: "xlsx" });

  const file = new FileSystem.File(fileUri);
  await file.write(wbout, { encoding: "base64" });
}

// 🔹 Groups export
export async function exportGroupsToCSV(groups: Group[], fileUri: string) {
  const header = "ID,Name,MemberCount\n";
  const rows = groups.map(g => `${g.id},"${g.name}",${g.memberCount}`).join("\n");

  const file = new FileSystem.File(fileUri);
  await file.write(header + rows, { encoding: "utf8" });
}

export async function exportGroupsToExcel(groups: Group[], fileUri: string) {
  const ws = XLSX.utils.json_to_sheet(groups);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Groups");
  const wbout = XLSX.write(wb, { type: "base64", bookType: "xlsx" });

  const file = new FileSystem.File(fileUri);
  await file.write(wbout, { encoding: "base64" });
}
