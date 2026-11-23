"""Gold sphere impostors and thin geometric orbit ribbons, GLSL 3.3."""

SCREEN_VERTEX = """
#version 330
out vec2 uv;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

BACKGROUND_FRAGMENT = """
#version 330
in vec2 uv;
out vec4 color;
void main() {
    float vignette = smoothstep(0.10, 0.85, length((uv - 0.5) * vec2(1.3, 1.0)));
    vec3 background = mix(vec3(0.975, 0.972, 0.957), vec3(0.885, 0.901, 0.908), vignette);
    color = vec4(background, 1.0);
}
"""

SPHERE_VERTEX = """
#version 330
in vec2 in_corner;
in vec3 in_position;
in float in_radius;
uniform mat4 view;
uniform mat4 projection;
out vec2 disk;
out vec3 eye_center;
out float sphere_radius;
void main() {
    eye_center = (view * vec4(in_position, 1.0)).xyz;
    sphere_radius = in_radius;
    disk = in_corner;
    vec3 eye = eye_center + vec3(in_corner * in_radius, 0.0);
    gl_Position = projection * vec4(eye, 1.0);
}
"""

SPHERE_FRAGMENT = """
#version 330
uniform mat4 projection;
uniform bool microtexture;
in vec2 disk;
in vec3 eye_center;
in float sphere_radius;
out vec4 color;
void main() {
    float radius_squared = dot(disk, disk);
    if (radius_squared > 1.0) discard;
    vec3 normal = vec3(disk, sqrt(max(0.0, 1.0-radius_squared)));
    vec3 surface = eye_center + normal * sphere_radius;
    vec4 clip = projection * vec4(surface, 1.0);
    gl_FragDepth = (clip.z / clip.w) * 0.5 + 0.5;
    vec3 light = normalize(vec3(-0.50, 0.85, 1.30));
    vec3 fill = normalize(vec3(0.9, -0.4, 0.25));
    vec3 half_vector = normalize(light + vec3(0.0,0.0,1.0));
    float diffuse = max(dot(normal,light),0.0);
    float specular = pow(max(dot(normal,half_vector),0.0),52.0);
    float soft_specular = pow(max(dot(normal,half_vector),0.0),9.0);
    float texture_amount = 0.0;
    if (microtexture) {
        texture_amount = 0.018 * sin(normal.x*211.0+sin(normal.y*177.0))
                               * sin(normal.z*251.0+normal.y*149.0);
    }
    float rim = pow(1.0-normal.z,3.0);
    vec3 gold = vec3(1.0,0.64,0.045);
    vec3 shaded = gold * (0.27 + 0.62*diffuse
                          +0.08*max(dot(normal,fill),0.0)+texture_amount);
    shaded += vec3(1.0,0.94,0.74) * (0.42*specular+0.10*soft_specular);
    shaded += vec3(0.72,0.48,0.12)*rim*0.08;
    color = vec4(clamp(shaded,0.0,1.0),1.0);
}
"""

LINE_VERTEX = """
#version 330
in vec3 in_position;
uniform mat4 view;
uniform mat4 projection;
void main() { gl_Position = projection * view * vec4(in_position, 1.0); }
"""

LINE_FRAGMENT = """
#version 330
uniform vec4 line_color;
out vec4 color;
void main() { color = line_color; }
"""
