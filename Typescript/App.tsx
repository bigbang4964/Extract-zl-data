// Import React để sử dụng JSX và component
import React from "react";

// Import Provider của react-native-paper để bọc toàn bộ app,
// giúp sử dụng theme, Button, TextInput, ... của thư viện này
import { Provider as PaperProvider } from "react-native-paper";

// Import màn hình chính của ứng dụng (ZlExtractorScreen)
import ZlExtractorScreen from "./screens/ZlExtractorScreen";

// Component gốc của ứng dụng
export default function App() {
  return (
    // Bọc toàn bộ ứng dụng trong PaperProvider
    // để các component con (như Button, TextInput) có thể sử dụng theme mặc định
    <PaperProvider>
      {/* Gọi màn hình chính ZlExtractorScreen */}
      <ZlExtractorScreen />
    </PaperProvider>
  );
}
