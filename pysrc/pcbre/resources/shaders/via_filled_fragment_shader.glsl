#version 150

in float ax;
in float ay;

in float _r_inside_frac_sq;

uniform uint color;

out uvec4 frag_info;

void main() {

    float d2 = ax * ax + ay * ay;

    if  (d2 > 1 || d2 < _r_inside_frac_sq)
        discard;
    else {
        frag_info.rg = uvec2(255, color);
    }


}
