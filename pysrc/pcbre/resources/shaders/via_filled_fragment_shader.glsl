#version 150

in float ax;
in float ay;

in float _r_inside_frac_sq;
in vec4 _color;

out vec4 FragColor;

void main() {

    float d2 = ax * ax + ay * ay;

    if  (d2 > 1 || d2 < _r_inside_frac_sq)
        FragColor = vec4(0,0,0,0);
    else
        FragColor = _color;


}
