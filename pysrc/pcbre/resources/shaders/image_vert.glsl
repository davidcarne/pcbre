uniform mat3 mat;
attribute vec2 vertex;
attribute vec2 texpos;

varying vec2 pos;

void main(void)
{
    vec3 calc = mat * vec3(vertex, 1);
    gl_Position = vec4(calc.x, calc.y, 0, calc.z);
    pos = texpos;
}

