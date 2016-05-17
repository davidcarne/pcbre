#version 150


uniform mat3 mat;

in vec2 vertex;

in vec2 pos;
in float r;

out float ax;
out float ay;

in float r_inside_frac_sq;
out float _r_inside_frac_sq;

void main() {

    // x/y deltas for frag shader position calc
    ax = vertex.x;
    ay = vertex.y;

    vec3 calc = mat * vec3(vertex * r + pos, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);

    _r_inside_frac_sq = r_inside_frac_sq;
}
