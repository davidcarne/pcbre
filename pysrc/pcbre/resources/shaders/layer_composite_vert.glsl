#version 150

/* Basic passthrough shader for layer compositing */

in vec2 vertex;
in vec2 texpos;

out vec2 texpos_v;

void main(void)
{
    gl_Position = vec4(vertex.x, vertex.y, 0, 1);
    texpos_v = texpos;
}

