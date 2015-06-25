#version 150


uniform mat3 mat;

in vec2 vertex;

in vec2 pos;
in float r;
in vec4 color;

out vec4 color_vtx;

void main() {

    vec3 calc = mat * vec3(vertex * r + pos, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);
    color_vtx = color;

}
