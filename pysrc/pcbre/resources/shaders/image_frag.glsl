#version 330

in vec2 pos;

uniform sampler2D tex1;

void main(void)
{
    vec4 tex = texture2D(tex1, pos);
    gl_FragColor = vec4(tex.r, tex.g, tex.b, 1);
}
