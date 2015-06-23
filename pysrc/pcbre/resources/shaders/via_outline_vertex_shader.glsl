#version 330


uniform mat3 mat;

attribute vec2 vertex;

attribute vec2 pos;
attribute float r;
attribute vec4 color;

varying vec4 color_vtx;

void main() {

    vec3 calc = mat * vec3(vertex * r + pos, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);
    color_vtx = color;

}