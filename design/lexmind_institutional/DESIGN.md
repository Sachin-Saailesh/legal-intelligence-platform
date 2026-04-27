```markdown
# The Design System: Editorial Intelligence & Tonal Authority

## 1. Overview & Creative North Star: "The Digital Curator"
The design system for this autonomous legal intelligence platform is governed by the **Digital Curator** philosophy. In a world of legal noise, this system acts as a high-fidelity filter. We reject the "generic SaaS" look of rounded bubbles and flat white voids. Instead, we embrace **Architectural Density**—a nod to the Bloomberg terminal’s efficiency, reimagined with the prestige of a global law firm’s printed brief.

The system breaks the "template" look through:
*   **Intentional Asymmetry:** Heavy-weight sidebars balanced against airy, serif-driven document viewports.
*   **Tonal Layering:** Replacing harsh lines with shifts in surface temperature.
*   **The Power User's Density:** Information is not hidden; it is structured through a rigid, mathematical hierarchy.

---

## 2. Color & Surface Architecture
We move beyond simple "backgrounds." We use a spectrum of cool grays and deep navies to define importance without cluttering the user’s cognitive load.

### The "No-Line" Rule
Explicitly prohibit 1px solid borders for sectioning. Boundaries must be defined through background color shifts. For example, a `surface-container-low` section sitting on a `surface` background creates a natural edge that feels professional, not boxed-in.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. 
*   **Sidebar (`tertiary` #102441):** The foundation. Deep, immovable authority.
*   **Background (`surface` #F8F9FA):** The canvas.
*   **Nested Containers:** Use `surface-container-low` (#F3F4F5) for secondary utilities and `surface-container-lowest` (#FFFFFF) for primary work cards to create a "lifted" effect.

### The Glass & Gradient Rule
For floating elements like "Agent Processing" overlays, use **Glassmorphism**:
*   **Surface-Tint:** Semi-transparent `primary` with an 8px backdrop-blur. 
*   **Signature Textures:** Main CTAs should utilize a subtle linear gradient from `primary` (#022448) to `primary-container` (#1E3A5F) at a 135-degree angle. This adds "soul" and prevents the UI from feeling flat or "dead."

---

## 3. Typography: The Editorial Scale
We use a dual-font strategy to balance machine precision with human-readable authority.

| Role | Token | Font | Weight | Character |
| :--- | :--- | :--- | :--- | :--- |
| **Data/Meta** | Label-SM/MD | Inter | 500 | All-caps, +0.05em tracking for UI labels. |
| **Body** | Body-MD/LG | Inter | 400 | Neutral, highly legible for high-density data. |
| **Citations** | Monospace | JetBrains Mono | 400 | Technical precision for code and statutes. |
| **Reading** | Document | Georgia | 400 | The "Editorial" choice. Used for legal text. |
| **Headlines** | Headline-SM/MD | Inter | 600 | Authoritative, low-contrast, architectural. |

---

## 4. Elevation & Depth
Depth is achieved through **Tonal Layering** rather than traditional structural lines.

*   **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` section to create a soft, natural lift. 
*   **Ambient Shadows:** For floating modals, use an extra-diffused shadow: `0 12px 32px -4px rgba(2, 36, 72, 0.08)`. This uses a navy tint (the `on-surface` color) instead of black to mimic natural office light.
*   **The Ghost Border Fallback:** If a border is required for accessibility, use the `outline-variant` token at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components

### 5.1 Buttons (The "Command" Units)
*   **Primary:** Gradient of #022448 to #1E3A5F. White text. 6px radius (`md`).
*   **Secondary:** Ghost style. No background, `outline-variant` (20% opacity) border.
*   **States:**
    *   *Hover:* Increase gradient saturation.
    *   *Focus:* 2px ring of `secondary` (#1F6298) with 2px offset.
    *   *Loading:* Replace text with a micro-spinner; maintain button width.

### 5.2 Agent Route Badges (Categorical Intelligence)
High-density badges using 4px (`sm`) radius.
*   **CONTRACT:** Text `primary-fixed-dim` on `primary` background.
*   **RESEARCH:** Text `secondary-fixed` on `secondary` background.
*   **DRAFT:** Text #1A1A2E on `surface-container-high`.
*   **COMPLIANCE:** Text #FFFFFF on #16A34A (Low Risk Green).
*   **RISK:** Text #FFFFFF on #DC2626 (Critical).

### 5.3 Confidence Score Indicators
A horizontal 4-bar micro-sparkline.
*   **90-100%:** All 4 bars active in `secondary`.
*   **70-89%:** 3 bars active.
*   **<50%:** 1 bar active in `error` (#BA1A1A).

### 5.4 Input Fields & High-Density Tables
*   **Inputs:** 6px radius. No border; use `surface-container-high` background. On focus, transition background to `surface-container-lowest` with a subtle ghost border.
*   **Tables:** Forbid divider lines. Use alternating row shading (`surface-container-low`) and 16px vertical padding. Vertical alignment must be "Top" to accommodate high-density multi-line legal citations.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** use `JetBrains Mono` for all legal citations (e.g., *15 U.S.C. § 78u-4*).
*   **Do** prioritize vertical rhythm. Use the Spacing Scale (8px increments) to separate groups instead of lines.
*   **Do** use Georgia for the actual text of contracts; it reduces eye strain and signals "Official Document."

### Don’t:
*   **Don’t** use pure black (#000000) for anything. Use `on-primary-fixed` (#001C3B) for deep shadows or text.
*   **Don’t** use 100% opaque borders to separate UI regions. Let the background color shifts do the work.
*   **Don’t** use rounded "pill" buttons. Stick to the 6px (`md`) radius to maintain the "Terminal" professional aesthetic.

---

## 7. Component Token Map (Primitive vs. Semantic)

| UI Element | Color Token | Corner Radius |
| :--- | :--- | :--- |
| Main Sidebar | `#0F2340` | `0` |
| Primary Action | `#1E3A5F` | `6px (md)` |
| Risk: Critical | `#DC2626` | `4px (sm)` |
| Data Row (Hover) | `surface-container-high` | `0` |
| Document Card | `surface-container-lowest`| `8px (lg)` |
| Text: Meta/Data | `on-surface-variant` | `N/A` |

---
**Director's Final Note:** 
*The design system is not a set of constraints, but a framework for precision. Every pixel should feel as though it was placed with the same care as a clause in a supreme court brief. When in doubt, lean toward density and depth over whitespace and simplicity.*```