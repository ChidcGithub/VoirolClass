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

float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

float smooth_noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
    for (int i = 0; i < 3; i++) {
        v += a * smooth_noise(p);
        p = rot * p * 2.0;
        a *= 0.5;
    }
    return v;
}

vec3 background(vec2 uv, vec2 aspect_uv, float time) {
    float n = fbm(aspect_uv * 2.5 + time * 0.01);
    return mix(
        vec3(0.04, 0.06, 0.10),
        vec3(0.10, 0.12, 0.18),
        uv.y * 0.5 + n * 0.10
    );
}

float sdRoundRect(vec2 p, vec2 size, float r) {
    vec2 d = abs(p) - size + r;
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
}

vec2 sdGrad(vec2 p, vec2 size, float r) {
    float eps = 0.5;
    float d0 = sdRoundRect(p, size, r);
    float dx = sdRoundRect(p + vec2(eps, 0.0), size, r);
    float dy = sdRoundRect(p + vec2(0.0, eps), size, r);
    return vec2(dx - d0, dy - d0) / eps;
}

void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;

    float micro = smooth_noise(uv * 40.0 + u_time * 0.4) * 0.002;
    vec2 duv = uv + vec2(micro, micro * 0.7);
    vec2 daspect = duv * vec2(aspect, 1.0);

    vec3 bg = background(duv, daspect, u_time);
    vec3 color = bg;

    float w = mix(60.0, 120.0, u_transition);
    float h = mix(4.0, 44.0, u_transition);

    vec2 half_size = vec2(w, h) * 0.5;
    float radius = mix(2.0, half_size.y, u_transition);

    float avg_level = (u_levels.x + u_levels.y + u_levels.z) / 3.0;
    float pulse = 1.0 + avg_level * 0.04;
    half_size *= pulse;

    vec2 center = u_resolution * 0.5;
    vec2 p = duv * u_resolution - center;

    float d = sdRoundRect(p, half_size, radius);
    float aa = 1.0 / u_resolution.y;
    float mask = 1.0 - smoothstep(0.0, aa * 2.0, d);

    if (mask > 0.001) {
        vec2 grad = sdGrad(p, half_size, radius);
        float grad_len = length(grad);
        vec2 grad_n = grad_len > 0.001 ? grad / grad_len : vec2(0.0);

        float edge_dist = abs(d);
        float refr_str = exp(-edge_dist * 8.0 / half_size.y) * 0.015;
        vec2 refr_uv = clamp(duv + grad_n * refr_str * u_resolution.y / u_resolution, 0.0, 1.0);
        vec2 refr_aspect = refr_uv * vec2(aspect, 1.0);
        vec3 refr_bg = background(refr_uv, refr_aspect, u_time);

        float edge_fac = 1.0 - smoothstep(0.0, half_size.y * 0.4, edge_dist);

        vec3 blur_bg = refr_bg * 2.0;
        float wsum = 2.0;
        for (int i = -1; i <= 1; i += 2) {
            vec2 tu = clamp(duv + vec2(float(i) * 1.2, 0.0) / u_resolution, 0.0, 1.0);
            blur_bg += background(tu, tu * vec2(aspect, 1.0), u_time);
            wsum += 1.0;
            vec2 tv = clamp(duv + vec2(0.0, float(i) * 1.2) / u_resolution, 0.0, 1.0);
            blur_bg += background(tv, tv * vec2(aspect, 1.0), u_time);
            wsum += 1.0;
        }
        blur_bg /= wsum;

        vec3 glass_bg = mix(blur_bg, refr_bg, edge_fac * 0.3);
        glass_bg *= (0.78 + 0.22 * smoothstep(0.0, half_size.y * 0.5, abs(d)));

        float fresnel = pow(1.0 - smoothstep(0.0, half_size.y, half_size.y - abs(d)), 3.0);
        vec3 fresnel_col = vec3(0.12, 0.2, 0.3) * fresnel * 0.12;

        float top_hl = smoothstep(0.0, 0.05, -d)
                     * smoothstep(0.0, 0.15, p.y + half_size.y)
                     * smoothstep(half_size.y * 0.6, half_size.y * 0.15, p.y);
        vec3 top_col = vec3(1.0) * top_hl * 0.05;

        float bot_rim = smoothstep(0.0, 0.06, -d)
                      * smoothstep(half_size.y * 0.25, half_size.y * 0.7, p.y);
        vec3 rim_col = vec3(0.25, 0.3, 0.4) * bot_rim * 0.06;

        color = mix(bg, glass_bg, 0.78);
        color += fresnel_col + top_col + rim_col;

        vec2 content_uv = p / half_size;

        if (u_state == 0) {
            float line_y = -0.85;
            float line_d = abs(content_uv.y - line_y);
            float line_mask = smoothstep(aa * 8.0, aa * 2.0, line_d);
            float idle_a = 0.15 + 0.2 * (0.5 + 0.5 * sin(u_time * 0.8));
            if (line_mask > 0.001) {
                color += vec3(0.4, 0.45, 0.55) * idle_a * line_mask;
            }
        } else if (u_state == 1) {
            float col_w = 0.12;
            float spacing = 0.20;
            float max_h = 0.65;
            float min_h = 0.08;

            for (int i = 0; i < 3; i++) {
                float fi = float(i);
                float cx = (fi - 1.0) * spacing;
                float bh = min_h + u_levels[i] * (max_h - min_h);

                vec2 bp = vec2(content_uv.x - cx, content_uv.y);
                vec2 bs = vec2(col_w * 0.5, bh);

                float bsdf = sdRoundRect(bp, bs, col_w * 0.5);
                float bm = 1.0 - smoothstep(0.0, aa * 3.0, bsdf);

                if (bm > 0.001) {
                    float bright = 0.5 + 0.5 * u_levels[i];
                    vec3 bc = vec3(0.6, 0.65, 0.7) * bright;
                    float glow = exp(-abs(bsdf) * 10.0) * 0.4 * u_levels[i];
                    bc += vec3(0.3, 0.4, 0.5) * glow;
                    color += bc * bm * 0.85;
                }
            }
        } else if (u_state == 2) {
            float dot_r = 0.055;
            float spacing = 0.20;
            float breathe = 0.6 + 0.3 * sin(u_time * 2.0);

            for (int i = 0; i < 3; i++) {
                float fi = float(i);
                vec2 dc = vec2((fi - 1.0) * spacing, 0.0);
                vec2 diff = content_uv - dc;
                diff.y *= half_size.x / half_size.y;
                float dd = length(diff) - dot_r;
                float dm = 1.0 - smoothstep(0.0, aa * 3.0, dd);

                if (dm > 0.001) {
                    vec3 dot_col = vec3(0.55, 0.6, 0.65) * breathe;
                    float dg = exp(-abs(dd) * 15.0) * 0.4 * breathe;
                    dot_col += vec3(0.25, 0.35, 0.5) * dg;
                    color += dot_col * dm * 0.85;
                }
            }

            for (int i = 0; i < 2; i++) {
                float fi = float(i);
                float x0 = (fi - 1.0) * spacing;
                float x1 = (fi + 1.0 - 1.0) * spacing;
                float seg = (content_uv.x - x0) / (x1 - x0);
                if (seg >= 0.0 && seg <= 1.0) {
                    float yl = sin(seg * 3.14159) * 0.07;
                    float ld = abs(content_uv.y - yl);
                    float lm = smoothstep(aa * 6.0, aa * 1.5, ld);
                    if (lm > 0.001) {
                        color += vec3(0.2, 0.3, 0.45) * breathe * 0.4 * lm;
                    }
                }
            }
        }

        if (u_state == 1 || u_state == 2) {
            float scan_x = content_uv.x * 0.5 + 0.5;
            float scan_d = abs(scan_x - fract(u_time * 0.3));
            float scan = exp(-scan_d * scan_d * 40.0);
            color += vec3(0.25, 0.3, 0.35) * scan * 0.12;
        }
    }

    float alpha = mask * 0.72;
    if (u_state == 0) {
        alpha = mask * (0.15 + 0.2 * (0.5 + 0.5 * sin(u_time * 0.8)));
    }

    frag_color = vec4(color, alpha);
}
"""
