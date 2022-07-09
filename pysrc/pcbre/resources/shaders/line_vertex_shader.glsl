#version 150

uniform mat3 mat;

INPUT_TYPE vec2 pos_a;
INPUT_TYPE vec2 pos_b;
INPUT_TYPE float thickness;

/*
 * the line vertex shader is an instanced renderer
 * Each instance consists of two unit-radius semicircles
 * Each semicircle is associated with one end of the thickline being drawn
 * and each semicircle is translated/rotated to the end of the line
 */

in vec2 vertex;
in int ptid;

void main(void)
{
    
    vec2 pos;
    if (ptid == 0) {
        pos = pos_a;
    } else {
        pos = pos_b;
    }

    vec2 delta = pos_b - pos_a;

    if (length(delta) == 0)
        delta = vec2(1,0);

    vec2 linevec = normalize(delta);

    // In column order, matrix is transposed from written version
    mat2 endcap_r = mat2(
        linevec.x, linevec.y,
        -linevec.y, linevec.x
    );

    vec3 calc = mat * vec3(pos + endcap_r * (thickness * vertex), 1);
    gl_Position = vec4(calc.x, calc.y, 0, 1);

}

