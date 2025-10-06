import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Button, Alert, Image, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import * as SQLite from "expo-sqlite";

import { exportContactsToCSV, exportContactsToExcel } from "../utils/exportUtils";

type Contact = {
  key: string;
  name: string;
  avatar: string;
  raw: string;
};

export default function ContactsScreen() {
  const [contacts, setContacts] = useState<Contact[]>([]);

  useEffect(() => {
    async function load() {
      try {
        // Mở DB đồng bộ (Storage.db đã copy sẵn vào documentDirectory hoặc Download)
        const db = SQLite.openDatabaseSync("Storage.db");

        // Lấy dữ liệu từ bảng info-cache
        const rows = (await db.getAllAsync(
          "SELECT key, val FROM 'info-cache'"
        )) as { key: string; val: string }[];

        const data: Contact[] = rows.map((row) => {
          try {
            const obj = JSON.parse(row.val);
            return {
              key: row.key,
              name: obj.zName ?? "",
              avatar: obj.avatar ?? "",
              raw: row.val,
            };
          } catch {
            return { key: row.key, name: "", avatar: "", raw: "" };
          }
        });

        setContacts(data);
      } catch (e) {
        console.error("DB load error:", e);
      }
    }

    load();
  }, []);

  const handleExportCSV = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "contacts.csv";
      await exportContactsToCSV(contacts, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export CSV error", String(e));
    }
  };

  const handleExportExcel = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "contacts.xlsx";
      await exportContactsToExcel(contacts, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export Excel error", String(e));
    }
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: "bold" }}>Danh bạ Zalo</Text>
      <FlatList
        data={contacts}
        keyExtractor={(item) => item.key}
        renderItem={({ item }) => (
          <View style={styles.item}>
            {item.avatar ? (
              <Image source={{ uri: item.avatar }} style={styles.avatar} />
            ) : (
              <View style={styles.avatarPlaceholder} />
            )}
            <View>
              <Text style={styles.name}>{item.name}</Text>
              <Text style={styles.uid}>{item.key}</Text>
            </View>
          </View>
        )}
      />
      <Button title="Export CSV" onPress={handleExportCSV} />
      <Button title="Export Excel" onPress={handleExportExcel} />
    </View>
  );
}

const styles = StyleSheet.create({
  item: { flexDirection: "row", padding: 10, borderBottomWidth: 1, borderColor: "#ddd" },
  avatar: { width: 40, height: 40, borderRadius: 20, marginRight: 10 },
  avatarPlaceholder: { width: 40, height: 40, borderRadius: 20, backgroundColor: "#ccc", marginRight: 10 },
  name: { fontSize: 16, fontWeight: "600" },
  uid: { fontSize: 12, color: "#666" },
});
