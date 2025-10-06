import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Button, Alert, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import * as SQLite from "expo-sqlite";
import { exportMessagesToCSV, exportMessagesToExcel } from "../utils/exportUtils";

type Message = {
  id: number;
  sender: string;
  content: string;
  time: string;
};

export default function MessagesScreen() {
  const [messages, setMessages] = useState<Message[]>([]);

  useEffect(() => {
    async function load() {
      try {
        // mở database (file msg.db đã copy sẵn vào documentDirectory hoặc Download)
        const db = await SQLite.openDatabaseAsync("msg.db");

        // chạy query
        const rows = await db.getAllAsync<{
          id: number;
          sender: string;
          content: string;
          time: number;
        }>("SELECT id, sender, content, time FROM messages LIMIT 200");

        const data: Message[] = rows.map((r) => ({
          id: r.id,
          sender: r.sender,
          content: r.content,
          time: new Date(r.time * 1000).toLocaleString(), // convert epoch -> human readable
        }));

        setMessages(data);
      } catch (e) {
        console.error("Load messages error", e);
      }
    }
    load();
  }, []);

  const handleExportCSV = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "messages.csv";
      await exportMessagesToCSV(messages, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export CSV error", String(e));
    }
  };

  const handleExportExcel = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "messages.xlsx";
      await exportMessagesToExcel(messages, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export Excel error", String(e));
    }
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: "bold" }}>Tin nhắn Zalo</Text>
      <FlatList
        data={messages}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <View style={styles.item}>
            <Text style={styles.sender}>{item.sender}</Text>
            <Text>{item.content}</Text>
            <Text style={styles.time}>{item.time}</Text>
          </View>
        )}
      />
      <Button title="Export CSV" onPress={handleExportCSV} />
      <Button title="Export Excel" onPress={handleExportExcel} />
    </View>
  );
}

const styles = StyleSheet.create({
  item: { padding: 10, borderBottomWidth: 1, borderColor: "#ddd" },
  sender: { fontWeight: "bold", fontSize: 15 },
  time: { fontSize: 12, color: "#666" },
});
