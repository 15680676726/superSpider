import { theme } from "antd";

export const BREAKPOINTS = {
  xs: 480,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600,
} as const;

export type Breakpoint = keyof typeof BREAKPOINTS;

// ─────────────────────────────────────────────────────────
// Cyber Holo Design System — Ant Design Token Overrides
//
// 背景哲学：
//   深空哑光底 (#171821)  +  大圆角玻璃卡片  +  霓虹紫蓝点缀
//   参考 Daccord 风格：强层次、大圆角、精致间距、微弱光感
// ─────────────────────────────────────────────────────────

const NEON       = "#5c6ef5";   // 主霓虹紫蓝
const NEON_LIGHT = "#818cf8";   // 高亮紫蓝
const CYAN       = "#22d3ee";   // 强调青
const BG         = "#171821";   // 全局底色
const SURFACE    = "#242740";   // 卡片表面
const ELEVATED   = "#1e2035";   // 侧边栏/导航
const BORDER     = "rgba(255,255,255,0.06)";
const TEXT       = "#e2e8f0";
const TEXT_2     = "#94a3b8";

export const baizeTheme = {
  wave: { disabled: false },
  theme: {
    algorithm: theme.darkAlgorithm,
    cssVar: true,
    hashed: false,
    token: {
      // ── 品牌色 ──
      colorPrimary:   NEON,
      colorInfo:      CYAN,
      colorLink:      NEON_LIGHT,
      colorSuccess:   "#34d399",
      colorWarning:   "#fbbf24",
      colorError:     "#f87171",

      // ── 背景 ──
      colorBgBase:        BG,
      colorBgLayout:      "transparent",
      colorBgContainer:   "rgba(15, 16, 30, 0.65)",  /* 磨砂玻璃卡片底 */
      colorBgElevated:    "rgba(20, 21, 38, 0.82)",  /* 弹出层 比卡片更不透明 */
      colorBgSpotlight:   "rgba(20, 21, 38, 0.82)",

      // ── 文字 ──
      colorTextBase:      TEXT,
      colorText:          TEXT,
      colorTextSecondary: TEXT_2,
      colorTextTertiary:  "#64748b",
      colorTextDisabled:  "#475569",

      // ── 边框 ──
      colorBorder:          BORDER,
      colorBorderSecondary: "rgba(255,255,255,0.03)",
      colorSplit:           BORDER,

      // ── 填充 ──
      colorFill:        "rgba(255,255,255,0.04)",
      colorFillSecondary: "rgba(255,255,255,0.06)",
      colorFillTertiary: "rgba(255,255,255,0.02)",

      // ── 几何 ──
      borderRadius:   12,
      borderRadiusLG: 16,
      borderRadiusSM: 8,
      borderRadiusXS: 6,

      // ── 字体 ──
      fontFamily:    "'Inter', -apple-system, sans-serif",
      fontSize:      14,
      fontSizeSM:    12,
      fontSizeLG:    16,

      // ── 阴影 ──
      boxShadow:          "0 4px 16px rgba(0,0,0,0.4)",
      boxShadowSecondary: "0 2px 8px rgba(0,0,0,0.3)",

      // ── Motion ──
      motionDurationMid:   "0.2s",
      motionDurationSlow:  "0.3s",
      motionEaseInOut:     "cubic-bezier(0.4,0,0.2,1)",

      // ── 控件高度 ──
      controlHeight:   36,
      controlHeightLG: 42,
      controlHeightSM: 28,

      // ── 间距 ──
      padding:   16,
      paddingLG: 24,
      paddingSM: 12,
      paddingXS: 8,
      margin:    16,
      marginLG:  24,
      marginSM:  12,
    },
    components: {
      Layout: {
        bodyBg:     "transparent",
        headerBg:   "transparent",
        siderBg:    "rgba(15, 16, 30, 0.72)",  /* 磨砂玻璃侧边栏 */
        triggerBg:  "rgba(15, 16, 30, 0.72)",
        triggerColor: "#94a3b8",
      },
      Sider: {
        colorBgCollapsedButton: ELEVATED,
      },
      Card: {
        colorBgContainer: SURFACE,
        colorBorderSecondary: BORDER,
        borderRadiusLG: 16,
        paddingLG: 18,
        fontWeightStrong: 600,
      },
      Menu: {
        itemBg:           "transparent",
        subMenuItemBg:    "transparent",
        itemSelectedBg:   "rgba(92,110,245,0.18)",
        itemActiveBg:     "rgba(255,255,255,0.06)",
        itemHoverBg:      "rgba(255,255,255,0.06)",
        itemColor:        TEXT_2,
        itemHoverColor:   TEXT,
        itemSelectedColor: TEXT,
        itemPaddingInline: 12,
        itemBorderRadius:  10,
        itemMarginInline:  8,
        itemMarginBlock:   2,
        groupTitleColor:   "#64748b",
        groupTitleFontSize: 11,
        iconSize: 15,
        collapsedIconSize: 18,
        activeBarBorderWidth: 0,
      },
      Button: {
        fontWeight:        600,
        borderRadius:      10,
        colorPrimary:      NEON,
        colorPrimaryHover: NEON_LIGHT,
        primaryShadow:     `0 4px 12px rgba(92,110,245,0.35)`,
        defaultBg:         "rgba(255,255,255,0.04)",
        defaultBorderColor: BORDER,
        defaultColor:      TEXT,
        defaultShadow:     "none",
        controlHeight:     36,
      },
      Input: {
        colorBgContainer:  "rgba(0,0,0,0.25)",
        colorBorder:       BORDER,
        activeBorderColor: NEON,
        hoverBorderColor:  "rgba(255,255,255,0.12)",
        activeShadow:      `0 0 0 2px rgba(92,110,245,0.2)`,
        borderRadius:      10,
        paddingInline:     12,
        colorText:         TEXT,
        colorTextPlaceholder: "#64748b",
      },
      Select: {
        colorBgContainer:   "rgba(0,0,0,0.25)",
        colorBorder:        BORDER,
        optionSelectedBg:   "rgba(92,110,245,0.15)",
        optionActiveBg:     "rgba(255,255,255,0.04)",
        colorBgElevated:    SURFACE,
        borderRadius:       10,
        selectorBg:         "rgba(0,0,0,0.25)",
      },
      Modal: {
        contentBg:    SURFACE,
        headerBg:     "transparent",
        borderRadiusLG: 18,
        titleFontSize: 16,
        titleColor:    TEXT,
      },
      Drawer: {
        colorBgElevated: SURFACE,
        borderRadiusLG:  18,
      },
      Table: {
        headerBg:           "rgba(255,255,255,0.03)",
        headerColor:        TEXT_2,
        headerSortHoverBg:  "rgba(255,255,255,0.04)",
        rowHoverBg:         "rgba(255,255,255,0.04)",
        borderColor:        BORDER,
        colorBgContainer:   "transparent",
        cellPaddingBlock:   12,
        cellPaddingInline:  14,
        headerSplitColor:   BORDER,
        fixedHeaderSortActiveBg: "rgba(255,255,255,0.04)",
        bodySortBg:         "transparent",
      },
      Tabs: {
        itemColor:         TEXT_2,
        itemHoverColor:    TEXT,
        itemSelectedColor: TEXT,
        inkBarColor:       NEON,
        cardBg:            "transparent",
        colorBorderSecondary: BORDER,
        titleFontSize:     14,
        horizontalItemPadding: "12px 0",
        horizontalItemGutter: 24,
      },
      Tag: {
        colorBorder:     "rgba(92,110,245,0.25)",
        colorBgContainer: "rgba(92,110,245,0.12)",
        colorText:        NEON_LIGHT,
        borderRadiusSM:   999,
        fontSizeSM:       11,
      },
      Badge: {
        colorBgContainer: ELEVATED,
      },
      Switch: {
        colorPrimary:        NEON,
        colorPrimaryHover:   NEON_LIGHT,
        colorTextQuaternary: "rgba(255,255,255,0.2)",
      },
      Radio: {
        colorPrimary:   NEON,
        buttonBg:       "rgba(255,255,255,0.04)",
        buttonCheckedBg: NEON,
        radioSize:      15,
      },
      Checkbox: {
        colorPrimary: NEON,
        colorBorder:  BORDER,
      },
      Form: {
        labelColor:       TEXT_2,
        labelFontSize:    13,
        verticalLabelPadding: "0 0 6px",
      },
      Spin: {
        colorPrimary: NEON,
        dotSize: 24,
      },
      Tooltip: {
        colorBgSpotlight: ELEVATED,
        colorTextLightSolid: TEXT,
        borderRadius: 8,
      },
      Dropdown: {
        colorBgElevated: SURFACE,
        controlItemBgHover: "rgba(255,255,255,0.06)",
        controlItemBgActive: "rgba(92,110,245,0.15)",
        borderRadiusLG: 12,
      },
      Empty: {
        colorText:     TEXT_2,
        colorTextDisabled: "#64748b",
      },
      Statistic: {
        contentFontSize: 28,
        titleFontSize:   12,
        colorText:       TEXT,
        colorTextDescription: TEXT_2,
      },
    },
  },
} as const;
