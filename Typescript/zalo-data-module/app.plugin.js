const { withProjectBuildGradle } = require("@expo/config-plugins");

/**
 * Expo Config Plugin cho ZaloDataModule
 */
module.exports = function withZaloDataModule(config) {
  // Thêm include ':zalo-data-module' vào project build.gradle
  return withProjectBuildGradle(config, (config) => {
    if (!config.modResults.contents.includes("include ':zalo-data-module'")) {
      config.modResults.contents += `\ninclude ':zalo-data-module'\nproject(':zalo-data-module').projectDir = new File(rootProject.projectDir, '../zalo-data-module/android')\n`;
    }
    return config;
  });
};
