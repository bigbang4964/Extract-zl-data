import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Button, Alert, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import * as SQLite from "expo-sqlite";
import { exportMessagesToCSV, exportMessagesToExcel } from "../utils/exportUtils";

// Định nghĩa kiểu dữ liệu cho một tin nhắn
type Message = {
  id: number;      // ID của tin nhắn
  sender: string;  // Người gửi
  content: string; // Nội dung tin nhắn
  time: string;    // Thời gian gửi (định dạng hiển thị)
};

export default function MessagesScreen() {
  // State lưu danh sách tin nhắn
  const [messages, setMessages] = useState<Message[]>([]);

  // useEffect chạy một lần khi component được mount
  useEffect(() => {
    async function load() {
      try {
        // Mở database SQLite (file msg.db cần được copy sẵn vào documentDirectory hoặc thư mục Download)
        const db = await SQLite.openDatabaseAsync("msg.db");

        // Thực thi truy vấn SQL để lấy dữ liệu từ bảng messages
        const rows = await db.getAllAsync<{
          id: number;
          sender: string;
          content: string;
          time: number;
        }>("SELECT id, sender, content, time FROM messages LIMIT 200");

        // Chuyển đổi dữ liệu từ DB sang dạng dễ hiển thị
        const data: Message[] = rows.map((r) => ({
          id: r.id,
          sender: r.sender,
          content: r.content,
          // Chuyển thời gian từ epoch (giây) sang chuỗi ngày giờ dễ đọc
          time: new Date(r.time * 1000).toLocaleString(),
        }));

        // Cập nhật state
        setMessages(data);
      } catch (e) {
        console.error("Load messages error", e);
      }
    }

    load();
  }, []);

  // Hàm xuất danh sách tin nhắn ra CSV
  const handleExportCSV = async () => {
    try {
      // Đường dẫn lưu file CSV trong thư mục document
      const fileUri = FileSystem.Paths.document + "messages.csv";

      // Gọi hàm tiện ích xuất CSV
      await exportMessagesToCSV(messages, fileUri);

      // Chia sẻ file (qua Gmail, Drive, Zalo, v.v.)
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export CSV error", String(e));
    }
  };

  // Hàm xuất danh sách tin nhắn ra Excel (.xlsx)
  const handleExportExcel = async () => {
    try {
      // Đường dẫn lưu file Excel trong thư mục document
      const fileUri = FileSystem.Paths.document + "messages.xlsx";

      // Gọi hàm tiện ích xuất Excel
      await exportMessagesToExcel(messages, fileUri);

      // Mở giao diện chia sẻ file
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export Excel error", String(e));
    }
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      {/* Tiêu đề màn hình */}
      <Text style={{ fontSize: 18, fontWeight: "bold" }}>Tin nhắn Zalo</Text>

      {/* Hiển thị danh sách tin nhắn */}
      <FlatList
        data={messages}
        keyExtractor={(item) => item.id.toString()} // Mỗi tin nhắn có ID duy nhất
        renderItem={({ item }) => (
          <View style={styles.item}>
            <Text style={styles.sender}>{item.sender}</Text>
            <Text>{item.content}</Text>
            <Text style={styles.time}>{item.time}</Text>
          </View>
        )}
      />

      {/* Hai nút xuất file CSV và Excel */}
      <Button title="Export CSV" onPress={handleExportCSV} />
      <Button title="Export Excel" onPress={handleExportExcel} />
    </View>
  );
}

// Style cho các phần tử UI
const styles = StyleSheet.create({
  item: { padding: 10, borderBottomWidth: 1, borderColor: "#ddd" }, // Mỗi dòng tin nhắn
  sender: { fontWeight: "bold", fontSize: 15 }, // Tên người gửi
  time: { fontSize: 12, color: "#666" }, // Thời gian gửi
});