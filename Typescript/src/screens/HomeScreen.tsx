import React, { useState, useEffect } from "react";
import { View, Text, Button, StyleSheet, Alert, Image, ScrollView } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { File, Directory, Paths } from "expo-file-system";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SQLite from "expo-sqlite";

type UserInfo = {
  uid: string;
  zName: string;
  avatar: string;
};

// Đệ quy tìm file trong thư mục con
async function findFileRecursive(dirUri: string, filename: string): Promise<string | null> {
  try {
    const dir = new Directory(dirUri);
    const entries = await dir.list();
    for (const entry of entries) {
      if (entry instanceof Directory) {
        const sub = await findFileRecursive(entry.uri, filename);
        if (sub) return sub;
      } else {
        if (entry.name === filename) {
          return entry.uri;
        }
      }
    }
  } catch (e) {
    console.warn("Không đọc thư mục:", dirUri, e);
  }
  return null;
}

export default function HomeScreen() {
  const [zalodataPath, setZalodataPath] = useState<string | null>(null);
  const [info, setInfo] = useState<UserInfo | null>(null);

  useEffect(() => {
    (async () => {
      const saved = await AsyncStorage.getItem("zalodataPath");
      if (saved) setZalodataPath(saved);
    })();
  }, []);

  const pickFolder = async () => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: "*/*",
        copyToCacheDirectory: false,
      });
      if (res.canceled) return;
      const uri = res.assets?.[0]?.uri;
      if (uri) {
        await AsyncStorage.setItem("zalodataPath", uri);
        setZalodataPath(uri);
        Alert.alert("✅ Đã chọn thư mục", uri);
      }
    } catch (e) {
      console.error("Lỗi chọn thư mục:", e);
    }
  };

  const scanData = async () => {
    if (!zalodataPath) {
      Alert.alert("Chưa chọn thư mục ZaloData");
      return;
    }
    try {
      // tìm config
      const configUri = await findFileRecursive(zalodataPath, "database-config.json");
      if (!configUri) {
        Alert.alert("Không tìm thấy database-config.json");
        return;
      }
      const configFile = new File(configUri);
      const jsonStr = await configFile.text();
      const configJson = JSON.parse(jsonStr);

      let uid = "";
      if (configJson["sh_sqlite_m_d"]) {
        const parsed = JSON.parse(configJson["sh_sqlite_m_d"]);
        uid = Object.keys(parsed)[0];
      }
      if (!uid) {
        Alert.alert("Không có UID trong config");
        return;
      }

      // tìm Storage.db
      const storageUri = await findFileRecursive(zalodataPath, "Storage.db");
      if (!storageUri) {
        Alert.alert("Không tìm thấy Storage.db");
        return;
      }

      // copy vào cache
      const destFile = new File(Paths.cache + "Storage.db");

      // nếu file đã tồn tại thì xóa
      if (await destFile.exists) {
        await destFile.delete();
      }
      await new File(storageUri).copy(destFile);

      // mở SQLite
      const db = await SQLite.openDatabaseAsync(destFile.uri);
      const rows = await db.getAllAsync<{ key: string; val: string }>(
        "SELECT key, val FROM 'info-cache' WHERE key = ? LIMIT 1",
        [uid]
      );
      if (rows.length === 0) {
        Alert.alert("Không tìm thấy info-cache");
        return;
      }
      const obj = JSON.parse(rows[0].val);
      setInfo({
        uid,
        zName: obj.zName ?? "",
        avatar: obj.avatar ?? "",
      });
    } catch (e) {
      console.error("Lỗi scanData:", e);
      Alert.alert("Lỗi xử lý", String(e));
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>📂 Zalo Data Extractor (Mobile)</Text>
      <Text style={styles.text}>
        {zalodataPath ? `Thư mục: ${zalodataPath}` : "Chưa chọn thư mục"}
      </Text>
      <Button title="Quét dữ liệu" onPress={scanData} />
      <View style={{ marginVertical: 8 }} />
      <Button title="Đổi thư mục" onPress={pickFolder} />

      {info && (
        <View style={styles.result}>
          <Text>UID: {info.uid}</Text>
          <Text>Tên: {info.zName}</Text>
          {info.avatar ? <Image source={{ uri: info.avatar }} style={styles.avatar} /> : null}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, justifyContent: "center", alignItems: "center", padding: 16 },
  title: { fontSize: 20, fontWeight: "bold", marginBottom: 16 },
  text: { fontSize: 16, marginBottom: 16, textAlign: "center" },
  result: { marginTop: 20, alignItems: "center" },
  avatar: { width: 100, height: 100, borderRadius: 50, marginTop: 8 },
});
