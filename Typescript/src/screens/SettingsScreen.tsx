import React from "react";
import { View, Text, Button, StyleSheet } from "react-native";

export default function SettingsScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>⚙️ Settings</Text>
      <Text>Theme, app info, etc.</Text>
      <Button title="Switch Theme" onPress={() => alert("Chức năng đổi theme")} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", padding: 16 },
  title: { fontSize: 20, fontWeight: "bold", marginBottom: 16 }
});
