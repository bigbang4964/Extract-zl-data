import { NativeModules, Platform } from "react-native";

const LINKING_ERROR =
  `The package 'zalo-data-module' doesn't seem to be linked. Make sure:\n\n` +
  Platform.select({ ios: "- iOS chưa hỗ trợ", default: "- run 'npx prebuild' để tự liên kết Android" });

const ZaloDataModule = NativeModules.ZaloDataModule
  ? NativeModules.ZaloDataModule
  : new Proxy({}, { get() { throw new Error(LINKING_ERROR); } });

export type FileEntry = {
  uri: string;
  name: string;
  mime: string;
};

export async function listFiles(uri: string): Promise<FileEntry[]> {
  return await ZaloDataModule.listFiles(uri);
}

export default { listFiles };
