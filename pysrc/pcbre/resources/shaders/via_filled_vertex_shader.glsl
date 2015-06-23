#version 330


uniform mat3 mat;

attribute vec2 vertex;

attribute vec2 pos;
attribute float r;

varying float ax;
varying float ay;

attribute vec4 color;
attribute float r_inside_frac_sq;

varying vec4 _color;
varying float _r_inside_frac_sq;

void main() {

    // x/y deltas for frag shader position calc
    ax = vertex.x;
    ay = vertex.y;

    vec3 calc = mat * vec3(vertex * r + pos, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);

    _color = color;
    _r_inside_frac_sq = r_inside_frac_sq;
}
