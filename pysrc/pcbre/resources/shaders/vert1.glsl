#version 330

uniform mat3 mat;
in vec2 vertex;
in vec4 color;
out vec4 color_vtx;

void main(void)
{
    vec3 calc = mat * vec3(vertex, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);
    color_vtx = color;
}

