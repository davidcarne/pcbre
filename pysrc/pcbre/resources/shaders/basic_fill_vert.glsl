#version 150

uniform mat3 mat;
in vec2 vertex;

void main(void)
{
    vec3 calc = mat * vec3(vertex, 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);
}
