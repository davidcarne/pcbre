#version 150

in vec2 pos;

uniform sampler2D tex1;
uniform uvec4 layer_info;
out uvec4 frag_info;
//uniform float gamma;


void main(void)
{
    float dist = texture(tex1, pos).r;
    float d = dist - 0.75;

    float aa = clamp(0.75*length( vec2( dFdx( d ), dFdy( d ))), 0.001, 1.0);

    uvec4 newcolor = uvec4(0,0,0,0);
    newcolor.g = layer_info.g;
    newcolor.r = uint(smoothstep(-aa, +aa, dist - 0.75) * layer_info.r);

    frag_info = newcolor;
}

