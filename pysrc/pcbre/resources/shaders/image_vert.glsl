#version 150
uniform mat3 mat;

in vec2 vertex;
in vec2 texpos;

out vec2 pos;

void main(void)
{
    vec3 calc = mat * vec3(vertex, 1);
    gl_Position = vec4(calc.x, calc.y, 0, calc.z);
    pos = texpos;
}

