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
uniform int   u_state;
uniform vec3  u_levels;
uniform float u_transition;
uniform sampler2D u_text;
uniform int   u_show_text;
uniform float u_text_alpha;

// ── helpers ─────────────────────────────────────────────────

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

float hash(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1, 0));
    float c = hash(i + vec2(0, 1));
    float d = hash(i + vec2(1, 1));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float sdRoundRect(vec2 p, vec2 sz, float r) {
    vec2 d = abs(p) - sz + r;
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
}

// Siri waveform envelope: tapers at edges
float siriEnvelope(float x) {
    float ax = abs(x);
    return pow(4.0 / (4.0 + pow(ax, 4.0)), 4.0);
}

// ── iridescent edge color ──────────────────────────────────

vec3 edgeColor(vec2 p, vec2 hs) {
    float angle = atan(p.y / max(hs.y, 1e-5) * 0.3, p.x);
    float dist  = length(p / hs);
    float hue   = fract(angle / 6.28318 + u_time * 0.025 + dist * 0.35);
    float sat   = 0.45 + 0.25 * sin(dist * 2.5 + u_time * 0.4);
    float val   = 0.75 + 0.25 * sin(dist * 3.0 + u_time * 0.6);
    return hsv2rgb(vec3(hue, sat, val));
}

// ── main ────────────────────────────────────────────────────

void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;
    float aa = 1.0 / u_resolution.y;

    float w_idle = 68.0;
    float h_idle = 7.0;
    float w_exp  = 440.0;
    float h_exp  = 52.0;
    float w = mix(w_idle, w_exp, u_transition);
    float h = mix(h_idle, h_exp, u_transition);
    vec2  hs = vec2(w, h) * 0.5;
    float r  = h * 0.5;

    vec2 p = (uv - 0.5) * u_resolution;

    // background — dark with subtle noise
    float bg_noise = noise(uv * u_resolution / 16.0 + u_time * 0.15) * 0.018;
    vec3 bg = vec3(0.005 + bg_noise);

    float d = sdRoundRect(p, hs, r);
    float mask = 1.0 - smoothstep(0.0, aa * 2.5, d);

    if (mask < 0.001) {
        frag_color = vec4(0.0);
        return;
    }

    vec3 color = bg;

    // ── glass fill with vertical gradient ──────────────────
    {
        float grad  = smoothstep(-hs.y, hs.y, p.y);  // 0=top, 1=bottom
        vec3 top_g  = vec3(0.07, 0.08, 0.12);
        vec3 mid_g  = vec3(0.04, 0.05, 0.08);
        vec3 bot_g  = vec3(0.02, 0.025, 0.04);
        float soft  = 1.0 - smoothstep(0.0, hs.y * 0.45, abs(d));
        vec3 glass  = mix(mix(top_g, mid_g, grad * 0.5), bot_g, grad * 0.7);
        glass = mix(glass, mid_g, soft * 0.4);
        // frost grain
        float grain = (noise(uv * u_resolution / 3.0) - 0.5) * 0.012;
        glass += grain;
        color = mix(bg, glass, mask * 0.80);
    }

    // ── edge glow: 3-layer ──────────────────────────────────
    {
        vec3 ec = edgeColor(p, hs);
        // inner sharp glow
        float glow1 = exp(-abs(d) * 18.0) * 0.28;
        // medium soft glow
        float glow2 = exp(-abs(d) * 4.5 / (hs.y + 1.0)) * 0.32;
        // outer ambient halo
        float glow3 = exp(-abs(d) * 1.3 / (hs.y + 1.0)) * 0.18;
        color += ec * (glow1 + glow2 + glow3);

        // chromatic aberration at edges
        float ca_fac = exp(-abs(d) * 6.0 / (hs.y + 1.0)) * 0.06;
        float ca_r = exp(-abs(d - 1.0) * 8.0) * 0.04;
        float ca_b = exp(-abs(d + 1.0) * 8.0) * 0.04;
        color += vec3(ca_r, 0.0, ca_b) * ca_fac;
    }

    // ── top specular highlight ──────────────────────────────
    {
        float spec = smoothstep(0.0, 0.08, -d)
                   * smoothstep(0.0, 0.35, p.y + hs.y)
                   * smoothstep(hs.y * 0.45, hs.y * 0.08, p.y);
        color += vec3(1.0, 0.97, 0.90) * spec * 0.10;
    }

    // ── inner shadow (bottom) ───────────────────────────────
    {
        float inner_d = sdRoundRect(p - vec2(0.0, -hs.y * 0.10), hs * 0.96, r);
        float inner_shadow = 1.0 - smoothstep(-aa * 3.0, aa * 6.0, inner_d);
        float shadow_mix = smoothstep(-hs.y * 0.3, -hs.y * 0.05, p.y);
        color += vec3(0.0) * inner_shadow * 0.09 * shadow_mix;
    }

    // ── Fresnel reflection ──────────────────────────────────
    {
        float fresnel = pow(1.0 - abs(p.y / max(hs.y, 1e-5)) * 0.65, 2.8);
        color += vec3(1.0, 0.95, 0.88) * fresnel * 0.055;
    }

    // ── inside content ──────────────────────────────────────
    vec2 cuv = p / max(hs, 1.0);

    if (u_state == 0) {
        // IDLE: faint breathing color bar
        float ly = -0.70;
        float ld = abs(cuv.y - ly);
        float lm = smoothstep(aa * 12.0, aa * 2.0, ld);
        float br = 0.28 + 0.16 * sin(u_time * 0.9);
        color += edgeColor(p, hs) * br * 0.60 * lm;
    }
    else if (u_state == 1) {
        // LISTENING: Siri-style multi-curve waveform
        float env = siriEnvelope(cuv.x * 1.65);

        for (int i = 0; i < 6; i++) {
            float fi  = float(i);
            float rf  = hash(vec2(fi, 0.42));  // pseudo-random per curve
            float rf2 = hash(vec2(fi, 0.87));
            float amp = 0.04 + rf * 0.35 + u_levels[i % 3] * 0.18;
            float freq = 4.0 + rf * 3.5 + u_levels[i % 3] * 2.0;
            float ph = u_time * (1.0 + rf2 * 1.5 + u_levels[i % 3] * 1.2) + fi * 1.8;
            float y0 = amp * env * sin(cuv.x * freq + ph) * 0.7;

            float bw  = 0.005 + rf * 0.010 + u_levels[i % 3] * 0.010;
            float bm  = smoothstep(bw * 3.0, bw * 0.15, abs(cuv.y - y0));

            float hue = fract(fi / 6.0 + u_time * 0.025);
            float sat = 0.50 + rf * 0.30;
            vec3 bcol = hsv2rgb(vec3(hue, sat, 0.78)) * (0.45 + rf * 0.55);
            float glow = exp(-abs(cuv.y - y0) * 16.0) * (0.20 + rf * 0.25);
            color += bcol * (bm * 0.75 + glow * 0.28);
        }

        // center bright dot
        float cd = length(cuv);
        float cdm = 1.0 - smoothstep(0.02, 0.06, cd);
        float cdg = exp(-cd * 22.0) * 0.40;
        color += vec3(1.0, 0.95, 0.90) * cdm * 0.30;
        float avg_lv = (u_levels.x + u_levels.y + u_levels.z) / 3.0;
        color += edgeColor(p, hs) * cdg * avg_lv;
    }
    else if (u_state == 2) {
        // PROCESSING: iOS 9 style animated curves
        float env = siriEnvelope(cuv.x * 2.2);

        for (int i = 0; i < 4; i++) {
            float fi  = float(i);
            float rf  = hash(vec2(fi + 0.1, 0.33));
            float rf2 = hash(vec2(fi + 0.1, 0.91));
            float amp = 0.03 + rf * 0.22;
            float freq = 5.5 + rf * 2.5;
            float ph = u_time * (0.8 + rf2 * 1.2) + fi * 2.2;
            float y0 = amp * env * sin(cuv.x * freq + ph) * 0.6;

            float bw  = 0.004 + rf * 0.008;
            float bm  = smoothstep(bw * 3.0, bw * 0.12, abs(cuv.y - y0));

            float hue = fract(fi / 4.0 + u_time * 0.03);
            float sat = 0.45 + rf * 0.35;
            vec3 bcol = hsv2rgb(vec3(hue, sat, 0.72)) * (0.40 + rf * 0.60);
            float glow = exp(-abs(cuv.y - y0) * 18.0) * (0.15 + rf * 0.22);
            color += bcol * (bm * 0.72 + glow * 0.24);
        }

        // sweeping scan line
        float sx = fract(u_time * 0.18);
        float scan = exp(-pow(abs(cuv.x * 0.5 + 0.5 - sx) * 4.0, 2.0));
        vec3 scan_col = edgeColor(p, hs);
        color += scan_col * scan * 0.15;
    }

    // text texture overlay
    if (u_show_text == 1 && u_text_alpha > 0.001) {
        vec2 tuv = (p + hs) / (2.0 * hs);
        vec4 tx = texture(u_text, tuv);
        color = mix(color, tx.rgb, tx.a * u_text_alpha);
    }

    float alpha = mask;
    if (u_state == 0) {
        alpha = mask * (0.25 + 0.20 * sin(u_time * 0.7));
    } else {
        alpha = mask * 0.84;
    }

    frag_color = vec4(color, alpha);
}
"""

MARQUEE_FRAGMENT = """
#version 330 core

in vec2 v_uv;
out vec4 frag_color;

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_active;

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
    vec2 uv = v_uv;

    float dx = min(uv.x, 1.0 - uv.x) * u_resolution.x;
    float dy = min(uv.y, 1.0 - uv.y) * u_resolution.y;
    float edge = min(dx, dy);

    float glow  = exp(-edge / 28.0) * 0.40;
    float sharp = exp(-edge / 5.0) * 0.55;

    float angle = atan(uv.y - 0.5, uv.x - 0.5);
    float hue = fract(angle / 6.28318 + u_time * 0.025);
    vec3 rainbow = hsv2rgb(vec3(hue, 0.55, 0.85));

    float a = (glow + sharp) * u_active * 0.78;
    frag_color = vec4(rainbow * a, a * 0.6);
}
"""
