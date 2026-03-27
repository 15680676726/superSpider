import { theme } from "antd";

// ---------------------------------------------------------------------------
// Responsive breakpoints (matches layout.css media queries)
// ---------------------------------------------------------------------------

export const BREAKPOINTS = {
  xs: 480,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600,
} as const;

export type Breakpoint = keyof typeof BREAKPOINTS;

// ---------------------------------------------------------------------------
// Noble Blue & Gold Theme  —  皇家蓝 × 香槟金
// ---------------------------------------------------------------------------

export const baizeTheme = {
  wave: {
    disabled: true,
  },
  theme: {
    algorithm: theme.darkAlgorithm,
    cssVar: true,
    hashed: false,
    token: {
      // Brand colors — 皇家蓝主色 / 香槟金强调
      colorPrimary: "#1B4FD8",
      colorInfo: "#2563EB",
      colorLink: "#C9A84C",
      colorSuccess: "#22c55e",
      colorWarning: "#E8C870",
      colorError: "#ef4444",

      // Surfaces — 午夜深蓝
      colorBgBase: "#03070F",
      colorBgLayout: "#03070F",
      colorBgContainer: "rgba(5, 12, 35, 0.50)",
      colorBgElevated: "rgba(10, 22, 60, 0.80)",

      // Text
      colorTextBase: "#EEF2FF",
      colorTextSecondary: "#A8B8D8",
      colorTextTertiary: "#6B7E9F",

      // Borders & Radius
      borderRadius: 12,
      borderRadiusLG: 16,
      borderRadiusSM: 8,
      colorBorder: "rgba(201, 168, 76, 0.20)",
      colorBorderSecondary: "rgba(201, 168, 76, 0.10)",

      // Shadows
      boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(201, 168, 76, 0.08)",
      boxShadowSecondary: "0 4px 16px rgba(0, 0, 0, 0.4)",

      // Typography
      fontFamily:
        "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      fontSize: 14,
      fontSizeHeading1: 30,
      fontSizeHeading2: 24,
      fontSizeHeading3: 20,

      // Motion
      motionDurationSlow: "0.4s",
      motionDurationMid: "0.25s",
      motionDurationFast: "0.15s",
      motionEaseInOut: "cubic-bezier(0.19, 1, 0.22, 1)",
    },
    components: {
      Layout: {
        bodyBg: "transparent",
        headerBg: "transparent",
        siderBg: "transparent",
        headerHeight: 80,
      },
      Card: {
        colorBgContainer: "rgba(5, 12, 35, 0.45)",
        colorBorderSecondary: "rgba(201, 168, 76, 0.12)",
        borderRadiusLG: 24,
      },
      Menu: {
        itemBg: "transparent",
        itemSelectedBg: "rgba(27, 79, 216, 0.20)",
        itemActiveBg: "rgba(201, 168, 76, 0.06)",
        itemPaddingInline: 16,
        itemBorderRadius: 12,
      },
      Button: {
        fontWeight: 700,
        borderRadius: 12,
        controlHeight: 40,
        controlHeightLG: 48,
        controlHeightSM: 32,
      },
      Input: {
        colorBgContainer: "rgba(5, 12, 35, 0.75)",
        activeBorderColor: "#C9A84C",
        hoverBorderColor: "rgba(201, 168, 76, 0.50)",
      },
      Select: {
        colorBgContainer: "rgba(5, 12, 35, 0.75)",
        optionSelectedBg: "rgba(27, 79, 216, 0.25)",
      },
      Modal: {
        contentBg: "rgba(5, 12, 35, 0.96)",
        headerBg: "transparent",
      },
      Drawer: {
        colorBgElevated: "rgba(5, 12, 35, 0.96)",
      },
      Table: {
        headerBg: "rgba(5, 12, 35, 0.70)",
        rowHoverBg: "rgba(201, 168, 76, 0.04)",
        borderColor: "rgba(201, 168, 76, 0.10)",
      },
      Tabs: {
        itemSelectedColor: "#C9A84C",
        inkBarColor: "#C9A84C",
        titleFontSize: 15,
        fontWeightStrong: 700,
      },
      Tag: {
        borderRadiusSM: 8,
        defaultBg: "rgba(27, 79, 216, 0.18)",
      },
      Alert: {
        colorInfoBg: "rgba(27, 79, 216, 0.12)",
        colorWarningBg: "rgba(201, 168, 76, 0.12)",
        colorErrorBg: "rgba(239, 68, 68, 0.10)",
        colorSuccessBg: "rgba(34, 197, 94, 0.10)",
      },
      Tooltip: {
        colorBgSpotlight: "rgba(5, 12, 35, 0.96)",
      },
      Result: {
        colorTextHeading: "#EEF2FF",
        colorTextDescription: "#A8B8D8",
      },
    },
  },
} as const;
