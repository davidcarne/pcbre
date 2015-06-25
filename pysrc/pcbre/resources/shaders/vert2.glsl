#version 150

uniform mat3 mat;
uniform vec4 color;
in vec2 vertex;

out vec4 color_vtx;

void main(void)
{
    vec3 calc = mat * vec3(vertex, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);
    color_vtx = color;
}

