VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 a_position;
out vec2 v_uv;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
    v_uv = a_position * 0.5 + 0.5;
}
"""

FRAGMENT_SHADER = """
#version 330 core

in vec2 v_uv;
out vec4 frag_color;

uniform vec2  u_resolution;
uniform float u_time;
uniform int   u_state;
uniform vec3  u_levels;
uniform float u_transition;

// ── helpers ──────────────────────────────────────────────

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

float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// ── rainbow edge color ──────────────────────────────────

vec3 edgeColor(vec2 p, vec2 half_size) {
    float angle = atan(p.y / half_size.y * 0.5, p.x / half_size.x);
    float hue = fract(angle / 6.28318 + u_time * 0.04);
    return hsv2rgb(vec3(hue, 0.65, 0.9));
}

// ── main ─────────────────────────────────────────────────

void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;

    // capsule dimensions — interpolated between idle and expanded
    float w_idle  = 64.0;
    float h_idle  = 6.0;
    float w_exp   = 420.0;
    float h_exp   = 48.0;
    float w  = mix(w_idle,  w_exp,  u_transition);
    float h  = mix(h_idle,  h_exp,  u_transition);
    vec2  hs = vec2(w, h) * 0.5;
    float r  = h * 0.5;

    vec2  center = u_resolution * 0.5;
    vec2  p      = (uv - 0.5) * u_resolution;
    float aa     = 1.0 / u_resolution.y;

    // ── background ───────────────────────────────────────
    vec3 bg = vec3(0.0, 0.0, 0.0);
    {
        float n  = noise(uv * u_resolution / 8.0 + u_time * 0.3) * 0.03;
        float g  = uv.y * 0.03;
        bg = vec3(0.02 + g + n);
    }

    // ── sdf + mask ───────────────────────────────────────
    float d    = sdRoundRect(p, hs, r);
    float mask = 1.0 - smoothstep(0.0, aa * 2.0, d);
    vec3  color = bg;

    if (mask < 0.001) {
        frag_color = vec4(bg, 0.0);
        return;
    }

    // ── glass fill ───────────────────────────────────────
    float soft  = 1.0 - smoothstep(0.0, hs.y * 0.6, abs(d));
    vec3 glass  = mix(vec3(0.03, 0.04, 0.06), vec3(0.08, 0.10, 0.14), soft);
    color = mix(bg, glass, mask * 0.72);

    // ── rainbow edge glow ────────────────────────────────
    {
        vec3  edge_col = edgeColor(p, hs);
        float edge_glow = exp(-abs(d) * 3.0 / (hs.y + 1.0)) * 0.55;
        color += edge_col * edge_glow;
    }

    // ── light sweep along border ─────────────────────────
    {
        float sweep_angle = fract(u_time * 0.15) * 6.28318;
        float p_angle     = atan(p.y / (hs.y + 1e-5), p.x);
        float sweep       = exp(-pow(abs(p_angle - sweep_angle) * 2.5, 2.0));
        float on_edge     = smoothstep(aa * 3.0, aa * 1.5, abs(d));
        color += vec3(1.0, 0.95, 0.85) * sweep * on_edge * 0.18;
    }

    // ── top reflection highlight ─────────────────────────
    {
        float top_hl = smoothstep(0.0, 0.08, -d)
                     * smoothstep(0.0, 0.3, p.y + hs.y)
                     * smoothstep(hs.y * 0.5, hs.y * 0.15, p.y);
        color += vec3(1.0) * top_hl * 0.05;
    }

    // ── interior content ─────────────────────────────────
    vec2 cuv = p / max(hs, 1.0);

    if (u_state == 0) {
        // ── IDLE: subtle breathing color line ────────────
        float line_y  = -0.78;
        float line_d  = abs(cuv.y - line_y);
        float lm      = smoothstep(aa * 10.0, aa * 2.0, line_d);
        float breathe = 0.25 + 0.18 * sin(u_time * 1.2);
        vec3  line_col = edgeColor(p, hs) * breathe * 0.7;
        color += line_col * lm;
    }
    else if (u_state == 1) {
        // ── LISTENING: waveform curves ───────────────────
        float avg_lv = (u_levels.x + u_levels.y + u_levels.z) / 3.0;
        float pulse  = 1.0 + avg_lv * 0.02;
        vec2  wp     = cuv / pulse;

        for (int b = 0; b < 3; b++) {
            float fi  = float(b);
            float lv  = u_levels[b];
            float amp = 0.08 + lv * 0.55;
            float freq = 4.5 + fi * 0.6 + lv * 2.0;
            float ph  = u_time * (1.2 + lv * 1.5) + fi * 2.1;
            float y0  = amp * sin(wp.x * freq + ph);
            float bw  = 0.006 + lv * 0.018;
            float bm  = smoothstep(bw * 2.0, bw * 0.3, abs(wp.y - y0));

            float hue  = fract(fi / 3.0 + u_time * 0.04);
            vec3  bcol = hsv2rgb(vec3(hue, 0.7, 0.85)) * (0.5 + lv * 0.5);
            float glow = exp(-abs(wp.y - y0) * 15.0) * lv * 0.5;
            color += bcol * (bm * 0.9 + glow * 0.3);
        }

        // ── center dot ────────────────────────────────────
        {
            float cd_r  = 0.025 + avg_lv * 0.015;
            float cd    = sdCircle(wp, cd_r);
            float cd_m  = 1.0 - smoothstep(0.0, aa * 4.0, cd);
            float cd_gl = exp(-abs(cd) * 20.0) * 0.5;
            color += vec3(0.9, 0.85, 0.95) * cd_m * 0.4;
            color += edgeColor(p, hs) * cd_gl * avg_lv;
        }
    }
    else if (u_state == 2) {
        // ── PROCESSING: rainbow breathing dots ────────────
        float spacing = 0.22;
        for (int i = 0; i < 3; i++) {
            float fi    = float(i);
            float dot_r = 0.04;
            float cx    = (fi - 1.0) * spacing;
            float cy    = sin(u_time * 2.5 + fi * 1.8) * 0.04;
            float dd    = sdCircle(cuv - vec2(cx, cy), dot_r);
            float dm    = 1.0 - smoothstep(0.0, aa * 4.0, dd);

            float hue   = fract(fi / 3.0 + u_time * 0.07);
            float brt   = 0.5 + 0.5 * sin(u_time * 3.0 + fi * 2.0);
            vec3  dcol  = hsv2rgb(vec3(hue, 0.6, 0.8)) * (0.5 + brt * 0.5);
            float dglow = exp(-abs(dd) * 18.0) * 0.45 * brt;
            color += dcol * (dm * 0.85 + dglow);
        }

        // ── connecting arcs between dots ──────────────────
        {
            float sweep_hue = fract(u_time * 0.06);
            vec3  sweep_col = hsv2rgb(vec3(sweep_hue, 0.7, 0.75));
            float sx = cuv.x * 0.5 + 0.5;
            float sweep = exp(-abs(sx - fract(u_time * 0.2)) * 12.0);
            float arc_shape = exp(-abs(cuv.y) * 40.0) * 0.7;
            color += sweep_col * sweep * arc_shape * 0.25;
        }
    }

    // ── final alpha ──────────────────────────────────────
    float alpha = mask;
    if (u_state == 0) {
        alpha = mask * (0.3 + 0.25 * sin(u_time * 0.8));
    } else {
        alpha = mask * 0.82;
    }

    frag_color = vec4(color, alpha);
}
"""
