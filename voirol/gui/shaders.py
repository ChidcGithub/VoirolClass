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

vec3 capsuleEdge(vec2 p, vec2 hs) {
    float angle = atan(p.y / max(hs.y, 1e-5) * 0.45, p.x);
    float hue = fract(angle / 6.28318 + u_time * 0.035);
    return hsv2rgb(vec3(hue, 0.55, 0.85));
}

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
    vec2 hs = vec2(w, h) * 0.5;
    float r = h * 0.5;

    vec2 p = (uv - 0.5) * u_resolution;

    // background
    float n = noise(uv * u_resolution / 12.0 + u_time * 0.2) * 0.02;
    vec3 bg = vec3(0.01 + n);

    float d = sdRoundRect(p, hs, r);
    float mask = 1.0 - smoothstep(0.0, aa * 2.5, d);

    if (mask < 0.001) {
        frag_color = vec4(0.0);
        return;
    }

    vec3 color = bg;

    // glass fill
    float soft = 1.0 - smoothstep(0.0, hs.y * 0.5, abs(d));
    vec3 glass = mix(vec3(0.02, 0.03, 0.05), vec3(0.06, 0.08, 0.12), soft);
    color = mix(bg, glass, mask * 0.78);

    // edge glow — subdued
    {
        vec3 ec = capsuleEdge(p, hs);
        float glow = exp(-abs(d) * 4.0 / (hs.y + 1.0)) * 0.35;
        color += ec * glow;
    }

    // soft border line
    {
        float border = smoothstep(aa * 3.0, aa * 0.5, abs(d));
        color += vec3(1.0) * border * 0.04;
    }

    // top specular
    {
        float top_hl = smoothstep(0.0, 0.06, -d)
                     * smoothstep(0.0, 0.35, p.y + hs.y)
                     * smoothstep(hs.y * 0.55, hs.y * 0.12, p.y);
        color += vec3(1.0) * top_hl * 0.06;
    }

    // ── inside content ──
    vec2 cuv = p / max(hs, 1.0);

    if (u_state == 0) {
        // IDLE: faint color bar
        float ly = -0.72;
        float ld = abs(cuv.y - ly);
        float lm = smoothstep(aa * 12.0, aa * 2.0, ld);
        float br = 0.25 + 0.15 * sin(u_time * 1.0);
        color += capsuleEdge(p, hs) * br * 0.55 * lm;
    }
    else if (u_state == 1) {
        // LISTENING: waveform curves
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            float lv = u_levels[i];
            float amp = 0.06 + lv * 0.48;
            float freq = 5.0 + fi * 0.7 + lv * 2.5;
            float ph = u_time * (1.3 + lv * 1.2) + fi * 2.1;
            float y0 = amp * sin(cuv.x * freq + ph);
            float bw = 0.007 + lv * 0.016;
            float bm = smoothstep(bw * 2.5, bw * 0.2, abs(cuv.y - y0));

            float hue = fract(fi / 3.0 + u_time * 0.03);
            vec3 bcol = hsv2rgb(vec3(hue, 0.55, 0.78)) * (0.5 + lv * 0.5);
            float g = exp(-abs(cuv.y - y0) * 18.0) * lv * 0.35;
            color += bcol * (bm * 0.82 + g);
        }
    }
    else if (u_state == 2) {
        // PROCESSING: breathing dots
        float sp = 0.24;
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            float cx = (fi - 1.0) * sp;
            float cy = sin(u_time * 2.0 + fi * 1.8) * 0.03;
            float rr = 0.035;
            float dd = length(cuv - vec2(cx, cy)) - rr;
            float dm = 1.0 - smoothstep(0.0, aa * 5.0, dd);
            float br = 0.45 + 0.35 * sin(u_time * 2.8 + fi * 2.0);
            float hue = fract(fi / 3.0 + u_time * 0.04);
            vec3 dc = hsv2rgb(vec3(hue, 0.5, 0.72)) * br;
            float dg = exp(-abs(dd) * 20.0) * 0.3 * br;
            color += dc * (dm * 0.8 + dg);
        }
    }

    // text texture
    if (u_show_text == 1 && u_text_alpha > 0.001) {
        vec2 tuv = (p + hs) / (2.0 * hs);
        vec4 tx = texture(u_text, tuv);
        color = mix(color, tx.rgb, tx.a * u_text_alpha);
    }

    float alpha = mask;
    if (u_state == 0) {
        alpha = mask * (0.28 + 0.22 * sin(u_time * 0.7));
    } else {
        alpha = mask * 0.82;
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
