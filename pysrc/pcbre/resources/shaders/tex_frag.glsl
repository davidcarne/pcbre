
varying vec2 pos;

uniform sampler2D tex1;
uniform vec4 color;
//uniform float gamma;


void main(void)
{
    float dist = texture2D(tex1, pos).r;
    float d = dist - 0.75;

    float aa = clamp(0.75*length( vec2( dFdx( d ), dFdy( d ))), 0.001, 1);


    vec4 newcolor = color;
    newcolor.a *= smoothstep(-aa, +aa, dist - 0.75);
    gl_FragColor = newcolor;
}
