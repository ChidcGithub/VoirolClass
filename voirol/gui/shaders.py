VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 a_position;
out vec2 v_uv;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
    v_uv = a_position * 0.5 + 0.5;
}
"""

CAPSULE_FRAGMENT = """
#version 330 core

in vec2 v_uv;
out vec4 frag_color;

uniform vec2  u_resolution;
uniform float u_time;
uniform int   u_state;        // 0=IDLE, 1=LISTENING, 2=PROCESSING
uniform float u_levels_avg;   // 0-1 audio level
uniform float u_transition;   // 0=idle form, 1=expanded form
uniform sampler2D u_text;
uniform int   u_show_text;
uniform float u_text_alpha;

// M3 palette (passed from host for themeability — adapts to light/dark)
uniform vec3  u_color_primary;            // primary
uniform vec3  u_color_on_primary;         // on_primary (used for text-on-primary)
uniform vec3  u_color_primary_container;  // primary_container (PROCESSING 备选)
uniform vec3  u_color_on_primary_container; // on_primary_container
uniform vec3  u_color_surface_highest;    // surface_container_highest
uniform vec3  u_color_surface_high;       // surface_container_high
uniform vec3  u_color_surface_container;  // surface_container
uniform vec3  u_color_outline_variant;    // outline_variant
uniform vec3  u_color_on_surface;         // on_surface
uniform vec3  u_color_on_surface_variant; // on_surface_variant
uniform vec3  u_color_secondary;          // secondary (用于 IDLE 状态色)
uniform float u_is_dark;                  // 1.0 = dark theme, 0.0 = light theme

float sdRoundRect(vec2 p, vec2 sz, float r) {
    vec2 d = abs(p) - sz + r;
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
}

float sdRoundedBar(vec2 p, float half_w, float half_h, float r) {
    return sdRoundRect(p, vec2(half_w, half_h), r);
}

void main() {
    vec2 uv = v_uv;
    float aa = 1.0 / u_resolution.y;

    // M3 规范尺寸：圆角 28dp (shape.xl)
    float w_idle = 64.0;
    float h_idle = 8.0;
    float w_exp  = 480.0;
    float h_exp  = 56.0;
    float w = mix(w_idle, w_exp, u_transition);
    float h = mix(h_idle, h_exp, u_transition);
    vec2  hs = vec2(w, h) * 0.5;
    // 圆角 = min(h/2, 28)，保证 idle 时是药丸，展开时是 28dp 圆角矩形
    float r  = min(h * 0.5, 28.0);

    vec2 p = (uv - 0.5) * u_resolution;
    float d = sdRoundRect(p, hs, r);
    float mask = 1.0 - smoothstep(0.0, aa * 2.0, d);

    // 提前剔除完全透明像素（距离远超阴影范围）
    if (mask < 0.001 && d > 12.0) {
        frag_color = vec4(0.0);
        return;
    }

    // ── M3 状态色映射 ──
    // IDLE:       surface_container (低调，呼吸感)
    // LISTENING:  surface_container_high (elevated, 显示波形)
    // PROCESSING: primary (强调色，引导注意力)
    vec3 base_color;
    float alpha = mask;

    if (u_state == 2) {
        // PROCESSING: primary fill
        base_color = u_color_primary;
    } else if (u_state == 1) {
        // LISTENING: surface_container_high (M3 elevated surface)
        base_color = u_color_surface_high;
    } else {
        // IDLE: surface_container (M3 标准表面)
        base_color = u_color_surface_container;
    }

    vec3 color = base_color;

    // ── M3 Elevation 阴影（多层软阴影模拟 elevation-3）──
    // 阴影只在展开状态下显示
    float shadow_alpha = u_transition * 0.30;
    if (d > 0.0 && shadow_alpha > 0.01) {
        // 外阴影：两层 (ambient + key)
        float ambient = exp(-d / 8.0) * shadow_alpha * 0.6;
        float key = exp(-max(d - 2.0, 0.0) / 4.0) * shadow_alpha * 0.8;
        float shadow = ambient + key;
        // 阴影偏移向下（模拟光源上方）
        float dy = p.y + 3.0;  // 下偏 3px
        float d_shadow = sdRoundRect(vec2(p.x, dy), hs, r);
        float shadow_mask = 1.0 - smoothstep(0.0, aa * 2.0, d_shadow);
        shadow *= (1.0 - shadow_mask);  // 只在形状外显示
        color = mix(color, vec3(0.0), shadow);
    }

    // ── M3 surface tint（primary 色叠加，海拔越高越浓）──
    if (u_state != 0 && mask > 0.001) {
        float tint_alpha = (u_state == 2) ? 0.0 : 0.08 * u_transition;
        color = mix(color, u_color_primary, tint_alpha);
    }

    if (mask > 0.001) {
        if (u_state == 0) {
            // IDLE: M3 subtle breathing — 使用 secondary 色，低饱和度
            float breath = 0.5 + 0.5 * sin(u_time * 1.2);
            color = mix(color, u_color_secondary, 0.10 * breath);
            alpha *= 0.60 + 0.30 * breath;
        }
        else if (u_state == 1) {
            // LISTENING: M3 圆润波形条（圆头，带音频响应）
            vec2 cuv = p / hs;
            // 5 条波形（M3 倾向更少更精致的元素）
            float bar_count = 5.0;
            float bar_w = 0.045;
            float bar_gap = 0.14;
            float total_w = bar_count * bar_w + (bar_count - 1.0) * bar_gap;
            float start_x = -total_w * 0.5;
            float bars = 0.0;
            for (int i = 0; i < 5; i++) {
                float fi = float(i);
                float cx = start_x + fi * (bar_w + bar_gap) + bar_w * 0.5;
                // 圆头波形条：用 SDF 距离场
                float phase = u_time * 4.0 + fi * 0.9;
                float env = 0.30 + 0.55 * (0.5 + 0.5 * sin(phase));
                float h_norm = env * (0.35 + 0.65 * u_levels_avg);
                float bar_h = h_norm * 0.7;  // 波形条高度（相对）
                // 波形条 SDF：圆头矩形
                vec2 bar_p = vec2((cuv.x - cx) / bar_w, cuv.y / bar_h);
                float bar_d = length(max(abs(bar_p) - vec2(0.5, 0.5), 0.0));
                float bar_mask = 1.0 - smoothstep(0.0, 0.05, bar_d);
                bars = max(bars, bar_mask);
            }
            // 波形条用 primary 色
            color = mix(color, u_color_primary, bars * 0.85);
            // M3 细描边 (outline_variant)
            float border = smoothstep(0.0, aa * 1.5, abs(d + 0.5));
            color = mix(u_color_outline_variant, color, border);
        }
        else if (u_state == 2) {
            // PROCESSING: M3 强调脉冲 — 用 on_primary 做内发光
            float pulse = 0.5 + 0.5 * sin(u_time * 2.5);
            // 内发光：从中心向外渐变
            float inner = 1.0 - smoothstep(0.0, hs.y * 0.9, abs(p.y));
            color += u_color_on_primary * 0.04 * pulse * inner;
            // M3 state layer：顶部一层淡 on_primary 叠加
            float state_layer = 0.08 * pulse;
            color = mix(color, u_color_on_primary, state_layer * mask);
        }
    }

    // text overlay — M3 文本颜色根据状态选择
    if (u_show_text == 1 && u_text_alpha > 0.001) {
        vec2 tuv = (p + hs) / (2.0 * hs);
        if (tuv.x >= 0.0 && tuv.x <= 1.0 && tuv.y >= 0.0 && tuv.y <= 1.0) {
            vec4 tx = texture(u_text, tuv);
            // PROCESSING (primary fill) → on_primary
            // LISTENING (surface fill) → on_surface
            vec3 text_tint = (u_state == 2) ? u_color_on_primary : u_color_on_surface;
            color = mix(color, text_tint, tx.a * u_text_alpha);
        }
    }

    frag_color = vec4(color, alpha);
}
"""

MARQUEE_FRAGMENT = """
#version 330 core

in vec2 v_uv;
out vec4 frag_color;

uniform vec2  u_resolution;
uniform float u_active;
uniform float u_time;
uniform vec3  u_color_primary;  // 从主题获取的主色

// Primary-colored aurora glow with breathing
void main() {
    vec2 uv = v_uv;
    vec2 res = u_resolution;

    float dx = min(uv.x, 1.0 - uv.x) * res.x;
    float dy = min(uv.y, 1.0 - uv.y) * res.y;
    float edge = min(dx, dy);

    // soft wide glow + sharper edge line
    float glow = exp(-edge / 36.0) * 0.32;
    float sharp = exp(-edge / 5.0) * 0.45;

    // breathing: opacity 0.5 → 1.0 over 3s
    float breath = 0.5 + 0.5 * sin(u_time * 2.094);  // ~3s period
    float intensity = (glow + sharp) * u_active * (0.55 + 0.45 * breath);

    // aurora color follows the theme primary
    frag_color = vec4(u_color_primary * intensity, intensity * 0.55);
}
"""
